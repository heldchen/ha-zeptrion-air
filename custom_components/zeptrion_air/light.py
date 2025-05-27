"""Light platform for Zeptrion Air."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    # LightEntityFeature, # Not used for basic ON/OFF switch
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..api import ZeptrionAirApiClient
from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zeptrion Air light entities from a config entry."""
    platform_data = hass.data[DOMAIN].get(entry.entry_id)

    if not platform_data:
        _LOGGER.error(f"light.py async_setup_entry: No platform_data found for entry ID {entry.entry_id}")
        return

    _LOGGER.debug(f"light.py async_setup_entry: Received platform_data: {platform_data}")

    api_client = platform_data.get("client")
    main_hub_device_info = platform_data.get("hub_device_info", {})
    identified_channels_list = platform_data.get("identified_channels", [])
    hub_entry_title = platform_data.get("entry_title", "Zeptrion Air Hub")
    hub_serial_for_subdevices = platform_data.get("hub_serial") # Renamed for clarity

    _LOGGER.debug(f"light.py async_setup_entry: Identified channels list: {identified_channels_list}")

    if not api_client or not hub_serial_for_subdevices:
        _LOGGER.error("light.py async_setup_entry: API client or hub serial not found in platform_data.")
        return

    new_entities = []
    if identified_channels_list:
        for channel_info_dict in identified_channels_list:
            channel_id = channel_info_dict.get('id')
            channel_cat = channel_info_dict.get('cat')
            channel_name = channel_info_dict.get('name', f"Channel {channel_id}")
            # channel_icon = channel_info_dict.get('icon') # Available if needed

            if channel_id is None or channel_cat is None:
                _LOGGER.warning(f"light.py: Skipping channel due to missing id or cat: {channel_info_dict}")
                continue

            # Category for Light ON/OFF (e.g., cat 0, 2, 4, 7 - need to confirm specific Zeptrion categories)
            # The prompt specifies cat=1 for LightSwitch. This seems unusual as cat=1 was Jalousie.
            # Assuming the prompt means a specific category for ON/OFF lights.
            # For now, strictly following "If channel_cat == 1:" from prompt.
            # This will likely need adjustment based on actual Zeptrion light categories.
            if channel_cat == 1: # As per prompt, though cat 1 is Jalousie in API doc.
                                 # Typical light ON/OFF might be cat 0, 2, or similar.
                _LOGGER.debug(f"light.py: Channel {channel_id} (Cat: {channel_cat}, Name: '{channel_name}'). Type is LightSwitch. Creating entity.")
                
                light_device_info = {
                    "identifiers": {(DOMAIN, f"{hub_serial_for_subdevices}_ch{channel_id}")},
                    "name": f"{hub_entry_title} {channel_name}", 
                    "via_device": (DOMAIN, hub_serial_for_subdevices), 
                    "manufacturer": main_hub_device_info.get("manufacturer", "Feller AG"),
                    "model": f"Zeptrion Air Light - Cat {channel_cat}", 
                    "sw_version": main_hub_device_info.get("sw_version"),
                }

                new_entities.append(
                    ZeptrionAirLightSwitch(
                        api_client=api_client,
                        device_info_for_light_entity=light_device_info,
                        channel_id=channel_id,
                        hub_serial=hub_serial_for_subdevices, 
                        entry_title=hub_entry_title 
                    )
                )
            # Placeholder for dimmable lights (e.g., cat 3 as per prompt, though cat 3 is Store in API doc)
            # elif channel_cat == 3: 
            #     _LOGGER.debug(f"light.py: Channel {channel_id} (Cat: {channel_cat}, Name: '{channel_name}'). Type is Dimmable Light. Placeholder.")
            #     # Instantiate ZeptrionAirLightDimmable here if implemented
            else:
                # This log will catch channels not matching cat 1 (or other light cats if added)
                _LOGGER.debug(f"light.py: Channel {channel_id} (Cat: {channel_cat}, Name: '{channel_name}'). Not a configured Light type. Skipping.")
    
    if new_entities:
        _LOGGER.debug(f"light.py: Adding {len(new_entities)} ZeptrionAirLight entities.")
        async_add_entities(new_entities)
    else:
        _LOGGER.debug("light.py: No light entities to add.")


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
        # Unique ID for the entity: e.g., "HUB_SERIAL_ch1_light"
        self._attr_unique_id = f"{hub_serial}_ch{self._channel_id}_light"
        
        self._attr_is_on: bool | None = None # Initial state unknown, or False
        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.ON_OFF}
        self._attr_color_mode: ColorMode = ColorMode.ON_OFF

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        _LOGGER.debug(f"Turning ON light: {self.name} (Channel: {self._channel_id})")
        try:
            # await self._api_client.async_channel_on(self._channel_id) # API method to be added
            # For now, let's mock the behavior of calling the API client method
            # This will be replaced with actual API call once methods are added.
            if hasattr(self._api_client, "async_channel_on"):
                 await self._api_client.async_channel_on(self._channel_id)
            else:
                _LOGGER.warning(f"API method async_channel_on not yet implemented for {self.name}")
                # Simulate success for optimistic update
            
            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Error turning ON light {self.name}: {e}")
            # Optionally, revert optimistic update
            # self._attr_is_on = False 
            # self.async_write_ha_state()


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        _LOGGER.debug(f"Turning OFF light: {self.name} (Channel: {self._channel_id})")
        try:
            # await self._api_client.async_channel_off(self._channel_id) # API method to be added
            if hasattr(self._api_client, "async_channel_off"):
                await self._api_client.async_channel_off(self._channel_id)
            else:
                _LOGGER.warning(f"API method async_channel_off not yet implemented for {self.name}")
                # Simulate success for optimistic update

            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Error turning OFF light {self.name}: {e}")
            # Optionally, revert optimistic update
            # self._attr_is_on = True
            # self.async_write_ha_state()

# Placeholder for Dimmable Light
# class ZeptrionAirLightDimmable(LightEntity): # Or ZeptrionAirLightBase
#     _attr_should_poll = False
#     # ... __init__ ...
#
#     @property
#     def brightness(self) -> int | None:
#         return self._attr_brightness # self._attr_brightness needs to be managed
#
#     async def async_turn_on(self, brightness: int | None = None, **kwargs: Any) -> None:
#         _LOGGER.debug(f"Turning ON dimmable light: {self.name} (Ch: {self._channel_id}), Brightness: {brightness}")
#         # brightness is 0-255
#         # API might expect 0-100. Conversion needed: api_brightness = round(brightness * 100 / 255)
#         try:
#             if brightness is not None:
#                 # await self._api_client.async_channel_set_brightness(self._channel_id, api_brightness)
#                 _LOGGER.warning(f"API method async_channel_set_brightness not yet implemented for {self.name}")
#                 self._attr_brightness = brightness # Optimistic
#             else:
#                 # await self._api_client.async_channel_on(self._channel_id)
#                 _LOGGER.warning(f"API method async_channel_on not yet implemented for {self.name}")
#                 # If turning on without brightness, HA might keep last brightness or set to max.
#                 # self._attr_brightness = self._attr_brightness or 255 # Example
#             self._attr_is_on = True
#             self.async_write_ha_state()
#         except Exception as e:
#             _LOGGER.error(f"Error turning ON dimmable light {self.name}: {e}")
#
#     async def async_turn_off(self, **kwargs: Any) -> None:
#         # ... similar to ZeptrionAirLightSwitch ...
#         self._attr_is_on = False
#         # self._attr_brightness = 0 # Or None, depending on HA behavior
#         self.async_write_ha_state()
#
#     @property
#     def supported_color_modes(self) -> set[ColorMode] | None:
#         return {ColorMode.BRIGHTNESS}
#
#     @property
#     def color_mode(self) -> ColorMode | None:
#         return ColorMode.BRIGHTNESS
