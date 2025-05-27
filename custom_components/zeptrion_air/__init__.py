"""
Custom integration to integrate Zeptrion Air devices with Home Assistant.

For more details about this integration, please refer to
https://github.com/heldchen/ha-zeptrion-air
"""

from __future__ import annotations

import logging
import re # Added import
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration
from homeassistant.helpers import device_registry

from .api import (
    ZeptrionAirApiClient,
    ZeptrionAirApiClientError, # Added import
    ZeptrionAirApiClientCommunicationError, # Added import
)
from .coordinator import ZeptrionAirDataUpdateCoordinator
from .data import ZeptrionAirData

from .const import DOMAIN, LOGGER, CONF_HOSTNAME, PLATFORMS as ZEPTRION_PLATFORMS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import ZeptrionAirConfigEntry


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZeptrionAirConfigEntry,
) -> bool:
    """Set up the Zeptrion Air Hub from a config entry."""

    hostname = entry.data[CONF_HOSTNAME]
    api_client = ZeptrionAirApiClient(hostname=hostname, session=async_get_clientsession(hass))

    # It seems the coordinator is set up but might not be strictly necessary for one-off fetches
    # like device ID and initial channel scan if platforms manage their own updates or don't need polling.
    # For now, let's use the api_client directly for setup data.
    # If coordinator is essential for other platforms (sensor, switch), it can remain.

    try:
        device_data_api = await api_client.async_get_device_identification()
        # Removed all_channels_scan, replaced by channel_des_data
        channel_des_data = await api_client.async_get_channel_descriptions()
        LOGGER.debug(f"Full /zrap/chdes response for {hostname}: {channel_des_data}") # Using hostname as hub_name defined later
    except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
        LOGGER.error(f"Failed to connect or communicate with Zeptrion Air device {hostname}: {e}")
        return False
    except Exception as e: # Catch any other unexpected error during setup
        LOGGER.error(f"Unexpected error setting up Zeptrion Air device {hostname}: {e}")
        return False

    # Prepare Hub device_info
    # Assuming device_data_api is the parsed XML dict from /zrap/id
    # Example: {'id': {'hw': '01.04.00', 'sn': '12345555', 'sys': 'ZEPTRION', ...}}
    zrap_id_data = device_data_api.get('id', {})
    if not zrap_id_data:
        LOGGER.error(f"Failed to get valid device identification from {hostname} (empty 'id' field)")
        return False

    serial_number = zrap_id_data.get('sn')
    if not serial_number: # Serial number is crucial for unique device identification
        LOGGER.error(f"Could not determine serial number for {hostname} from API. Cannot set up device.")
        return False
        
    # Ensure entry.unique_id is consistent with the serial_number if possible.
    # If entry.unique_id exists and differs, it might indicate a mismatch or an old entry.
    # For simplicity here, we'll use serial_number as the canonical source of truth for the device ID.
    # Config flow should ideally set entry.unique_id to the serial number upon discovery/setup.
    if entry.unique_id and entry.unique_id != serial_number:
        LOGGER.warning(
            f"Config entry unique ID {entry.unique_id} does not match device serial number {serial_number}. "
            f"Using serial number from API ({serial_number}) for device identification."
        )
    # If no unique_id on entry, or if we decide to always align it:
    # hass.config_entries.async_update_entry(entry, unique_id=serial_number) # Requires careful consideration

    model = zrap_id_data.get('type', 'Zeptrion Air Device')
    # sw_version_raw and parsed_sw_version logic is removed.
    hub_name = entry.title or hostname.replace('.local', '') # Use entry title if available

    hub_device_info = {
        "identifiers": {(DOMAIN, serial_number)}, # Use API serial number as primary identifier
        "name": hub_name,
        "manufacturer": "Feller AG", # Manufacturer is fixed
        "model": model,
        "connections": {(device_registry.CONNECTION_UPNP, hostname)}, # For linking via network
        # "sw_version" is intentionally omitted.
    }
    
    LOGGER.debug(f"Constructed hub_device_info for {serial_number} (sw_version omitted for testing): {hub_device_info}")

    # Register the hub device in HA Device Registry
    # This replaces the later device_registry call using coordinator data if coordinator is not primary source for this.
    registry = device_registry.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **hub_device_info # Pass the prepared dict
    )

    # Identify channels using /zrap/chdes
    identified_channels = []
    # Assuming hub_name is defined before this block, as in the original code.
    # If not, use hostname for logging here.
    
    chdes_root = channel_des_data.get('zrap', {}).get('chdes', {})
    LOGGER.debug(f"Extracted 'chdes' data for {hub_name}: {chdes_root}")

    raw_channels_from_chdes = []
    if chdes_root:
        if 'ch' in chdes_root: # Case: {'chdes': {'ch': [...] or {...}}}
            raw_channels_data = chdes_root['ch']
            if isinstance(raw_channels_data, list):
                raw_channels_from_chdes = raw_channels_data
            elif isinstance(raw_channels_data, dict):
                raw_channels_from_chdes = [raw_channels_data] # Single channel entry
        else: # Case: {'chdes': {'ch1': {...}, 'ch2': {...}}}
            for key, value_dict in chdes_root.items():
                if key.startswith('ch') and isinstance(value_dict, dict):
                    # Add the channel number as 'id' if not present, or ensure it's consistent
                    # xmltodict might put ch1 content directly, ch number is key
                    value_dict_copy = value_dict.copy() # Avoid modifying original
                    if 'id' not in value_dict_copy and '@id' not in value_dict_copy : # If 'id' or '@id' is not in the dict from chX
                         value_dict_copy['id_from_key'] = key[2:] # Store ch number from key e.g. "1" from "ch1"
                    raw_channels_from_chdes.append(value_dict_copy)
    
    LOGGER.debug(f"Raw channels list from /zrap/chdes for {hub_name}: {raw_channels_from_chdes}")

    for channel_data in raw_channels_from_chdes:
        channel_id_str = channel_data.get('@id', channel_data.get('id', channel_data.get('id_from_key')))
        cat_str = channel_data.get('cat', channel_data.get('@cat')) # API doc uses 'cat' as element
        name = channel_data.get('name')
        # API doc example uses 'group' for friendly name, 'icon' for icon
        friendly_name = channel_data.get('group') 
        icon = channel_data.get('icon')
        
        channel_name = friendly_name or name # Use group (as friendly_name) if available, else name

        if channel_id_str is None or cat_str is None:
            LOGGER.debug(f"Ignoring channel, missing id or cat: ID='{channel_id_str}', Cat='{cat_str}', Data='{channel_data}'")
            continue

        try:
            channel_id_int = int(channel_id_str)
            cat_int = int(cat_str)
        except ValueError:
            LOGGER.warning(f"Could not parse channel ID '{channel_id_str}' or category '{cat_str}' to int. Skipping.")
            continue

        # Categories for blinds/shutters: 1 (Jalousie), 3 (Store), 5 (Rollladen), 6 (Markise)
        # Assuming these are the correct category integers based on typical Zeptrion usage.
        if cat_int in [1, 3, 5, 6]:
            channel_info = {
                "id": channel_id_int,
                "cat": cat_int,
                "name": channel_name, # This is the 'friendly_name' or 'name'
                "icon": icon,
                "type": "cover" # Explicitly type it for platform setup
            }
            identified_channels.append(channel_info)
            LOGGER.debug(f"Identified usable COVER channel for {hub_name}: {channel_info}")
        else:
            # Could add logic here for other types e.g. lights (cat 0, 2, 4, 7) if a 'switch' platform is added
            LOGGER.debug(f"Ignoring channel id {channel_id_int} with cat '{cat_int}' (name: '{channel_name}') for {hub_name} as it's not a recognized cover type.")

    LOGGER.info(f"Final identified usable channels for {hub_name}: {identified_channels}")

    # Get the integration object (no await needed)
    integration_obj = async_get_loaded_integration(hass, entry.domain)
    
    # Initialize Coordinator
    coordinator = ZeptrionAirDataUpdateCoordinator(hass=hass) # No client arg here

    # Instantiate ZeptrionAirData CORRECTLY for entry.runtime_data
    # Pass only the arguments defined in the ZeptrionAirData dataclass.
    zeptrion_air_data_for_runtime = ZeptrionAirData(
        client=api_client,
        coordinator=coordinator, # Pass the coordinator instance
        integration=integration_obj
    )
    entry.runtime_data = zeptrion_air_data_for_runtime

    # Prepare platform_setup_data Dictionary for hass.data
    platform_setup_data = {
        "client": api_client, 
        "hub_device_info": hub_device_info, # For the main Zeptrion Air device/hub
        "identified_channels": identified_channels, # New key with list of channel_info dicts
        "entry_title": hub_name, # Name of the hub entry (derived from entry.title or hostname)
        "hub_serial": serial_number, # Unique ID of the hub
        "coordinator": coordinator # Platforms might need the coordinator instance
    }
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = platform_setup_data
    
    # Refresh coordinator data.
    # The coordinator's _async_update_data method should use entry.runtime_data.client
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, ZEPTRION_PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    # The device registration for the hub is now done earlier with more details.
    # The original LOGGER.info("Coordinator data: %s", coordinator.data) can be misleading
    # if coordinator.data is from /zrap/id and we've already processed it.
    # The coordinator.async_config_entry_first_refresh() might be redundant if data is already fetched
    # but doesn't harm, and ensures coordinator has its data if other platforms rely on it.

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ZeptrionAirConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ZEPTRION_PLATFORMS)
    if unload_ok:
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id)
        # Clean up runtime_data if it was set by this integration
        if hasattr(entry, 'runtime_data') and isinstance(entry.runtime_data, ZeptrionAirData):
            entry.runtime_data = None # Or consider del entry.runtime_data
    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ZeptrionAirConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
