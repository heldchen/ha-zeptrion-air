from __future__ import annotations

import logging
from typing import Any # Add Any for **kwargs if used

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.light import (
    ColorMode,
    LightEntity,
)
# Removed unused ZeptrionAirApiClient import if it was there, ensure DOMAIN is imported
from .const import DOMAIN, ENTITY_IMAGE_CHANNEL # Added ENTITY_IMAGE_CHANNEL import

_LOGGER = logging.getLogger(__name__)

# TODO: This is a minimal placeholder for the Zeptrion Air light platform.
# Full implementation for light switches (cat=1) and dimmers (cat=3)
# needs to be carefully re-introduced and tested.

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Zeptrion Air light entities from a config entry."""
    _LOGGER.debug(f"light.py async_setup_entry for {entry.title}")
    platform_data = hass.data[DOMAIN].get(entry.entry_id)

    if not platform_data:
        _LOGGER.error(f"light.py async_setup_entry: No platform_data found for entry ID {entry.entry_id}")
        return False # Indicate setup failure

    identified_channels_list = platform_data.get("identified_channels", [])
    hub_serial = platform_data.get("hub_serial")
    hub_entry_title = platform_data.get("entry_title", "Zeptrion Air Hub") # For naming fallback

    if not hub_serial:
        _LOGGER.error("light.py async_setup_entry: Hub serial not found in platform_data.")
        return False # Indicate setup failure

    if not identified_channels_list:
        _LOGGER.info("light.py async_setup_entry: No identified_channels found in platform_data for %s.", entry.title)
        return True # No entities to add, but setup is not a failure

    new_entities = []
    _LOGGER.debug(f"light.py: Processing {len(identified_channels_list)} identified channels for lights.")

    for channel_info in identified_channels_list:
        channel_id = channel_info.get('id')
        device_type = channel_info.get('device_type')
        entity_base_name = channel_info.get('entity_base_name')

        if channel_id is None or device_type not in ("light_switch", "light_dimmer"):
            _LOGGER.debug(f"light.py: Skipping channel {channel_id} (Type: {device_type}). Not a light switch or dimmer.")
            continue

        desired_name = entity_base_name if entity_base_name else f"{hub_entry_title} Light {channel_id}"
        _LOGGER.debug(f"light.py: Creating light entity for Channel {channel_id} (Type: {device_type}) with Name: '{desired_name}'.")
        
        new_entities.append(
            ZeptrionAirMinimalLightSwitch(
                config_entry=entry,
                channel_id=channel_id,
                hub_serial=hub_serial,
                name=desired_name 
            )
        )

    if new_entities:
        _LOGGER.info(f"light.py: Adding {len(new_entities)} Zeptrion Air light entities for {entry.title}.")
        async_add_entities(new_entities)
    else:
        _LOGGER.info(f"light.py: No light entities to add for {entry.title} from identified channels.")
    
    return True # Indicate successful setup (even if no entities were added)

class ZeptrionAirMinimalLightSwitch(LightEntity):
    """Minimal representation of a Zeptrion Air Light Switch (Placeholder)."""

    _attr_should_poll = False # Zeptrion devices generally don't push state updates well

    def __init__(self, config_entry: ConfigEntry, channel_id: int, hub_serial: str, name: str) -> None:
        """Initialize the Zeptrion Air minimal light switch."""
        self.config_entry = config_entry # Store config_entry
        self._channel_id = channel_id
        self._attr_name = name # Use the name passed from async_setup_entry
        self._attr_unique_id = f"{hub_serial}_ch{self._channel_id}_light" # Ensure consistent unique_id, removed "_minimal"
        # Note: Actual device state (is_on) would need to be fetched or managed.
        # For this minimal version, it's initialized to False.
        self._attr_is_on: bool = False 
        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.ON_OFF}
        self._attr_color_mode: ColorMode = ColorMode.ON_OFF
        # Device info can be added here if desired, similar to cover.py, for better HA integration
        # self._attr_device_info = {
        #     "identifiers": {(DOMAIN, f"{hub_serial}_ch{self._channel_id}")},
        #     "name": name,
        #     "via_device": (DOMAIN, hub_serial),
        #     # Add other relevant device info (manufacturer, model, sw_version)
        # }
        self._attr_entity_picture = ENTITY_IMAGE_CHANNEL # Added entity picture
        _LOGGER.debug(f"ZeptrionAirMinimalLightSwitch initialized: {self.name} (ID: {self.unique_id})")


    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        # In a real implementation, this would reflect the actual state.
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Placeholder: In a real implementation, this would send a command.
        # Example: await self.config_entry.runtime_data.client.async_channel_on(self._channel_id)
        _LOGGER.debug(f"{self.name}: async_turn_on called. (Currently a placeholder).")
        # self._attr_is_on = True # Optimistic update
        # self.async_write_ha_state() # Update HA state

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        # Placeholder: In a real implementation, this would send a command.
        # Example: await self.config_entry.runtime_data.client.async_channel_off(self._channel_id)
        _LOGGER.debug(f"{self.name}: async_turn_off called. (Currently a placeholder).")
        # self._attr_is_on = False # Optimistic update
        # self.async_write_ha_state() # Update HA state

