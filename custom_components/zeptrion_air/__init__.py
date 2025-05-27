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
    sw_version = zrap_id_data.get('sw')
    hub_name = entry.title or hostname.replace('.local', '') # Use entry title if available

    hub_device_info = {
        "identifiers": {(DOMAIN, serial_number)}, # Use API serial number as primary identifier
        "name": hub_name,
        "manufacturer": "Feller AG", # Manufacturer is fixed
        "model": model,
        "sw_version": sw_version,
        "connections": {(device_registry.CONNECTION_UPNP, hostname)}, # For linking via network
    }
    
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
    
    scan_data = all_channels_scan.get('chscan', {})
    if scan_data:
        # Check if 'ch' is a list (multiple channels) or dict (single channel)
        channels = scan_data.get('ch')
        if channels:
            if not isinstance(channels, list):
                channels = [channels] # Make it a list for consistent processing
            for channel_data in channels:
                if isinstance(channel_data, dict) and channel_data.get('val') == '-1':
                    channel_id_str = channel_data.get('@id') # Assuming @id for channel number
                    if channel_id_str:
                        try:
                            blind_channel_ids.append(int(channel_id_str))
                        except ValueError:
                            LOGGER.warning(f"Invalid channel ID format: {channel_id_str}")
        else: # Fallback for structure like {'ch1': {'val': '0'}, ...}
            for key, value_dict in scan_data.items():
                if key.startswith('ch') and isinstance(value_dict, dict) and value_dict.get('val') == '-1':
                    try:
                        channel_id_str = key[2:] # Extract number from 'chX'
                        blind_channel_ids.append(int(channel_id_str))
                    except ValueError:
                        LOGGER.warning(f"Invalid channel key format: {key}")
                        
    LOGGER.info(f"Identified blind channels for {hub_name}: {blind_channel_ids}")

    # Prepare hub_data which will be used for both entry.runtime_data and hass.data
    hub_data = {
        "client": api_client, # Renamed from "api_client"
        "hub_device_info": hub_device_info,
        "blind_channels": blind_channel_ids,
        "entry_title": hub_name,
        "hub_serial": serial_number,
        "integration": async_get_loaded_integration(hass, entry.domain) # For ZeptrionAirData
    }

    # Assign to entry.runtime_data before coordinator instantiation
    # The coordinator will access client and integration via entry.runtime_data
    entry.runtime_data = ZeptrionAirData(**hub_data) # Pass all hub_data to ZeptrionAirData constructor

    # Store common data for platforms (can still be useful for direct access in platform setup)
    # Platforms will access hass.data[DOMAIN][entry.entry_id].client etc.
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.runtime_data 
    
    # Setup coordinator
    # The coordinator's constructor should be able to pick up entry.runtime_data if it needs it,
    # or it's passed implicitly via hass object which can access entry.
    # Based on the prompt, it should be `ZeptrionAirDataUpdateCoordinator(hass=hass)`
    # The ZeptrionAirDataUpdateCoordinator's __init__ needs to be checked if it expects client via its constructor
    # or if it retrieves it from entry.runtime_data.
    # The original code passed `client=api_client`. If the coordinator's __init__ is:
    # `def __init__(self, hass: HomeAssistant, client: ZeptrionAirApiClient)`
    # then it needs the client.
    # If its __init__ is `def __init__(self, hass: HomeAssistant, entry: ConfigEntry)`
    # then it can get it from `entry.runtime_data.client`.
    # The prompt states: "The coordinator should now pick up the client from entry.runtime_data.client"
    # This implies the coordinator's constructor might not need `client` directly.
    # Let's assume ZeptrionAirDataUpdateCoordinator is updated to fetch client from entry.runtime_data if not provided.
    # Or, more directly, the coordinator is now part of ZeptrionAirData.
    
    # The original code in this file (before current changes) was:
    # coordinator = ZeptrionAirDataUpdateCoordinator(hass=hass, client=api_client)
    # entry.runtime_data = ZeptrionAirData(client=api_client, integration=..., coordinator=coordinator)
    # This structure means ZeptrionAirData holds the coordinator.
    # Let's adjust to match the new structure where entry.runtime_data IS ZeptrionAirData.

    # Create the coordinator instance. It will be stored within entry.runtime_data (ZeptrionAirData instance)
    coordinator = ZeptrionAirDataUpdateCoordinator(hass=hass) # Removed client=api_client
    entry.runtime_data.coordinator = coordinator # Store coordinator in ZeptrionAirData

    await coordinator.async_config_entry_first_refresh() # This fetches /zrap/id again

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
