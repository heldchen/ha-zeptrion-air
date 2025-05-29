"""
Custom integration to integrate Zeptrion Air devices with Home Assistant.

For more details about this integration, please refer to
https://github.com/alternize/ha-zeptrion-air-integration
"""

from __future__ import annotations

import logging
import re 
from typing import TYPE_CHECKING, Any, cast # Added Any, cast

from homeassistant.config_entries import ConfigEntry # For entry type hint
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant # For hass type hint
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration, Integration # For integration_obj
from homeassistant.helpers import device_registry # For DeviceRegistry

from .api import (
    ZeptrionAirApiClient,
    ZeptrionAirApiClientError, # Added import
    ZeptrionAirApiClientCommunicationError, # Added import
)
from .coordinator import ZeptrionAirDataUpdateCoordinator
from .data import ZeptrionAirData

from .const import DOMAIN, LOGGER, CONF_HOSTNAME, PLATFORMS as ZEPTRION_PLATFORMS

if TYPE_CHECKING: # Keep this for HomeAssistant, but ZeptrionAirConfigEntry is not used
    pass
    # from .data import ZeptrionAirConfigEntry # Not using this


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry, # Using ConfigEntry as ZeptrionAirConfigEntry not defined
) -> bool:
    """Set up the Zeptrion Air Hub from a config entry."""

    # Assuming CONF_HOSTNAME is guaranteed to be str by config flow
    hostname: str = entry.data[CONF_HOSTNAME] 
    api_client: ZeptrionAirApiClient = ZeptrionAirApiClient(hostname=hostname, session=async_get_clientsession(hass))

    # Initialize Coordinator and runtime_data earlier
    # Pass the api_client directly to the coordinator
    coordinator: ZeptrionAirDataUpdateCoordinator = ZeptrionAirDataUpdateCoordinator(hass=hass, client=api_client)
    integration_obj: Integration = async_get_loaded_integration(hass, entry.domain)
    
    entry.runtime_data = ZeptrionAirData(
        client=api_client,
        coordinator=coordinator,
        integration=integration_obj
    )
    coordinator.config_entry = entry

    try:
        # First refresh is no longer needed here, coordinator will fetch on its schedule
        # We need to perform an initial data fetch to get device_id for setup
        # This is a one-time fetch; subsequent updates are handled by the coordinator's schedule
        device_data_api = await api_client.async_get_device_identification() # Use api_client directly for initial fetch

        if not device_data_api:
            LOGGER.error(f"Failed to fetch initial device identification data for {hostname} using api_client.")
            entry.runtime_data = None # Clear runtime_data on failure
            return False

        # Fetch initial RSSI - supplemental, non-critical for setup to proceed
        rssi_value = None # Default to None
        try:
            rssi_value = await api_client.async_get_rssi()
            LOGGER.debug(f"Successfully fetched initial RSSI for {hostname}: {rssi_value}")
        except ZeptrionAirApiClientCommunicationError as e:
            LOGGER.warning(f"Initial RSSI fetch failed (communication error) for {hostname}: {e}. Will rely on coordinator updates.")
        except ZeptrionAirApiClientError as e:
            LOGGER.warning(f"Initial RSSI fetch failed (API error) for {hostname}: {e}. Will rely on coordinator updates.")
        except Exception as e:
            LOGGER.error(f"Unexpected error during initial RSSI fetch for {hostname}: {e}. Will rely on coordinator updates.")
        
        # Add rssi_dbm to the device_data_api dictionary.
        # device_data_api is confirmed to be a dictionary if we reached this point.
        device_data_api['rssi_dbm'] = rssi_value
        
        # Store the initially fetched data (now including RSSI) in the coordinator
        if coordinator.data is None:
            coordinator.data = device_data_api.copy()
            # Note: If coordinator.data could already exist and we want to update it,
            # this simple assignment might not be enough. However, given the current flow,
            # coordinator.data is typically None at this stage of initial setup.

        # Fetch channel descriptions directly, this is a one-off setup task
        channel_des_data: dict[str, Any] = await api_client.async_get_channel_descriptions()
        LOGGER.debug(f"Full /zrap/chdes response for {hostname}: {channel_des_data}")

    except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
        # This will catch errors from api_client.async_get_device_identification() or async_get_channel_descriptions()
        LOGGER.error(f"Failed to communicate with Zeptrion Air device {hostname} during setup: {e}")
        entry.runtime_data = None # Clear runtime_data on failure
        return False
    # UpdateFailed is no longer expected here from async_config_entry_first_refresh
    except Exception as e:
        LOGGER.error(f"Unexpected error setting up Zeptrion Air device {hostname}: {e}")
        entry.runtime_data = None # Clear runtime_data on failure
        return False

    zrap_id_data: dict[str, Any] = device_data_api.get('id', {}) # device_data_api is now checked for None
    if not zrap_id_data:
        LOGGER.error(f"Failed to get valid device identification from {hostname} (empty 'id' field)")
        return False

    serial_number_maybe: str | None = zrap_id_data.get('sn')
    if not serial_number_maybe: 
        LOGGER.error(f"Could not determine serial number for {hostname} from API. Cannot set up device.")
        return False
    serial_number: str = serial_number_maybe # Now str
        
    if entry.unique_id and entry.unique_id != serial_number:
        LOGGER.warning(
            f"Config entry's unique ID ('{entry.unique_id}') does not match the device's current serial "
            f"number ('{serial_number}') obtained from the API. The integration will use the API-provided "
            f"serial number ('{serial_number}') for device registration and identification. This might "
            f"occur if the device hardware was changed or for older configurations."
        )

    model: str = zrap_id_data.get('type', 'Zeptrion Air Device')
    hub_name: str = entry.title or hostname.replace('.local', '') 

    # Type for hub_device_info elements
    hub_device_info_identifiers: set[tuple[str, str]] = {(DOMAIN, serial_number)}
    hub_device_info_connections: set[tuple[str, str]] = {(device_registry.CONNECTION_UPNP, hostname)}
    hub_device_info_sw_version: str | None = zrap_id_data.get('sw')

    hub_device_info: dict[str, Any] = { # More specific: dict[str, str | set[tuple[str, str]] | None]
        "identifiers": hub_device_info_identifiers,
        "name": hub_name, # str
        "manufacturer": "Feller AG", # str
        "model": model, # str
        "connections": hub_device_info_connections,
        "sw_version": hub_device_info_sw_version,
    }
    
    LOGGER.debug(f"Constructed hub_device_info for {serial_number}: {hub_device_info}")

    registry: device_registry.DeviceRegistry = device_registry.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        **hub_device_info 
    )

    identified_channels: list[dict[str, Any]] = []
    
    chdes_root: dict[str, Any] = channel_des_data.get('chdes', {}) 
    LOGGER.debug(f"Extracted 'chdes' data for {hub_name}: {chdes_root}")

    raw_channels_from_chdes: list[dict[str, Any]] = []
    if chdes_root:
        raw_channels_data: list[dict[str, Any]] | dict[str, Any] | None = chdes_root.get('ch')
        if isinstance(raw_channels_data, list):
            raw_channels_from_chdes = raw_channels_data
        elif isinstance(raw_channels_data, dict):
            raw_channels_from_chdes = [raw_channels_data] 
        elif raw_channels_data is None: # Handle {'chdes': {'ch1': ..., 'ch2': ...}}
            for key, value_dict in chdes_root.items():
                if key.startswith('ch') and isinstance(value_dict, dict):
                    value_dict_copy = value_dict.copy() 
                    if 'id' not in value_dict_copy and '@id' not in value_dict_copy : 
                         value_dict_copy['id_from_key'] = key[2:] 
                    raw_channels_from_chdes.append(value_dict_copy)
    
    LOGGER.debug(f"Raw channels list from /zrap/chdes for {hub_name}: {raw_channels_from_chdes}")

    for channel_data in raw_channels_from_chdes: # channel_data is dict[str, Any]
        channel_id_str: str | None = channel_data.get('@id', channel_data.get('id', channel_data.get('id_from_key')))
        cat_str: str | None = channel_data.get('cat', channel_data.get('@cat')) 
        name: str | None = channel_data.get('name')
        friendly_name: str | None = channel_data.get('group') 
        icon: str | None = channel_data.get('icon')
        
        channel_name: str | None = friendly_name or name 

        if channel_id_str is None or cat_str is None:
            LOGGER.debug(f"Ignoring channel, missing id or cat: ID='{channel_id_str}', Cat='{cat_str}', Data='{channel_data}'")
            continue

        try:
            channel_id_int: int = int(channel_id_str)
            cat_int: int = int(cat_str)
        except ValueError:
            LOGGER.warning(f"Could not parse channel ID '{channel_id_str}' or category '{cat_str}' to int. Skipping.")
            continue
        
        # channel_info: dict[str, int | str | None]
        # More specific: {"id": int, "cat": int, "name": str|None, "icon": str|None, 
        #                "api_group": str|None, "api_name": str|None, "device_type": str, "entity_base_name": str}
        channel_info: dict[str, Any] = {
            "id": channel_id_int,
            "cat": cat_int,
            "name": channel_name, 
            "icon": icon,
            "api_group": friendly_name, 
            "api_name": name,           
        }

        resolved_entity_name: str
        if friendly_name and friendly_name.strip():
            if name and name.strip():
                resolved_entity_name = f"{hub_name} {friendly_name.strip()} - {name.strip()}"
            else:
                resolved_entity_name = f"{hub_name} {friendly_name.strip()}"
        elif name and name.strip():
            resolved_entity_name = f"{hub_name} {name.strip()}"
        else:
            resolved_entity_name = f"{hub_name} Channel {channel_id_int}"
        
        channel_info["entity_base_name"] = resolved_entity_name
        LOGGER.debug(f"Constructed entity_base_name for ch {channel_id_int}: '{resolved_entity_name}' from api_group: '{friendly_name}', api_name: '{name}'")

        device_type_str: str = ""
        if cat_int == 1: 
            device_type_str = "light_switch"
        elif cat_int == 3: 
            device_type_str = "light_dimmer"
        elif cat_int == 5 or cat_int == 6: 
            device_type_str = "cover"
        
        if device_type_str:
            channel_info["device_type"] = device_type_str
            identified_channels.append(channel_info)
            LOGGER.debug(f"Identified usable channel for {hub_name}: {channel_info}")
        else:
            LOGGER.debug(f"Ignoring channel id {channel_id_int} with cat '{cat_int}' (name: '{channel_name}') for {hub_name} as it's not a recognized device type.")
            continue 

    LOGGER.info(f"Final identified usable channels for {hub_name}: {identified_channels}")

    integration_obj: Integration = async_get_loaded_integration(hass, entry.domain) # Already moved up
    
    # coordinator is already initialized and entry.runtime_data is set.
    # zeptrion_air_data_for_runtime variable is no longer needed as entry.runtime_data is set directly.

    platform_setup_data: dict[str, Any] = {
        "hub_device_info": hub_device_info, 
        "identified_channels": identified_channels, 
        "entry_title": hub_name, 
        "hub_serial": serial_number, 
        "coordinator": coordinator # coordinator is already initialized
    }
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = platform_setup_data
    
    # Removed: await coordinator.async_config_entry_first_refresh()

    LOGGER.debug("Forwarding setup to platforms: %s", ZEPTRION_PLATFORMS)
    LOGGER.debug("Attempting to forward entry setups for %s.", entry.entry_id)
    await hass.config_entries.async_forward_entry_setups(entry, ZEPTRION_PLATFORMS)
    LOGGER.debug("Successfully forwarded entry setups for %s.", entry.entry_id)
    
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    LOGGER.info("Zeptrion Air integration setup successfully completed for %s.", entry.title)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry, # Using ConfigEntry
) -> bool:
    """Handle removal of an entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, ZEPTRION_PLATFORMS)
    if unload_ok:
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id)
        if hasattr(entry, 'runtime_data') and isinstance(entry.runtime_data, ZeptrionAirData):
            entry.runtime_data = None 
    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry, # Using ConfigEntry
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

