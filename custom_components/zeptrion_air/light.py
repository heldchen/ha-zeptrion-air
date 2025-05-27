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

_LOGGER = logging.getLogger(__name__)

# TODO: This is a minimal placeholder for the Zeptrion Air light platform.
# It was reverted to this state to debug a ModuleNotFoundError.
# Full implementation for light switches (cat=1) and dimmers (cat=3)
# needs to be carefully re-introduced and tested.

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Zeptrion Air light entities from a config entry - MINIMAL DEBUG VERSION."""
    _LOGGER.info("Minimal light.py: async_setup_entry called. Intentionally not adding entities for debugging.")
    return True

class ZeptrionAirMinimalLightSwitch(LightEntity):
    """Minimal representation of a Zeptrion Air Light Switch (Placeholder)."""

    _attr_should_poll = False

    def __init__(self, channel_id: int, hub_serial: str) -> None:
        """Initialize the Zeptrion Air minimal light switch (Placeholder)."""
        self._channel_id = channel_id
        self._attr_name = f"Minimal Zeptrion Light ch{self._channel_id}"
        self._attr_unique_id = f"{hub_serial}_ch{self._channel_id}_minimal_light"
        self._attr_is_on: bool = False
        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.ON_OFF}
        self._attr_color_mode: ColorMode = ColorMode.ON_OFF

    @property
    def is_on(self) -> bool:
        """Return true if light is on (Placeholder)."""
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on (Placeholder - does nothing)."""
        _LOGGER.debug(f"{self.name}: Minimal async_turn_on called (does nothing).")
        pass

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off (Placeholder - does nothing)."""
        _LOGGER.debug(f"{self.name}: Minimal async_turn_off called (does nothing).")
        pass
