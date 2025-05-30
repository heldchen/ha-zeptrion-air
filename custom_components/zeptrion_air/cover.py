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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .api import ZeptrionAirApiClient, ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError # Adjusted if ZeptrionAirHub is not used directly here
from .const import (
    DOMAIN,
    SERVICE_BLIND_RECALL_S1,
    SERVICE_BLIND_RECALL_S2,
    SERVICE_BLIND_RECALL_S3,
    SERVICE_BLIND_RECALL_S4,
    CONF_STEP_DURATION_MS,
    DEFAULT_STEP_DURATION_MS,
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
        _LOGGER.error(f"async_setup_entry: No platform_data found for entry ID {entry.entry_id}")
        return False

    _LOGGER.debug(f"async_setup_entry: Received platform_data: {platform_data}")

    main_hub_device_info: dict[str, Any] = platform_data.get("hub_device_info", {})
    identified_channels_list: list[dict[str, Any]] = platform_data.get("identified_channels", [])
    hub_entry_title: str = platform_data.get("entry_title", "Zeptrion Air Hub") 
    
    hub_serial_for_blinds_maybe: str | None = platform_data.get("hub_serial")
    if not hub_serial_for_blinds_maybe:
        _LOGGER.error("async_setup_entry: Hub serial not found in platform_data.")
        return False # Changed return
    hub_serial_for_blinds: str = hub_serial_for_blinds_maybe

    new_entities: list[ZeptrionAirBlind] = []

    panel_type_mapping: dict[int, str] = {
        5: "Blinds", # Rollladen
        6: "Markise" # Markise/Awning
        # Add other mappings here if other cat values are used for covers in the future
    }

    if identified_channels_list:
        for channel_info_dict in identified_channels_list: # channel_info_dict is dict[str, Any]
            channel_id_maybe: int | None = channel_info_dict.get('id')
            channel_cat_maybe: int | None = channel_info_dict.get('cat')
            device_type: str | None = channel_info_dict.get('device_type')

            if channel_id_maybe is None or channel_cat_maybe is None or device_type != "cover":
                if device_type != "cover" and channel_id_maybe is not None : 
                     _LOGGER.debug(f"Skipping channel {channel_id_maybe} (Cat: {channel_cat_maybe}). Not a cover device_type ('{device_type}').")
                else: 
                     _LOGGER.warning(f"Skipping channel due to missing id, cat or not being a cover: {channel_info_dict}")
                continue
            
            channel_id: int = channel_id_maybe # Now int
            channel_cat: int = channel_cat_maybe # Now int
            
            entity_base_name: str | None = channel_info_dict.get("entity_base_name")
            desired_name: str = entity_base_name if entity_base_name is not None else f"Channel {channel_id}"

            # Create a stable base name for entity IDs (slugified version of entity_base_name)
            # This will be used to generate consistent entity IDs regardless of friendly name changes
            entity_base_slug = desired_name.lower().replace(' ', '_').replace('-', '_').replace('.', '_').replace(':', '_')
            # Remove any double underscores and strip leading/trailing underscores
            entity_base_slug = '_'.join(filter(None, entity_base_slug.split('_')))

            _LOGGER.debug(f"Channel {channel_id} (Cat: {channel_cat}). Type is cover. Using Name: '{desired_name}'. Entity base slug: '{entity_base_slug}'. Creating entity.")
            
            # Type hub_manufacturer and hub_sw_version before use
            hub_manufacturer: str = main_hub_device_info.get("manufacturer", "Feller AG")
            hub_sw_version: str | None = main_hub_device_info.get("sw_version")

            blind_device_info: dict[str, Any] = {
                "identifiers": {(DOMAIN, f"{hub_serial_for_blinds}_ch{channel_id}")}, # set[tuple[str,str]]
                "name": desired_name, 
                "via_device": (DOMAIN, hub_serial_for_blinds), # tuple[str,str]
                "manufacturer": hub_manufacturer, # str
                "sw_version": hub_sw_version, # str | None
            }
            panel_type_string: str = panel_type_mapping.get(channel_cat, "Unknown Panel")
            blind_device_info["model"] = f"Zeptrion Air Channel {channel_id} - {panel_type_string}" # str

            new_entities.append(
                ZeptrionAirBlind(
                        config_entry=entry, 
                        device_info_for_blind_entity=blind_device_info,
                        channel_id=channel_id, # int
                        hub_serial=hub_serial_for_blinds, # str
                        entry_title=hub_entry_title, # str
                        entity_base_slug=entity_base_slug
                    )
                )
    
    if new_entities:
        for entity in new_entities: # entity is ZeptrionAirBlind
            _LOGGER.debug(
                "Preparing to add cover entity: Name: %s, Unique ID: %s",
                entity.name,
                entity.unique_id
            )
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
        #self._attr_has_entity_name = True
        self._attr_name: str = str(name_val) if name_val is not None else f"Channel {channel_id}"
        self._attr_unique_id = f"zapp_{hub_serial}_ch{self._channel_id}"
        
        _LOGGER.debug("ZeptrionAirBlind cover entity initialized:")
        _LOGGER.debug("  Friendly name: '%s'", self._attr_name)
        _LOGGER.debug("  Unique ID: '%s'", self._attr_unique_id)

        self._attr_device_class = CoverDeviceClass.SHUTTER
        
        self._attr_is_closed: bool | None = None
        self._attr_is_opening: bool | None = None
        self._attr_is_closing: bool | None = None
        self._attr_current_cover_position: int | None = None

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
        # Since we don't know the actual state, always return None if position is unknown
        # Or, if we want to be optimistic after a 'close' command, this would change.
        # For now, following the "no reliable position feedback" principle.
        return self._attr_is_closed 

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
        # Zeptrion blinds do not report position.
        return self._attr_current_cover_position

    async def async_open_cover(self) -> None:
        """Open the cover."""
        _LOGGER.debug("Opening blind %s (Channel %s)", self._attr_name, self._channel_id)
        try:
            await self.config_entry.runtime_data.client.async_channel_open(self._channel_id)
            # Optimistic updates (optional, as per instructions)
            # self._attr_is_opening = True
            # self._attr_is_closing = False
            # self._attr_is_closed = False
            # self.async_write_ha_state()
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            _LOGGER.error("API error while opening blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to open blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while opening blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to open blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_close_cover(self) -> None:
        """Close the cover."""
        _LOGGER.debug("Closing blind %s (Channel %s)", self._attr_name, self._channel_id)
        try:
            await self.config_entry.runtime_data.client.async_channel_close(self._channel_id)
            # Optimistic updates (optional)
            # self._attr_is_closing = True
            # self._attr_is_opening = False
            # self._attr_is_closed = False # Assuming it's not fully closed yet
            # self.async_write_ha_state()
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            _LOGGER.error("API error while closing blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to close blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while closing blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to close blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_stop_cover(self) -> None:
        """Stop the cover movement."""
        _LOGGER.debug("Stopping blind %s (Channel %s)", self._attr_name, self._channel_id)
        try:
            await self.config_entry.runtime_data.client.async_channel_stop(self._channel_id)
            # Optimistic updates (optional)
            # self._attr_is_opening = False
            # self._attr_is_closing = False
            # self.async_write_ha_state()
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            _LOGGER.error("API error while stopping blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to stop blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while stopping blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to stop blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_open_cover_tilt(self) -> None:
        """Tilt the cover open."""
        _LOGGER.debug("Tilting open blind %s (Channel %s)", self._attr_name, self._channel_id)
        step_duration_ms = self.config_entry.data.get(CONF_STEP_DURATION_MS, DEFAULT_STEP_DURATION_MS)
        try:
            await self.config_entry.runtime_data.client.async_channel_move_close(self._channel_id, time_ms=step_duration_ms)
            # No optimistic state updates for tilt for now, similar to open/close.
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            _LOGGER.error("API error while tilting open blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to tilt open blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while tilting open blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to tilt open blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    async def async_close_cover_tilt(self) -> None:
        """Tilt the cover closed."""
        _LOGGER.debug("Tilting close blind %s (Channel %s)", self._attr_name, self._channel_id)
        step_duration_ms = self.config_entry.data.get(CONF_STEP_DURATION_MS, DEFAULT_STEP_DURATION_MS)
        try:
            await self.config_entry.runtime_data.client.async_channel_move_open(self._channel_id, time_ms=step_duration_ms)
            # No optimistic state updates for tilt for now.
        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            _LOGGER.error("API error while tilting close blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to tilt close blind {self.name} (Channel {self._channel_id}): An API error occurred. {e}") from e
        except Exception as e:
            _LOGGER.error("Unexpected error while tilting close blind %s (Channel %s): %s", self._attr_name, self._channel_id, e)
            raise HomeAssistantError(f"Failed to tilt close blind {self.name} (Channel {self._channel_id}): An unexpected error occurred. {e}") from e

    # No async_update method as the device does not provide reliable position feedback.
    # State updates would be optimistic if implemented in open/close/stop.
    # Or, a periodic poll of /zrap/chscan could be done, but it only returns -1 for blinds.
    # If we were to use optimistic state:
    # After async_open_cover: self._attr_is_closed = False
    # After async_close_cover: Once movement is assumed complete: self._attr_is_closed = True
    # However, without knowing duration, this is tricky.
    # Keeping it simple as per "no reliable position feedback".
    # `is_closed` will remain None if `current_cover_position` is None.
    # If we want to strictly adhere to CoverEntity:
    # `is_closed` should be True if position is 0, False if > 0, None if position is None.
    # Let's assume for now:
    # - Commands are fire-and-forget.
    # - `is_closed` and `current_cover_position` remain `None` as their true state is unknown.
    # This matches the API's limitation where `/zrap/chscan` returns -1 (unknown) for blinds.
    # If an optimistic state is desired, `is_closed` would be set after a presumed duration
    # or immediately (e.g., `self._attr_is_closed = False` on open, `True` on close after delay).
    # For now, the properties will just return their initialized values.
    # The current implementation of `is_closed` returning `self._attr_is_closed` (which is init to None)
    # correctly reflects the unknown state.

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass() 
                                            
        platform: entity_platform.EntityPlatform | None = entity_platform.async_get_current_platform()

        if platform:
            platform.async_register_entity_service(
                SERVICE_BLIND_RECALL_S1,
                {},
                self.async_blind_recall_s1.__name__ # "async_blind_recall_s1"
            )
            platform.async_register_entity_service(
                SERVICE_BLIND_RECALL_S2,
                {},
                self.async_blind_recall_s2.__name__ # "async_blind_recall_s2"
            )
            platform.async_register_entity_service(
                SERVICE_BLIND_RECALL_S3,
                {},
                self.async_blind_recall_s3.__name__ # "async_blind_recall_s3"
            )
            platform.async_register_entity_service(
                SERVICE_BLIND_RECALL_S4,
                {},
                self.async_blind_recall_s4.__name__ 
            )
        else:
            _LOGGER.warning("Entity platform not available for %s, services not registered.", self.entity_id)

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

