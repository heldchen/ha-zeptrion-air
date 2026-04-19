from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .data import ZeptrionAirConfigEntry
from .entity import ZeptrionAirEntity

_LOGGER = logging.getLogger(__name__)

# Define constants for sensor types to avoid magic strings
SENSOR_TYPE_NAME: str = "name"
SENSOR_TYPE_GROUP: str = "group"
SENSOR_TYPE_ICON_ID: str = "icon_id" # From the API it's <icon>, let's call it icon_id

SENSOR_TYPES_TO_REGISTER: list[str] = [SENSOR_TYPE_NAME, SENSOR_TYPE_GROUP, SENSOR_TYPE_ICON_ID]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZeptrionAirConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    '''Set up Zeptrion Air sensor entities from a config entry.'''
    data = entry.runtime_data
    identified_channels_list = data.identified_channels
    hub_serial = data.hub_serial

    # Prepare a list to hold all sensor entities (channel sensors + RSSI sensor)
    # Ensure the list type can accommodate both ZeptrionAirChannelSensor and ZeptrionAirRssiSensor.
    # Using SensorEntity as a common base type for the list.
    new_entities: list[SensorEntity] = []

    for channel_info_dict in identified_channels_list:
        channel_id: int | None = channel_info_dict.get('id')
        
        # Ensure channel_id is valid before proceeding
        if channel_id is None:
            _LOGGER.debug(f"Skipping channel due to missing id: {channel_info_dict}")
            continue

        # Channel details from the API
        channel_api_name: str = channel_info_dict.get("name", "")
        channel_api_group: str = channel_info_dict.get("group", "")
        channel_api_icon_id: str = channel_info_dict.get("icon", "") # This is the icon ID like "1443_Auf_Ab"

        details_map: dict[str, dict[str, str]] = {
            SENSOR_TYPE_NAME: {"name": "Name", "value": channel_api_name, "icon": "mdi:information-outline", "slug": "name"},
            SENSOR_TYPE_GROUP: {"name": "Group", "value": channel_api_group, "icon": "mdi:folder-outline", "slug": "group"},
            SENSOR_TYPE_ICON_ID: {"name": "Icon ID", "value": channel_api_icon_id, "icon": "mdi:image-outline", "slug": "icon_id"},
        }

        for sensor_type, info_data in details_map.items():
            if info_data["value"] is not None:
                new_entities.append(
                    ZeptrionAirChannelSensor(
                        entry=entry,
                        channel_id=channel_id,
                        sensor_type_suffix=info_data["name"],
                        sensor_type_slug=info_data["slug"],
                        initial_value=info_data["value"],
                        icon_val=info_data["icon"],
                    )
                )
    
    # --- Add ZeptrionAirRssiSensor ---
    new_entities.append(ZeptrionAirRssiSensor(entry))

    if new_entities:
        _LOGGER.info(f"Adding {len(new_entities)} Zeptrion Air sensor entities in total.")
        async_add_entities(new_entities)
    else:
        _LOGGER.info("No Zeptrion Air sensor entities to add (neither channel nor RSSI).")


class ZeptrionAirChannelSensor(ZeptrionAirEntity, SensorEntity):
    '''Representation of a Zeptrion Air Channel Sensor.'''

    _attr_entity_registry_enabled_default = False
    _attr_should_poll = False  # Data is pushed from coordinator or setup once

    def __init__(
        self,
        entry: ZeptrionAirConfigEntry,
        channel_id: int,
        sensor_type_suffix: str,
        sensor_type_slug: str,
        initial_value: str,
        icon_val: str | None,
    ) -> None:
        '''Initialize the sensor.'''
        super().__init__(entry.runtime_data.coordinator, channel_id)
        self._channel_id = channel_id
        self._attr_native_value = initial_value
        self._attr_icon = icon_val

        self._attr_name = sensor_type_suffix
        self._attr_unique_id = f"{self._attr_unique_id}_{sensor_type_slug}"
        
        _LOGGER.debug(
            "Sensor initialized for channel %s",
            self._channel_id
        )
        _LOGGER.debug("  Friendly name: '%s'", self._attr_name)
        _LOGGER.debug("  Unique ID: '%s'", self._attr_unique_id)
        

    @property
    def available(self) -> bool:
        # Assuming data is fetched once at setup, so sensor is always available
        # unless the parent device (hub) becomes unavailable.
        # This could be enhanced if sensors were to update via a coordinator.
        return True

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT # Added import

class ZeptrionAirRssiSensor(ZeptrionAirEntity, SensorEntity):
    """Representation of a Zeptrion Air RSSI Sensor for the Hub."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        entry: ZeptrionAirConfigEntry,
    ) -> None:
        """Initialize the RSSI sensor."""
        super().__init__(entry.runtime_data.coordinator)
        
        self._attr_name = "Wi-Fi Signal"
        self._attr_unique_id = f"{self._attr_unique_id}_rssi"

        _LOGGER.debug(
            "RSSI Sensor initialized for hub_serial '%s'",
            entry.runtime_data.hub_serial
        )
        
        # Set initial state:
        # The CoordinatorEntity base class calls _handle_coordinator_update
        # when the coordinator has data and the entity is added to hass.
        # Calling it here ensures initial state if data is already present
        # before listener registration. Guard with self.coordinator.data check.
        if self.coordinator.data:
            self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is None:
            _LOGGER.debug(f"RSSI Sensor ({self.unique_id}): Coordinator data is None.")
            self._attr_native_value = None
        elif 'rssi_dbm' not in self.coordinator.data:
            _LOGGER.debug(f"RSSI Sensor ({self.unique_id}): 'rssi_dbm' key not found in coordinator data. Current coordinator data: {self.coordinator.data}")
            self._attr_native_value = None
        else:
            rssi = self.coordinator.data['rssi_dbm']
            if rssi is None:
                _LOGGER.debug(f"RSSI Sensor ({self.unique_id}): 'rssi_dbm' value is None in coordinator data.")
                self._attr_native_value = None
            else:
                try:
                    self._attr_native_value = int(rssi)
                    _LOGGER.debug(f"RSSI Sensor ({self.unique_id}): Updated native_value to {self._attr_native_value}.")
                except (ValueError, TypeError) as e:
                    _LOGGER.warning(f"RSSI Sensor ({self.unique_id}): Could not parse RSSI value '{rssi}' as int: {e}")
                    self._attr_native_value = None
        
        if self.hass:
            self.async_write_ha_state()

