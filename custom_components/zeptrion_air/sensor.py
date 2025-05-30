from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Define constants for sensor types to avoid magic strings
SENSOR_TYPE_NAME: str = "name"
SENSOR_TYPE_GROUP: str = "group"
SENSOR_TYPE_ICON_ID: str = "icon_id" # From the API it's <icon>, let's call it icon_id

SENSOR_TYPES_TO_REGISTER: list[str] = [SENSOR_TYPE_NAME, SENSOR_TYPE_GROUP, SENSOR_TYPE_ICON_ID]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    '''Set up Zeptrion Air sensor entities from a config entry.'''
    platform_data: dict[str, Any] | None = hass.data[DOMAIN].get(entry.entry_id)
    if not platform_data:
        _LOGGER.error(f"sensor.py async_setup_entry: No platform_data found for entry ID {entry.entry_id}")
        return

    identified_channels_list: list[dict[str, Any]] = platform_data.get("identified_channels", [])
    hub_serial: str | None = platform_data.get("hub_serial")
    hub_entry_title: str = platform_data.get("entry_title", "Zeptrion Air Hub")
    # main_hub_device_info is needed if we want to link sensors directly to hub,
    # but it's better to link them to channel devices.

    if not hub_serial: # Guard makes hub_serial effectively str after this
        _LOGGER.error("sensor.py async_setup_entry: Hub serial not found in platform_data.")
        return
    
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

        # Get the base device info for the channel (created by cover.py or light.py etc.)
        # This assumes that other platforms (like cover) have already created a device for the channel.
        # The device_info for the channel itself.
        channel_device_identifier: tuple[str, str] = (DOMAIN, f"{hub_serial}_ch{channel_id}")

        # Channel details from the API
        channel_api_name: str = channel_info_dict.get("name", "")
        channel_api_group: str = channel_info_dict.get("group", "")
        channel_api_icon_id: str = channel_info_dict.get("icon", "") # This is the icon ID like "1443_Auf_Ab"

        # Get the entity_base_name for display purposes (friendly name)
        parent_device_name_maybe: str | None = channel_info_dict.get("entity_base_name")
        parent_device_name: str = parent_device_name_maybe if parent_device_name_maybe is not None else f"{hub_entry_title} Channel {channel_id}"

        # Create a stable base slug for entity IDs (consistent regardless of friendly name changes)
        # This matches the pattern used in button.py
        entity_base_slug = parent_device_name.lower().replace(' ', '_').replace('-', '_').replace('.', '_').replace(':', '_')
        # Remove any double underscores and strip leading/trailing underscores
        entity_base_slug = '_'.join(filter(None, entity_base_slug.split('_')))

        details_map: dict[str, dict[str, str]] = {
            SENSOR_TYPE_NAME: {"name": "Name", "value": channel_api_name, "icon": "mdi:information-outline", "slug": "name"},
            SENSOR_TYPE_GROUP: {"name": "Group", "value": channel_api_group, "icon": "mdi:folder-outline", "slug": "group"},
            SENSOR_TYPE_ICON_ID: {"name": "Icon ID", "value": channel_api_icon_id, "icon": "mdi:image-outline", "slug": "icon_id"},
        }

        for sensor_type, info_data in details_map.items():
            if info_data["value"] is not None:
                new_entities.append(
                    ZeptrionAirChannelSensor(
                        config_entry_unique_id=str(entry.unique_id or entry.entry_id),
                        hub_serial=hub_serial,
                        channel_id=channel_id,
                        channel_device_identifier=channel_device_identifier, 
                        sensor_type=sensor_type,
                        sensor_name_suffix=info_data["name"],
                        sensor_type_slug=info_data["slug"],
                        initial_value=info_data["value"],
                        icon_val=info_data["icon"],
                        # Base name for the channel, e.g., "Living Room Blind CH1" (friendly name)
                        channel_base_name=parent_device_name,
                        # Stable base slug for entity ID generation
                        entity_base_slug=entity_base_slug
                    )
                )
    
    # --- Add ZeptrionAirRssiSensor ---
    coordinator: ZeptrionAirDataUpdateCoordinator | None = platform_data.get("coordinator")
    hub_device_info: DeviceInfo | None = platform_data.get("hub_device_info")
    hub_name: str | None = platform_data.get("entry_title") # entry_title is usually the user-given name or default

    if coordinator and hub_device_info and hub_serial and hub_name:
        # Create stable hub slug for RSSI sensor entity ID
        hub_name_slug = hub_name.lower().replace(' ', '_').replace('-', '_').replace('.', '_').replace(':', '_')
        hub_name_slug = '_'.join(filter(None, hub_name_slug.split('_')))
        
        rssi_sensor = ZeptrionAirRssiSensor(
            coordinator=coordinator,
            hub_device_info=hub_device_info,
            hub_serial=hub_serial, # hub_serial is confirmed not None above
            hub_name=hub_name,
            hub_name_slug=hub_name_slug  # Add stable slug
        )
        new_entities.append(rssi_sensor)
        _LOGGER.info(f"Adding Zeptrion Air RSSI sensor for hub {hub_name} (Serial: {hub_serial})")
    else:
        missing_data_elements = []
        if not coordinator:
            missing_data_elements.append("coordinator")
        if not hub_device_info:
            missing_data_elements.append("hub_device_info")
        if not hub_name:
            missing_data_elements.append("hub_name (entry_title)")
        _LOGGER.error(
            f"Could not create RSSI sensor for hub {hub_serial} due to missing data: {', '.join(missing_data_elements)}."
        )

    if new_entities:
        _LOGGER.info(f"Adding {len(new_entities)} Zeptrion Air sensor entities in total.")
        async_add_entities(new_entities)
    else:
        _LOGGER.info("No Zeptrion Air sensor entities to add (neither channel nor RSSI).")


class ZeptrionAirChannelSensor(SensorEntity):
    '''Representation of a Zeptrion Air Channel Sensor.'''

    _attr_entity_registry_enabled_default = False
    _attr_should_poll = False  # Data is pushed from coordinator or setup once

    def __init__(
        self,
        config_entry_unique_id: str,
        hub_serial: str,
        channel_id: int,
        channel_device_identifier: tuple[str, str],
        sensor_type: str,
        sensor_name_suffix: str,
        sensor_type_slug: str,
        initial_value: str,
        icon_val: str | None,
        channel_base_name: str,
        entity_base_slug: str
    ) -> None:
        '''Initialize the sensor.'''
        self._hub_serial: str = hub_serial
        self._channel_id: int = channel_id
        self._sensor_type: str = sensor_type
        self._attr_native_value: str = initial_value
        self._attr_icon: str | None = icon_val

        self._attr_has_entity_name = True
        self._attr_name = f"{sensor_name_suffix}"
        self._attr_unique_id = f"zapp_{self._hub_serial}_ch{self._channel_id}_{sensor_type}"

        # Device info to link this sensor to its respective channel device
        # The channel device itself is linked to the main hub device.
        self._attr_device_info = DeviceInfo(
            identifiers={channel_device_identifier}, 
            # No name, model, manufacturer here as it should inherit from the channel device.
            # This effectively says "this sensor is part of the device identified by channel_device_identifier"
            # The channel device (e.g., cover entity) should have the full via_device=hub_identifier setup.
        )
        
        _LOGGER.debug(
            "Sensor initialized for channel %s of hub_serial '%s':",
            self._channel_id, self._hub_serial
        )
        _LOGGER.debug("  Friendly name: '%s'", self._attr_name)
        _LOGGER.debug("  Unique ID: '%s'", self._attr_unique_id)
        

    @property
    def available(self) -> bool:
        # Assuming data is fetched once at setup, so sensor is always available
        # unless the parent device (hub) becomes unavailable.
        # This could be enhanced if sensors were to update via a coordinator.
        return True

from .coordinator import ZeptrionAirDataUpdateCoordinator
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT # Added import

from .entity import ZeptrionAirEntity # Ensure this import is present

class ZeptrionAirRssiSensor(ZeptrionAirEntity, SensorEntity):
    """Representation of a Zeptrion Air RSSI Sensor for the Hub."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        coordinator: ZeptrionAirDataUpdateCoordinator,
        hub_device_info: DeviceInfo, # DeviceInfo for the main Hub
        hub_serial: str,
        hub_name: str,
        hub_name_slug: str,
    ) -> None:
        """Initialize the RSSI sensor."""
        super().__init__(coordinator)
        self._hub_serial: str = hub_serial
        
        self._attr_has_entity_name = True
        self._attr_name = "Wi-Fi Signal"
        self._attr_unique_id = f"zapp_{self._hub_serial}_rssi"

        _LOGGER.debug(
            "RSSI Sensor initialized for hub_serial '%s'",
            self._hub_serial
        )
        _LOGGER.debug("  Friendly name: '%s'", self._attr_name)
        _LOGGER.debug("  Unique ID: '%s'", self._attr_unique_id)
        
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

