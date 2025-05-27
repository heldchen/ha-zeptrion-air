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

from ..const import DOMAIN
from ..api import ZeptrionAirApiClient # Required for type hinting in __init__

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Zeptrion Air light entities from a config entry."""
    platform_data = hass.data[DOMAIN].get(entry.entry_id)

    if not platform_data:
        _LOGGER.error(f"light.py async_setup_entry: No platform_data found for entry ID {entry.entry_id}")
        return False # Indicate failure

    _LOGGER.debug(f"light.py async_setup_entry: Received platform_data: {platform_data}")

    api_client = platform_data.get("client")
    main_hub_device_info = platform_data.get("hub_device_info", {})
    identified_channels_list = platform_data.get("identified_channels", [])
    hub_entry_title = platform_data.get("entry_title", "Zeptrion Air Hub")
    hub_serial = platform_data.get("hub_serial")

    if not api_client or not hub_serial:
        _LOGGER.error("light.py async_setup_entry: API client or hub serial not found in platform_data.")
        return False # Indicate failure

    new_entities = []
    if identified_channels_list:
        for channel_info_dict in identified_channels_list:
            channel_id = channel_info_dict.get('id')
            # channel_cat is used for model name, keep it for now
            channel_cat = channel_info_dict.get('cat') 
            channel_name = channel_info_dict.get('name', f"Channel {channel_id}")
            device_type = channel_info_dict.get('device_type')

            if channel_id is None or device_type is None:
                _LOGGER.warning(f"light.py: Skipping channel due to missing id or device_type: {channel_info_dict}")
                continue

            if device_type == "light_switch":
                _LOGGER.debug(f"light.py: Channel {channel_id} (Name: '{channel_name}', Type: {device_type}). Creating ZeptrionAirLightSwitch entity.")
                
                light_device_info = {
                    "identifiers": {(DOMAIN, f"{hub_serial}_ch{channel_id}")},
                    "name": f"{hub_entry_title} {channel_name}", 
                    "via_device": (DOMAIN, hub_serial), 
                    "manufacturer": main_hub_device_info.get("manufacturer", "Feller AG"),
                    "model": f"Zeptrion Air Light Switch - Cat {channel_cat}", 
                    "sw_version": main_hub_device_info.get("sw_version"), # Assuming sw_version is part of main_hub_device_info
                }

                new_entities.append(
                    ZeptrionAirLightSwitch(
                        api_client=api_client,
                        device_info_for_light_entity=light_device_info,
                        channel_id=channel_id,
                        hub_serial=hub_serial, 
                        entry_title=hub_entry_title 
                    )
                )
            # elif device_type == "light_dimmer":
            #     _LOGGER.debug(f"light.py: Channel {channel_id} (Name: '{channel_name}', Type: {device_type}). Dimmable light - skipping for now.")
            else:
                _LOGGER.debug(f"light.py: Channel {channel_id} (Name: '{channel_name}', Type: {device_type}). Not a 'light_switch'. Skipping.")
    
    if new_entities:
        _LOGGER.debug(f"light.py: Adding {len(new_entities)} ZeptrionAirLightSwitch entities.")
        async_add_entities(new_entities)
    else:
        _LOGGER.debug("light.py: No light_switch entities to add.")
    
    return True # Indicate successful setup


class ZeptrionAirLightSwitch(LightEntity):
    """Representation of a Zeptrion Air Light Switch."""

    _attr_should_poll = False # Rely on optimistic updates

    def __init__(
        self,
        api_client: ZeptrionAirApiClient,
        device_info_for_light_entity: dict[str, Any],
        channel_id: int,
        hub_serial: str,
        entry_title: str, # Hub's name/title for context
    ) -> None:
        """Initialize the Zeptrion Air light switch."""
        self._api_client = api_client
        self._channel_id = channel_id
        
        self._attr_device_info = device_info_for_light_entity
        self._attr_name = device_info_for_light_entity.get("name")
        self._attr_unique_id = f"{hub_serial}_ch{self._channel_id}_light" # Corrected unique_id
        
        self._attr_is_on: bool | None = None # Initial state unknown
        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.ON_OFF}
        self._attr_color_mode: ColorMode = ColorMode.ON_OFF

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        _LOGGER.debug(f"Turning ON light: {self.name} (Channel: {self._channel_id})")
        prev_is_on = self._attr_is_on # Store previous state for revert
        try:
            await self._api_client.async_channel_on(self._channel_id)
            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Error turning ON light {self.name} (Channel: {self._channel_id}): {e}")
            self._attr_is_on = prev_is_on # Revert optimistic update
            # self.async_write_ha_state() # Optionally write state back
            # For now, do not write state back on error to avoid rapid changes if error is persistent

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        _LOGGER.debug(f"Turning OFF light: {self.name} (Channel: {self._channel_id})")
        prev_is_on = self._attr_is_on # Store previous state for revert
        try:
            await self._api_client.async_channel_off(self._channel_id)
            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Error turning OFF light {self.name} (Channel: {self._channel_id}): {e}")
            self._attr_is_on = prev_is_on # Revert optimistic update
            # self.async_write_ha_state() # Optionally write state back
