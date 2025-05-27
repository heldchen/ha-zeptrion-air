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

# Assuming DOMAIN and LOGGER are defined in const.py, but not strictly needed for this minimal file to load.
# from .const import DOMAIN 
# If API client is needed by __init__ for light switch, it should be passed.
# from .api import ZeptrionAirApiClient 

_LOGGER = logging.getLogger(__name__) # Basic logger

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Zeptrion Air light entities from a config entry - MINIMAL.".""
    _LOGGER.info("Minimal light.py: async_setup_entry called. Not adding entities.")
    # For now, do not try to get platform_data or add entities.
    # platform_data = hass.data.get(DOMAIN, {}).get(entry.entry_id) 
    # if not platform_data:
    #     _LOGGER.error("Minimal light.py: No platform_data found.")
    #     return False
    # identified_channels_list = platform_data.get("identified_channels", [])
    # if not identified_channels_list:
    #    _LOGGER.info("Minimal light.py: No identified_channels_list found.")
    #    # return True # Successfully did nothing
    return True # Indicate successful setup, even if no entities added.

class ZeptrionAirMinimalLightSwitch(LightEntity):
    """Minimal representation of a Zeptrion Air Light Switch."""

    _attr_should_poll = False

    def __init__(self, channel_id: int, hub_serial: str) -> None:
        """Initialize the Zeptrion Air minimal light switch.".""
        self._channel_id = channel_id
        self._attr_name = f"Minimal Zeptrion Light ch{self._channel_id}"
        self._attr_unique_id = f"{hub_serial}_ch{self._channel_id}_minimal_light"
        self._attr_is_on: bool = False # Default to off
        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.ON_OFF}
        self._attr_color_mode: ColorMode = ColorMode.ON_OFF
        # Basic device info to link it to the hub
        # This might be needed if HA complains about entities without device info
        # For now, keeping it absolutely minimal.
        # self._attr_device_info = { 
        #     "identifiers": {(DOMAIN, f"{hub_serial}_ch{self._channel_id}")},
        #     "via_device": (DOMAIN, hub_serial),
        # }


    @property
    def is_on(self) -> bool:
        """Return true if light is on.".""
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on (does nothing in minimal).".""
        _LOGGER.debug(f"{self.name}: Minimal async_turn_on called.")
        # self._attr_is_on = True # No state change, no API call
        # self.async_write_ha_state()
        pass

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off (does nothing in minimal).".""
        _LOGGER.debug(f"{self.name}: Minimal async_turn_off called.")
        # self._attr_is_on = False # No state change, no API call
        # self.async_write_ha_state()
        pass

# Do NOT include ZeptrionAirLightDimmable or other complex logic for this step.
