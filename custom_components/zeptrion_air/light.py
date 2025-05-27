"""Light platform for Zeptrion Air."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
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
            channel_cat = channel_info_dict.get('cat') # Keep for model info if desired
            channel_name = channel_info_dict.get('name', f"Channel {channel_id}")
            device_type = channel_info_dict.get('device_type')
            # channel_icon = channel_info_dict.get('icon') # Available if needed

            if channel_id is None or device_type is None:
                _LOGGER.warning(f"light.py: Skipping channel due to missing id or device_type: {channel_info_dict}")
                continue
            
            # Common device info construction
            light_device_info = {
                "identifiers": {(DOMAIN, f"{hub_serial_for_subdevices}_ch{channel_id}")},
                "name": f"{hub_entry_title} {channel_name}",
                "via_device": (DOMAIN, hub_serial_for_subdevices),
                "manufacturer": main_hub_device_info.get("manufacturer", "Feller AG"),
                # Model can be more specific based on device_type or cat
                "model": f"Zeptrion Air Light - {device_type.replace('_', ' ').title()} (Cat {channel_cat})",
                "sw_version": main_hub_device_info.get("sw_version"),
            }

            if device_type == "light_switch":
                _LOGGER.debug(f"light.py: Channel {channel_id} (Name: '{channel_name}', Type: {device_type}). Creating ZeptrionAirLightSwitch entity.")
                new_entities.append(
                    ZeptrionAirLightSwitch(
                        api_client=api_client,
                        device_info_for_light_entity=light_device_info,
                        channel_id=channel_id,
                        hub_serial=hub_serial_for_subdevices,
                        entry_title=hub_entry_title
                    )
                )
            elif device_type == "light_dimmer":
                _LOGGER.debug(f"light.py: Channel {channel_id} (Name: '{channel_name}', Type: {device_type}). Creating ZeptrionAirLightDimmable entity.")
                new_entities.append(
                    ZeptrionAirLightDimmable(
                        api_client=api_client,
                        device_info_for_light_entity=light_device_info,
                        channel_id=channel_id,
                        hub_serial=hub_serial_for_subdevices,
                        entry_title=hub_entry_title
                    )
                )
            else:
                _LOGGER.debug(f"light.py: Channel {channel_id} (Name: '{channel_name}', Type: {device_type}). Not a configured Light platform type. Skipping.")

    if new_entities:
        _LOGGER.debug(f"light.py: Adding {len(new_entities)} Zeptrion Air Light entities.")
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


class ZeptrionAirLightDimmable(LightEntity):
    """Representation of a Zeptrion Air Dimmable Light."""

    _attr_should_poll = False # Rely on optimistic updates

    def __init__(
        self,
        api_client: ZeptrionAirApiClient,
        device_info_for_light_entity: dict[str, Any],
        channel_id: int,
        hub_serial: str,
        entry_title: str, # Hub's name/title for context
    ) -> None:
        """Initialize the Zeptrion Air dimmable light."""
        self._api_client = api_client
        self._channel_id = channel_id
        
        self._attr_device_info = device_info_for_light_entity
        self._attr_name = device_info_for_light_entity.get("name")
        # Unique ID for the entity: e.g., "HUB_SERIAL_ch1_light_dimmer"
        self._attr_unique_id = f"{hub_serial}_ch{self._channel_id}_light_dimmer"
        
        self._attr_is_on: bool | None = None # Initial state unknown
        self._attr_brightness: int | None = None # Stores HA brightness 0-255

        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.BRIGHTNESS}
        self._attr_color_mode: ColorMode = ColorMode.BRIGHTNESS

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._attr_is_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._attr_brightness

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get("brightness") # HA provides brightness in 0-255 range

        # Store previous state for potential revert on error
        prev_is_on = self._attr_is_on
        prev_brightness = self._attr_brightness

        try:
            if brightness is not None:
                _LOGGER.debug(
                    f"Turning ON dimmable light: {self.name} (Channel: {self._channel_id}) with brightness: {brightness}"
                )
                # The async_channel_set_brightness method in API client will handle conversion if needed
                await self._api_client.async_channel_set_brightness(self._channel_id, brightness)
                self._attr_brightness = brightness
                self._attr_is_on = True
            else:
                _LOGGER.debug(
                    f"Turning ON dimmable light: {self.name} (Channel: {self._channel_id}) without specific brightness"
                )
                await self._api_client.async_channel_on(self._channel_id)
                self._attr_is_on = True
                # If light is turned on without specific brightness, and current brightness is 0 or None,
                # set to full brightness (255) for HA state.
                if self._attr_brightness is None or self._attr_brightness == 0:
                    self._attr_brightness = 255
            
            self.async_write_ha_state()

        except Exception as e: # Catch ZeptrionAirApiClientError specifically if defined and imported
            _LOGGER.error(f"Error turning ON dimmable light {self.name} (Channel: {self._channel_id}): {e}")
            # Revert optimistic updates
            self._attr_is_on = prev_is_on
            self._attr_brightness = prev_brightness
            # self.async_write_ha_state() # Optionally update HA state back, or let it be eventually corrected by polling/next update
            # For now, we don't call async_write_ha_state() on error to avoid potential rapid state changes if errors are frequent.

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        _LOGGER.debug(f"Turning OFF dimmable light: {self.name} (Channel: {self._channel_id})")
        try:
            # Store previous state for potential revert on error
            prev_is_on = self._attr_is_on
            # prev_brightness = self._attr_brightness # Brightness is not changed by turn_off directly

            await self._api_client.async_channel_off(self._channel_id)
            self._attr_is_on = False
            # Per HA developer guidelines, brightness should not be set to 0 when turning off,
            # but rather retain its last value so it can be restored when turned back on without a specific brightness.
            # self._attr_brightness = 0 # So, this line is commented out.
            self.async_write_ha_state()
        except Exception as e: # Catch ZeptrionAirApiClientError specifically if defined and imported
            _LOGGER.error(f"Error turning OFF dimmable light {self.name} (Channel: {self._channel_id}): {e}")
            # Revert optimistic update
            self._attr_is_on = prev_is_on
            # self.async_write_ha_state() # Optionally update HA state back
