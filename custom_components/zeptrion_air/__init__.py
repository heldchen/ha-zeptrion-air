"""
Custom integration to integrate Zeptrion Air devices with Home Assistant.

For more details about this integration, please refer to
https://github.com/heldchen/ha-zeptrion-air
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform # Removed CONF_PASSWORD, CONF_USERNAME as they are not used here
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
        all_channels_scan = await api_client.async_get_all_channels_scan_info()
        # Added debug log for full chscan response
        LOGGER.debug(f"Full /zrap/chscan response for {hostname}: {all_channels_scan}")
    except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e: # More specific exceptions
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
    sw_version_raw = zrap_id_data.get('sw') # Renamed to sw_version_raw
    hub_name = entry.title or hostname.replace('.local', '') # Use entry title if available

    hub_device_info = {
        "identifiers": {(DOMAIN, serial_number)}, # Use API serial number as primary identifier
        "name": hub_name,
        "manufacturer": "Feller AG", # Manufacturer is fixed
        "model": model,
        # "sw_version" will be added conditionally below
        "connections": {(device_registry.CONNECTION_UPNP, hostname)}, # For linking via network
    }

    if isinstance(sw_version_raw, str) and sw_version_raw.strip():
        hub_device_info["sw_version"] = sw_version_raw.strip()
        LOGGER.debug(f"Using software version for hub {serial_number}: {sw_version_raw.strip()}")
    else:
        LOGGER.debug(f"No valid software version found for hub {serial_number} (raw: '{sw_version_raw}'). Omitting sw_version from device info.")
    
    # Register the hub device in HA Device Registry
    # This replaces the later device_registry call using coordinator data if coordinator is not primary source for this.
    registry = device_registry.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **hub_device_info # Pass the prepared dict
    )

    # Identify Blind Channels
    blind_channel_ids = []
    # Example structure: {'chscan': {'ch1': {'val': '0'}, 'ch2': {'val': '-1'}}}
    # Or for multiple channels: {'chscan': {'ch': [{'@id': '1', 'val': '0'}, ...]}}
    # The api.py returns parsed XML, so need to handle its structure.
    # Let's assume api.py's _api_xml_wrapper returns something like:
    # {'chscan': {'ch1': {'val': '0'}, 'ch2': {'val': '100'}, 'ch3': {'val': '-1'}}} for single device scan
    # or {'chscan': {'ch': [{'val': '0', '@id': '1'}, {'val': '-1', '@id': '2'}]} if structure is list
    
    # Adjusted scan_data access and added debug log
    scan_data = all_channels_scan.get('zrap', {}).get('chscan', {})
    LOGGER.debug(f"Extracted 'chscan' data for {hub_name}: {scan_data}")

    if scan_data:
        # Check if 'ch' is a list (multiple channels) or dict (single channel)
        channels = scan_data.get('ch')
        if channels:
            if not isinstance(channels, list):
                channels = [channels] # Make it a list for consistent processing
            for channel_data in channels:
                if isinstance(channel_data, dict) and channel_data.get('val') == '-1':
                    channel_id_str = channel_data.get('@id') # Assuming @id for channel number
                    # Added debug log before appending
                    LOGGER.debug(f"List processing: Found potential blind channel: ID='{channel_id_str}', Data='{channel_data}'")
                    if channel_id_str:
                        try:
                            blind_channel_ids.append(int(channel_id_str))
                        except ValueError:
                            LOGGER.warning(f"Invalid channel ID format: {channel_id_str}")
        else: # Fallback for structure like {'ch1': {'val': '0'}, ...}
            for key, value_dict in scan_data.items():
                if key.startswith('ch') and isinstance(value_dict, dict) and value_dict.get('val') == '-1':
                    channel_id_str = key[2:] # Extract number from 'chX'
                    # Added debug log before appending
                    LOGGER.debug(f"Fallback key processing: Found potential blind channel from key: ID='{channel_id_str}', Data='{value_dict}'")
                    try:
                        blind_channel_ids.append(int(channel_id_str))
                    except ValueError:
                        LOGGER.warning(f"Invalid channel key format: {key}")
                        
    LOGGER.info(f"Identified blind channels for {hub_name}: {blind_channel_ids}")

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
    # This dictionary should contain all keys that platforms (like cover.py) expect.
    # Note: cover.py was written expecting "api_client", "entry_title", "hub_serial".
    # Using "client" here as per prompt, which means cover.py might need an update or this key should be "api_client".
    # For now, following prompt to use "client".
    platform_setup_data = {
        "client": api_client, 
        "hub_device_info": hub_device_info, # For the main Zeptrion Air device/hub
        "blind_channels": blind_channel_ids,
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
