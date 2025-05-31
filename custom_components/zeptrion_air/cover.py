"""Cover platform for Zeptrion Air."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ZeptrionAirApiClient, ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError
from .const import (
    DOMAIN,
    SERVICE_BLIND_RECALL_S1,
    SERVICE_BLIND_RECALL_S2,
    SERVICE_BLIND_RECALL_S3,
    SERVICE_BLIND_RECALL_S4,
    CONF_STEP_DURATION_MS,
    DEFAULT_STEP_DURATION_MS,
    ZEPTRION_AIR_WEBSOCKET_MESSAGE,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Zeptrion Air cover entities from a config entry."""
    platform_data: dict[str, Any] | None = hass.data[DOMAIN].get(entry.entry_id)

    if not platform_data:
        _LOGGER.error("No platform_data found for entry ID %s", entry.entry_id)
        return False

    _LOGGER.debug("Received platform_data: %s", platform_data)

    main_hub_device_info: dict[str, Any] = platform_data.get("hub_device_info", {})
    identified_channels_list: list[dict[str, Any]] = platform_data.get("identified_channels", [])
    hub_entry_title: str = platform_data.get("entry_title", "Zeptrion Air Hub") 
    
    hub_serial_for_blinds_maybe: str | None = platform_data.get("hub_serial")
    if not hub_serial_for_blinds_maybe:
        _LOGGER.error("Hub serial not found in platform_data.")
        return False
    hub_serial_for_blinds: str = hub_serial_for_blinds_maybe

    new_entities: list[ZeptrionAirBlind] = []

    panel_type_mapping: dict[int, str] = {
        5: "Blinds",
        6: "Markise"
    }

    if identified_channels_list:
        for channel_info_dict in identified_channels_list:
            channel_id_maybe: int | None = channel_info_dict.get('id')
            channel_cat_maybe: int | None = channel_info_dict.get('cat')
            device_type: str | None = channel_info_dict.get('device_type')

            if channel_id_maybe is None or channel_cat_maybe is None or device_type != "cover":
                if device_type != "cover" and channel_id_maybe is not None: 
                     _LOGGER.debug("Skipping channel %s (Cat: %s). Not a cover device_type ('%s').", 
                                   channel_id_maybe, channel_cat_maybe, device_type)
                else: 
                     _LOGGER.warning("Skipping channel due to missing id, cat or not being a cover: %s", 
                                     channel_info_dict)
                continue
            
            channel_id: int = channel_id_maybe
            channel_cat: int = channel_cat_maybe
            
            entity_base_name: str | None = channel_info_dict.get("entity_base_name")
            desired_name: str = entity_base_name if entity_base_name is not None else f"Channel {channel_id}"

            entity_base_slug = desired_name.lower().replace(' ', '_').replace('-', '_').replace('.', '_').replace(':', '_')
            entity_base_slug = '_'.join(filter(None, entity_base_slug.split('_')))

            _LOGGER.debug("Channel %s (Cat: %s). Type is cover. Using Name: '%s'. Entity base slug: '%s'. Creating entity.",
                          channel_id, channel_cat, desired_name, entity_base_slug)
            
            hub_manufacturer: str = main_hub_device_info.get("manufacturer", "Feller AG")
            hub_sw_version: str | None = main_hub_device_info.get("sw_version")

            blind_device_info: dict[str, Any] = {
                "identifiers": {(DOMAIN, f"{hub_serial_for_blinds}_ch{channel_id}")},
                "name": desired_name, 
                "via_device": (DOMAIN, hub_serial_for_blinds),
                "manufacturer": hub_manufacturer,
                "sw_version": hub_sw_version,
            }
            panel_type_string: str = panel_type_mapping.get(channel_cat, "Unknown Panel")
            blind_device_info["model"] = f"Zeptrion Air Channel {channel_id} - {panel_type_string}"

            new_entities.append(
                ZeptrionAirBlind(
                    config_entry=entry, 
                    device_info_for_blind_entity=blind_device_info,
                    channel_id=channel_id,
                    hub_serial=hub_serial_for_blinds,
                    entry_title=hub_entry_title,
                    entity_base_slug=entity_base_slug
                )
            )
    
    if new_entities:
        for entity in new_entities:
            _LOGGER.debug("Preparing to add cover entity: Name: %s, Unique ID: %s",
                          entity.name, entity.unique_id)
        _LOGGER.info("Adding %s ZeptrionAirBlind cover entities.", len(new_entities))
        async_add_entities(new_entities)
    else:
        _LOGGER.info("No Zeptrion Air cover entities to add.")
    
    return True


class ZeptrionAirBlind(CoverEntity):
    """Representation of a Zeptrion Air Blind."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        device_info_for_blind_entity: dict[str, Any], 
        channel_id: int,
        hub_serial: str, 
        entry_title: str,
        entity_base_slug: str,
    ) -> None:
        """Initialize the Zeptrion Air blind."""
        self.config_entry: ConfigEntry = config_entry 
        self._channel_id: int = channel_id
        
        self._attr_device_info: dict[str, Any] = device_info_for_blind_entity
        
        name_val = device_info_for_blind_entity.get("name")
        self._attr_name: str = str(name_val) if name_val is not None else f"Channel {channel_id}"
        self._attr_unique_id = f"zapp_{hub_serial}_ch{self._channel_id}"
        
        _LOGGER.debug("ZeptrionAirBlind cover entity initialized:")
        _LOGGER.debug("  Friendly name: '%s'", self._attr_name)
        _LOGGER.debug("  Unique ID: '%s'", self._attr_unique_id)

        self._attr_device_class = CoverDeviceClass.SHUTTER
        
        self._attr_is_closed: bool | None = None
        self._attr_is_opening: bool = False
        self._attr_is_closing: bool = False
        self._attr_current_cover_position: int | None = None
        self._commanded_action: str | None = None
        self._active_action: str | None = None

        self._attr_supported_features: CoverEntityFeature = (
            CoverEntityFeature.OPEN |
            CoverEntityFeature.CLOSE |
            CoverEntityFeature.STOP |
            CoverEntityFeature.OPEN_TILT |
            CoverEntityFeature.CLOSE_TILT
        )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or position is unknown."""
        # this is unreliable as we don't know the real position. it can be influenced by
        # hardware button presses and scenes, so we always return None to avoid buttons
        # being disabled automatically by HA based on the Cover state
        #return self._attr_is_closed
        return None

    @property
    def is_opening(self) -> bool:
        """Return if the cover is currently opening."""
        return self._attr_is_opening

    @property
    def is_closing(self) -> bool:
        """Return if the cover is currently closing."""
        return self._attr_is_closing

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover. None if unknown."""
        return self._attr_current_cover_position

    async def async_open_cover(self) -> None:
        """Open the cover."""
        _LOGGER.debug("Opening blind %s (Channel %s)", self._attr_name, self._channel_id)
        self._commanded_action = "opening"
        try:
            await self.config_entry.runtime_data.client.async_channel_open(self._channel_id)
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            self._commanded_action = None
            _LOGGER.error("API error while opening blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to open blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            self._commanded_action = None
            _LOGGER.error("Unexpected error while opening blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to open blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_close_cover(self) -> None:
        """Close the cover."""
        _LOGGER.debug("Closing blind %s (Channel %s)", self._attr_name, self._channel_id)
        self._commanded_action = "closing"
        try:
            await self.config_entry.runtime_data.client.async_channel_close(self._channel_id)
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            self._commanded_action = None
            _LOGGER.error("API error while closing blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to close blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            self._commanded_action = None
            _LOGGER.error("Unexpected error while closing blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to close blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_stop_cover(self) -> None:
        """Stop the cover movement."""
        _LOGGER.debug("Stopping blind %s (Channel %s)", self._attr_name, self._channel_id)
        self._commanded_action = "stop"
        try:
            await self.config_entry.runtime_data.client.async_channel_stop(self._channel_id)
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            self._commanded_action = None
            _LOGGER.error("API error while stopping blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to stop blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            self._commanded_action = None
            _LOGGER.error("Unexpected error while stopping blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to stop blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_open_cover_tilt(self) -> None:
        """Tilt the cover open."""
        _LOGGER.debug("Tilting open blind %s (Channel %s)", self._attr_name, self._channel_id)
        self._commanded_action = "tilt_opening"
        try:
            step_duration_ms = self.config_entry.data.get(CONF_STEP_DURATION_MS, DEFAULT_STEP_DURATION_MS)
            await self.config_entry.runtime_data.client.async_channel_move_open(self._channel_id, time_ms=step_duration_ms)
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            _LOGGER.error("API error while tilting open blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to tilt open blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while tilting open blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to tilt open blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_close_cover_tilt(self) -> None:
        """Tilt the cover closed."""
        _LOGGER.debug("Tilting close blind %s (Channel %s)", self._attr_name, self._channel_id)
        self._commanded_action = "tilt_closing"
        try:
            step_duration_ms = self.config_entry.data.get(CONF_STEP_DURATION_MS, DEFAULT_STEP_DURATION_MS)
            await self.config_entry.runtime_data.client.async_channel_move_close(self._channel_id, time_ms=step_duration_ms)
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            self._commanded_action = None
            _LOGGER.error("API error while tilting close blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to tilt close blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            self._commanded_action = None
            _LOGGER.error("Unexpected error while tilting close blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to tilt close blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(
                ZEPTRION_AIR_WEBSOCKET_MESSAGE, self.async_handle_websocket_message
            )
        )
                                            
        platform: entity_platform.EntityPlatform | None = entity_platform.async_get_current_platform()

        if platform:
            platform.async_register_entity_service(
                SERVICE_BLIND_RECALL_S1,
                {},
                self.async_blind_recall_s1.__name__
            )
            platform.async_register_entity_service(
                SERVICE_BLIND_RECALL_S2,
                {},
                self.async_blind_recall_s2.__name__
            )
            platform.async_register_entity_service(
                SERVICE_BLIND_RECALL_S3,
                {},
                self.async_blind_recall_s3.__name__
            )
            platform.async_register_entity_service(
                SERVICE_BLIND_RECALL_S4,
                {},
                self.async_blind_recall_s4.__name__
            )
        else:
            _LOGGER.warning("Entity platform not available for %s, services not registered.", self.entity_id)

    async def async_handle_websocket_message(self, event: Event) -> None:
        """Handle websocket messages for the blind."""
        message_data = event.data
        if message_data.get("channel") == self._channel_id and message_data.get("source") == "eid1":
            message_value = message_data.get("value")

            _LOGGER.debug("Handling WS for %s: val=%s, cmd_action=%s, active_action=%s, is_closed=%s",
                          self._attr_name, message_value, self._commanded_action, self._active_action, self._attr_is_closed)

            if message_value == 100:  # Action is running
                if self._commanded_action == "opening" or self._commanded_action == "tilt_opening":
                    self._active_action = "opening"
                elif self._commanded_action == "closing" or self._commanded_action == "tilt_closing":
                    self._active_action = "closing"
                else:
                    _LOGGER.warning("Blind %s received val=100 (movement started) but current commanded_action is '%s'. "
                                    "_active_action will remain '%s'. This may indicate a desync or delayed message.",
                                    self._attr_name, self._commanded_action, self._active_action)

                if self._active_action == "opening":
                    self._attr_is_opening = True
                    self._attr_is_closing = False
                    self._attr_is_closed = None
                elif self._active_action == "closing":
                    self._attr_is_closing = True
                    self._attr_is_opening = False
                    self._attr_is_closed = None
                else:
                    self._attr_is_opening = False
                    self._attr_is_closing = False

            elif processed_value == 0:  # Action stopped
                # this is unreliable as we don't know the real position. it can be influenced by
                # hardware button presses and scenes
                if self._active_action == "opening":
                    self._attr_is_closed = False
                elif self._active_action == "closing":
                    self._attr_is_closed = True

                self._attr_is_opening = False
                self._attr_is_closing = False
                self._active_action = None
                
            else:
                return

            _LOGGER.debug("Finished WS for %s: cmd_action=%s, active_action=%s, is_closed=%s, is_opening=%s, is_closing=%s",
                          self._attr_name, self._commanded_action, self._active_action, self._attr_is_closed, 
                          self._attr_is_opening, self._attr_is_closing)
            self.async_write_ha_state()

    async def async_blind_recall_s1(self) -> None:
        """Recall scene S1 for the blind."""
        _LOGGER.debug("Recalling S1 for blind %s (Channel %s)", self.name, self._channel_id)
        try:
            await self.config_entry.runtime_data.client.async_channel_recall_s1(self._channel_id)
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            _LOGGER.error("API error while recalling S1 for blind %s (Channel %s): %s", self.name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to recall S1 for blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while recalling S1 for blind %s (Channel %s): %s", self.name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to recall S1 for blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_blind_recall_s2(self) -> None:
        """Recall scene S2 for the blind."""
        _LOGGER.debug("Recalling S2 for blind %s (Channel %s)", self.name, self._channel_id)
        try:
            await self.config_entry.runtime_data.client.async_channel_recall_s2(self._channel_id)
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            _LOGGER.error("API error while recalling S2 for blind %s (Channel %s): %s", self.name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to recall S2 for blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while recalling S2 for blind %s (Channel %s): %s", self.name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to recall S2 for blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_blind_recall_s3(self) -> None:
        """Recall scene S3 for the blind."""
        _LOGGER.debug("Recalling S3 for blind %s (Channel %s)", self.name, self._channel_id)
        try:
            await self.config_entry.runtime_data.client.async_channel_recall_s3(self._channel_id)
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            _LOGGER.error("API error while recalling S3 for blind %s (Channel %s): %s", self.name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to recall S3 for blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while recalling S3 for blind %s (Channel %s): %s", self.name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to recall S3 for blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_blind_recall_s4(self) -> None:
        """Recall scene S4 for the blind."""
        _LOGGER.debug("Recalling S4 for blind %s (Channel %s)", self.name, self._channel_id)
        try:
            await self.config_entry.runtime_data.client.async_channel_recall_s4(self._channel_id)
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            _LOGGER.error("API error while recalling S4 for blind %s (Channel %s): %s", self.name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to recall S4 for blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while recalling S4 for blind %s (Channel %s): %s", self.name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to recall S4 for blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e
