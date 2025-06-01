"""
Custom integration to integrate Zeptrion Air devices with Home Assistant.

For more details about this integration, please refer to
https://github.com/alternize/ha-zeptrion-air-integration
"""

from __future__ import annotations

import logging
import re 
from typing import TYPE_CHECKING, Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration, Integration
from homeassistant.helpers import device_registry
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .api import (
    ZeptrionAirApiClient,
    ZeptrionAirApiClientError,
    ZeptrionAirApiClientCommunicationError,
)
from .coordinator import ZeptrionAirDataUpdateCoordinator
from .data import ZeptrionAirData
from .websocket_listener import ZeptrionAirWebsocketListener

from .frontend import async_setup_frontend

from .const import DOMAIN, LOGGER, CONF_HOSTNAME, PLATFORMS as ZEPTRION_PLATFORMS

if TYPE_CHECKING:
    pass

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up the Zeptrion Air Hub from a config entry."""

    hostname: str = entry.data[CONF_HOSTNAME] 
    api_client: ZeptrionAirApiClient = ZeptrionAirApiClient(hostname=hostname, session=async_get_clientsession(hass))

    coordinator: ZeptrionAirDataUpdateCoordinator = ZeptrionAirDataUpdateCoordinator(hass=hass, client=api_client)
    integration_obj: Integration = async_get_loaded_integration(hass, entry.domain)
    
    entry.runtime_data = ZeptrionAirData(
        client=api_client,
        coordinator=coordinator,
        integration=integration_obj
    )
    coordinator.config_entry = entry

    try:
        # We need to perform an initial data fetch to get device_id for setup
        # This is a one-time fetch; subsequent updates are handled by the coordinator's schedule
        device_data_api = await api_client.async_get_device_identification() # Use api_client directly for initial fetch

        if not device_data_api:
            LOGGER.error(f"Failed to fetch initial device identification data for {hostname} using api_client.")
            entry.runtime_data = None
            return False

        # Fetch initial RSSI - supplemental, non-critical for setup to proceed
        rssi_value = None
        try:
            rssi_value = await api_client.async_get_rssi()
            LOGGER.debug(f"Successfully fetched initial RSSI for {hostname}: {rssi_value}")
        except ZeptrionAirApiClientCommunicationError as e:
            LOGGER.warning(f"Initial RSSI fetch failed (communication error) for {hostname}: {e}. Will rely on coordinator updates.")
        except ZeptrionAirApiClientError as e:
            LOGGER.warning(f"Initial RSSI fetch failed (API error) for {hostname}: {e}. Will rely on coordinator updates.")
        except Exception as e:
            LOGGER.error(f"Unexpected error during initial RSSI fetch for {hostname}: {e}. Will rely on coordinator updates.")
        device_data_api['rssi_dbm'] = rssi_value
        
        # Store the initially fetched data (now including RSSI) in the coordinator
        if coordinator.data is None:
            coordinator.data = device_data_api.copy()

        # Fetch channel descriptions directly, this is a one-off setup task
        channel_des_data: dict[str, Any] = await api_client.async_get_channel_descriptions()
        LOGGER.debug(f"Full /zrap/chdes response for {hostname}: {channel_des_data}")

    except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
        LOGGER.error(f"Failed to communicate with Zeptrion Air device {hostname} during setup: {e}")
        entry.runtime_data = None
        return False
    except Exception as e:
        LOGGER.error(f"Unexpected error setting up Zeptrion Air device {hostname}: {e}")
        entry.runtime_data = None
        return False

    zrap_id_data: dict[str, Any] = device_data_api.get('id', {})
    if not zrap_id_data:
        LOGGER.error(f"Failed to get valid device identification from {hostname} (empty 'id' field)")
        return False

    serial_number_maybe: str | None = zrap_id_data.get('sn')
    if not serial_number_maybe: 
        LOGGER.error(f"Could not determine serial number for {hostname} from API. Cannot set up device.")
        return False
    serial_number: str = serial_number_maybe
        
    if entry.unique_id and entry.unique_id != serial_number:
        LOGGER.warning(
            f"Config entry's unique ID ('{entry.unique_id}') does not match the device's current serial "
            f"number ('{serial_number}') obtained from the API. The integration will use the API-provided "
            f"serial number ('{serial_number}') for device registration and identification. This might "
            f"occur if the device hardware was changed or for older configurations."
        )

    model: str = zrap_id_data.get('type', 'Zeptrion Air Device')
    hub_name: str = entry.title or hostname.replace('.local', '') 

    hub_device_info_identifiers: set[tuple[str, str]] = {(DOMAIN, serial_number)}
    hub_device_info_connections: set[tuple[str, str]] = {(device_registry.CONNECTION_UPNP, hostname)}
    hub_device_info_sw_version: str | None = zrap_id_data.get('sw')

    hub_device_info: dict[str, Any] = {
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

    current_runtime_data = entry.runtime_data
    if isinstance(current_runtime_data, ZeptrionAirData):
        if entry.unique_id:
            websocket_listener = ZeptrionAirWebsocketListener(hostname=hostname, hass_instance=hass, hub_unique_id=entry.unique_id)
            await websocket_listener.start()
            current_runtime_data.websocket_listener = websocket_listener
        else:
            LOGGER.error(f"[{hostname}] Cannot start WebSocket listener: entry.unique_id is not set. This is unexpected.")
            # Optionally, set current_runtime_data.websocket_listener to None or handle error
            current_runtime_data.websocket_listener = None # Ensure it's None if not started
        if current_runtime_data.websocket_listener: # Only proceed if listener was successfully created and started
            LOGGER.info(f"[{hostname}] WebSocket listener started and attached to runtime_data.")

            # Define and schedule the watchdog
            async def async_websocket_watchdog(now=None):
                """Check the websocket listener and restart if necessary."""
                # Ensure websocket_listener is not None before using it
                if current_runtime_data.websocket_listener:
                    LOGGER.debug(f"[{hostname}] Watchdog: Checking WebSocket listener status.")
                    if not current_runtime_data.websocket_listener.is_alive():
                        LOGGER.warning(f"[{hostname}] Watchdog: WebSocket listener found inactive. Attempting restart.")
                        try:
                            await current_runtime_data.websocket_listener.start()
                            LOGGER.info(f"[{hostname}] Watchdog: WebSocket listener restarted successfully.")
                        except Exception as e:
                            LOGGER.error(f"[{hostname}] Watchdog: Error restarting WebSocket listener: {e}")
                    else:
                        LOGGER.debug(f"[{hostname}] Watchdog: WebSocket listener is alive.")
                else:
                    LOGGER.debug(f"[{hostname}] Watchdog: WebSocket listener is None, skipping check.")


            # Schedule the watchdog to run every 5 minutes
            cancel_watchdog_callback = async_track_time_interval(
                hass,
                async_websocket_watchdog,
                timedelta(minutes=5)
            )
            current_runtime_data.websocket_watchdog_cancel_callback = cancel_watchdog_callback
            LOGGER.info(f"[{hostname}] WebSocket listener watchdog scheduled every 5 minutes.")
        else:
            LOGGER.info(f"[{hostname}] WebSocket listener was not started (e.g. missing unique_id). Watchdog not scheduled.")

    else:
        # This block handles the case where current_runtime_data is not a ZeptrionAirData instance.
        # It's less likely to have a 'websocket_listener' local variable here that needs stopping
        # because the listener's lifecycle is tied to current_runtime_data being the correct type.
        LOGGER.error(f"[{hostname}] Cannot start WebSocket listener or watchdog: runtime_data is not a ZeptrionAirData instance.")
        # For now, we log the error and proceed without WS, as core functionality might still work.
        # Consider returning False if WS is essential:
        # return False

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
                # resolved_entity_name = f"{hub_name} {friendly_name.strip()} - {name.strip()}"
                resolved_entity_name = f"{friendly_name.strip()} - {name.strip()}"
            else:
                # resolved_entity_name = f"{hub_name} {friendly_name.strip()}"
                resolved_entity_name = f"{friendly_name.strip()}"
        elif name and name.strip():
            # resolved_entity_name = f"{hub_name} {name.strip()}"
            resolved_entity_name = f"{name.strip()}"
        else:
            # resolved_entity_name = f"{hub_name} Channel {channel_id_int}"
            resolved_entity_name = f"Channel {channel_id_int}"
        
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

    integration_obj: Integration = async_get_loaded_integration(hass, entry.domain)
    
    platform_setup_data: dict[str, Any] = {
        "hub_device_info": hub_device_info, 
        "identified_channels": identified_channels, 
        "entry_title": hub_name, 
        "hub_serial": serial_number, 
        "coordinator": coordinator
    }
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = platform_setup_data
    
    # Set up frontend components
    
    await async_setup_frontend(hass, entry)
    
    # Wrapping up the setup

    LOGGER.debug("Forwarding setup to platforms: %s", ZEPTRION_PLATFORMS)
    LOGGER.debug("Attempting to forward entry setups for %s.", entry.entry_id)
    await hass.config_entries.async_forward_entry_setups(entry, ZEPTRION_PLATFORMS)
    LOGGER.debug("Successfully forwarded entry setups for %s.", entry.entry_id)
    
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    LOGGER.info("Zeptrion Air integration setup successfully completed for %s.", entry.title)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    # Stop the websocket listener if it exists
    if entry.runtime_data and isinstance(entry.runtime_data, ZeptrionAirData):
        # Stop the watchdog first
        if entry.runtime_data.websocket_watchdog_cancel_callback:
            LOGGER.debug(f"[{entry.data.get(CONF_HOSTNAME, 'Unknown Host')}] Unloading: Cancelling websocket watchdog.")
            entry.runtime_data.websocket_watchdog_cancel_callback()
            entry.runtime_data.websocket_watchdog_cancel_callback = None # Clear the stored callback

        # Then stop the websocket listener
        if entry.runtime_data.websocket_listener:
            LOGGER.debug(f"[{entry.data.get(CONF_HOSTNAME, 'Unknown Host')}] Unloading: Stopping websocket listener.")
            await entry.runtime_data.websocket_listener.stop()
            entry.runtime_data.websocket_listener = None

    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, ZEPTRION_PLATFORMS)
    if unload_ok:
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id)
        # Ensure runtime_data is cleared, especially if it was ZeptrionAirData
        if hasattr(entry, 'runtime_data') and entry.runtime_data is not None:
            if isinstance(entry.runtime_data, ZeptrionAirData):
                LOGGER.debug(f"[{entry.data.get(CONF_HOSTNAME, 'Unknown Host')}] Clearing ZeptrionAirData from entry.runtime_data.")
            else:
                LOGGER.debug(f"[{entry.data.get(CONF_HOSTNAME, 'Unknown Host')}] Clearing non-ZeptrionAirData from entry.runtime_data.")
            entry.runtime_data = None 
    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

