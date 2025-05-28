from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN # Assuming DOMAIN is defined in const.py
# We'll need access to the ZeptrionAirApiClient from the entry's runtime_data
# and the channel details passed during setup.

_LOGGER = logging.getLogger(__name__)

# Define constants for sensor types to avoid magic strings
SENSOR_TYPE_NAME: str = "name"
SENSOR_TYPE_GROUP: str = "group"
SENSOR_TYPE_ICON_ID: str = "icon_id" # From the API it's <icon>, let's call it icon_id

SENSOR_TYPES_TO_REGISTER: list[str] = [SENSOR_TYPE_NAME, SENSOR_TYPE_GROUP, SENSOR_TYPE_ICON_ID]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry, # Not using ZeptrionAirConfigEntry as it's not defined in this context
    async_add_entities: AddEntitiesCallback,
) -> None:
    '''Set up Zeptrion Air sensor entities from a config entry.'''
    platform_data: dict[str, Any] | None = hass.data[DOMAIN].get(entry.entry_id)
    if not platform_data:
        _LOGGER.error(f"sensor.py async_setup_entry: No platform_data found for entry ID {entry.entry_id}")
        return

    identified_channels_list: list[dict[str, Any]] = platform_data.get("identified_channels", [])
    hub_serial: str | None = platform_data.get("hub_serial")
    # main_hub_device_info is needed if we want to link sensors directly to hub,
    # but it's better to link them to channel devices.

    if not hub_serial: # Guard makes hub_serial effectively str after this
        _LOGGER.error("sensor.py async_setup_entry: Hub serial not found in platform_data.")
        return

    new_entities: list[ZeptrionAirChannelSensor] = []
    for channel_info_dict in identified_channels_list:
        channel_id: int | None = channel_info_dict.get('id')
        # channel_cat = channel_info_dict.get('cat') # Not strictly needed for sensors if they are for any channel
        
        # Ensure channel_id is valid before proceeding
        if channel_id is None: # Guard makes channel_id effectively int after this for sensor creation
            _LOGGER.debug(f"sensor.py: Skipping channel due to missing id: {channel_info_dict}")
            continue

        # Get the base device info for the channel (created by cover.py or light.py etc.)
        # This assumes that other platforms (like cover) have already created a device for the channel.
        # The device_info for the channel itself.
        channel_device_identifier: tuple[str, str] = (DOMAIN, f"{hub_serial}_ch{channel_id}")

        # Channel details from the API
        channel_api_name: str = channel_info_dict.get("name", "")
        channel_api_group: str = channel_info_dict.get("group", "")
        channel_api_icon_id: str = channel_info_dict.get("icon", "") # This is the icon ID like "1443_Auf_Ab"

        details_map: dict[str, dict[str, str]] = {
            SENSOR_TYPE_NAME: {"name": "Name", "value": channel_api_name, "icon": "mdi:information-outline"},
            SENSOR_TYPE_GROUP: {"name": "Group", "value": channel_api_group, "icon": "mdi:folder-outline"},
            SENSOR_TYPE_ICON_ID: {"name": "Icon ID", "value": channel_api_icon_id, "icon": "mdi:image-outline"},
        }

        for sensor_type, info_data in details_map.items(): # Renamed info to info_data
            if info_data["value"] is not None: # Only create sensor if detail exists
                new_entities.append(
                    ZeptrionAirChannelSensor(
                        config_entry_unique_id=str(entry.unique_id or entry.entry_id), # Ensure str
                        hub_serial=hub_serial, # hub_serial is str here
                        channel_id=channel_id, # channel_id is int here
                        channel_device_identifier=channel_device_identifier, 
                        sensor_type=sensor_type,
                        sensor_name_suffix=info_data["name"],
                        initial_value=info_data["value"],
                        icon_val=info_data["icon"],
                        # Base name for the channel, e.g., "Living Room Blind CH1"
                        channel_base_name=str(channel_info_dict.get("entity_base_name", f"Channel {channel_id}")) # Ensure str
                    )
                )

    if new_entities:
        _LOGGER.info(f"Adding {len(new_entities)} Zeptrion Air sensor entities.")
        async_add_entities(new_entities)
    else:
        _LOGGER.info("No Zeptrion Air sensor entities to add.")


class ZeptrionAirChannelSensor(SensorEntity):
    '''Representation of a Zeptrion Air Channel Sensor.'''

    _attr_entity_registry_enabled_default = False  # Disabled by default
    _attr_should_poll = False  # Data is pushed from coordinator or setup once

    def __init__(
        self,
        config_entry_unique_id: str,
        hub_serial: str,
        channel_id: int,
        channel_device_identifier: tuple[str, str],
        sensor_type: str,
        sensor_name_suffix: str,
        initial_value: str,
        icon_val: str | None,
        channel_base_name: str
    ) -> None:
        '''Initialize the sensor.'''
        self._hub_serial: str = hub_serial
        self._channel_id: int = channel_id
        self._sensor_type: str = sensor_type
        self._attr_native_value: str = initial_value
        self._attr_icon: str | None = icon_val

        # Construct the name: e.g., "Living Room Blind CH1 Name"
        self._attr_name = f"{channel_base_name} {sensor_name_suffix}"
        
        # Construct unique ID: e.g., zapp-serial_ch1_name
        self._attr_unique_id = f"{self._hub_serial}_ch{self._channel_id}_{self._sensor_type}"

        # Device info to link this sensor to its respective channel device
        # The channel device itself is linked to the main hub device.
        self._attr_device_info = DeviceInfo(
            identifiers={channel_device_identifier}, 
            # No name, model, manufacturer here as it should inherit from the channel device.
            # This effectively says "this sensor is part of the device identified by channel_device_identifier"
            # The channel device (e.g., cover entity) should have the full via_device=hub_identifier setup.
        )
        
        _LOGGER.debug(
            f"Sensor initialized: {self._attr_name} (Unique ID: {self._attr_unique_id}) for channel {self._channel_id}"
        )

    @property
    def available(self) -> bool:
        # Assuming data is fetched once at setup, so sensor is always available
        # unless the parent device (hub) becomes unavailable.
        # This could be enhanced if sensors were to update via a coordinator.
        return True

    # No update method needed if _attr_should_poll = False and data is set at init.
    # If these sensors were to be updated from a central coordinator:
    # def _handle_coordinator_update(self) -> None:
    #     '''Handle updated data from the coordinator.'''
    #     # Example: self._attr_native_value = self.coordinator.data.get_channel_detail(...)
    #     self.async_write_ha_state()

    # async def async_added_to_hass(self) -> None:
    #     '''Run when this Entity has been added to HA.'''
    #     if self.coordinator: # If using a coordinator
    #         self.async_on_remove(
    #             self.coordinator.async_add_listener(self._handle_coordinator_update)
    #         )
