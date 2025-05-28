"""Cover platform for Zeptrion Air."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform # Added import
from homeassistant.helpers.entity_platform import AddEntitiesCallback
# Assuming ZeptrionAirHub will be defined in __init__.py and hold the client & device info
# from . import ZeptrionAirHub
from .api import ZeptrionAirApiClient # Adjusted if ZeptrionAirHub is not used directly here
from .const import ( # Added import for service constants
    DOMAIN,
    SERVICE_BLIND_UP_STEP,
    SERVICE_BLIND_DOWN_STEP,
    SERVICE_BLIND_RECALL_S1,
    SERVICE_BLIND_RECALL_S2,
    SERVICE_BLIND_RECALL_S3,
    SERVICE_BLIND_RECALL_S4,
)
from homeassistant.util import slugify # Added import

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zeptrion Air cover entities from a config entry."""
    platform_data = hass.data[DOMAIN].get(entry.entry_id)

    if not platform_data:
        _LOGGER.error(f"cover.py async_setup_entry: No platform_data found for entry ID {entry.entry_id}")
        return

    _LOGGER.debug(f"cover.py async_setup_entry: Received platform_data: {platform_data}")

    api_client = platform_data.get("client")
    main_hub_device_info = platform_data.get("hub_device_info", {})
    # Retrieve identified_channels instead of blind_channel_ids
    identified_channels_list = platform_data.get("identified_channels", [])
    hub_entry_title = platform_data.get("entry_title", "Zeptrion Air Hub") 
    hub_serial_for_blinds = platform_data.get("hub_serial")

    # Updated logging
    _LOGGER.debug(f"cover.py async_setup_entry: Identified channels list: {identified_channels_list}")

    if not api_client or not hub_serial_for_blinds:
        _LOGGER.error("cover.py async_setup_entry: API client or hub serial not found in platform_data.")
        return

    new_entities = []

    # 1. Define the category to panel type mapping
    panel_type_mapping = {
        5: "Blinds", # Rollladen
        6: "Markise" # Markise/Awning
        # Add other mappings here if other cat values are used for covers in the future
    }

    if identified_channels_list:
        for channel_info_dict in identified_channels_list:
            channel_id = channel_info_dict.get('id')
            channel_cat = channel_info_dict.get('cat')
            device_type = channel_info_dict.get('device_type') # Ensure this is present if used for filtering

            # channel_icon = channel_info_dict.get('icon') # Available if needed

            if channel_id is None or channel_cat is None or device_type != "cover":
                if device_type != "cover" and channel_id is not None : # Log only if it's not a cover channel
                     _LOGGER.debug(f"cover.py: Skipping channel {channel_id} (Cat: {channel_cat}). Not a cover device_type ('{device_type}').")
                else: # Log other skip reasons like missing id or cat
                     _LOGGER.warning(f"cover.py: Skipping channel due to missing id, cat or not being a cover: {channel_info_dict}")
                continue
            
            # Get the entity_base_name from channel_info_dict (provided by __init__.py)
            entity_base_name = channel_info_dict.get("entity_base_name")
            # Fallback if entity_base_name is not found, though it should always be there
            desired_name = entity_base_name if entity_base_name else f"{hub_entry_title} Channel {channel_id}"

            _LOGGER.debug(f"cover.py: Channel {channel_id} (Cat: {channel_cat}). Type is cover. Using Name: '{desired_name}'. Creating entity.")
            
            blind_device_info = {
                "identifiers": {(DOMAIN, f"{hub_serial_for_blinds}_ch{channel_id}")},
                "name": desired_name, # Use the name from entity_base_name
                "via_device": (DOMAIN, hub_serial_for_blinds), 
                "manufacturer": main_hub_device_info.get("manufacturer", "Feller AG"),
                "sw_version": main_hub_device_info.get("sw_version"),
                # "suggested_area": can be explored if needed
            }
            panel_type_string = panel_type_mapping.get(channel_cat, "Unknown Panel")
            blind_device_info["model"] = f"Zeptrion Air Channel {channel_id} - {panel_type_string}"

            new_entities.append(
                ZeptrionAirBlind(
                        api_client=api_client,
                        device_info_for_blind_entity=blind_device_info,
                        channel_id=channel_id,
                        hub_serial=hub_serial_for_blinds, 
                        entry_title=hub_entry_title # Hub's name/title for context, used for unique_id
                    )
                )
            # No explicit else needed here because the initial `if` condition
            # `device_type != "cover"` already handles non-cover channels.
    
    if new_entities:
        for entity in new_entities:
            _LOGGER.debug(
                "Preparing to add cover entity: Name: %s, Unique ID: %s",
                entity.name, # Using property entity.name
                entity.unique_id # Using property entity.unique_id
            )
        _LOGGER.info("Adding %s ZeptrionAirBlind cover entities.", len(new_entities))
        async_add_entities(new_entities)
    else:
        _LOGGER.info("No Zeptrion Air cover entities to add.") # Changed to info as per prompt
    
    _LOGGER.info("cover.py: async_setup_entry completed successfully.")
    return True # Explicitly return True for successful setup


class ZeptrionAirBlind(CoverEntity):
    """Representation of a Zeptrion Air Blind."""

    def __init__(
        self,
        api_client: ZeptrionAirApiClient,
        device_info_for_blind_entity: dict[str, Any], # Specific device_info for this blind
        channel_id: int,
        hub_serial: str, # Serial number of the parent hub
        entry_title: str, # Name/title of the parent hub (e.g. "Living Room Zeptrion")
    ) -> None:
        """Initialize the Zeptrion Air blind."""
        self._api_client = api_client
        self._channel_id = channel_id
        self._attr_has_entity_name = True # Set as per requirement
        
        self._attr_device_info = device_info_for_blind_entity
        # The name of the entity itself (e.g., "Living Room Zeptrion Blind Ch1")
        # This is the "entity name" part if _attr_has_entity_name is True.
        # The device name comes from hub_device_info["name"] via async_setup_entry.
        self._attr_name = device_info_for_blind_entity["name"] 
        
        # The unique_id for the entity, using entry_title (hub's name) and channel_id
        self._attr_unique_id = f"{entry_title}-ch{self._channel_id}"
        
        # Construct and set the object_id
        slugified_hub_name = slugify(entry_title)
        desired_object_id = f"{slugified_hub_name}_ch{self._channel_id}"
        self._attr_object_id = desired_object_id
        
        # Detailed debug log after all relevant attributes are set
        _LOGGER.debug(
            "ZeptrionAirBlind init: Name='%s', UniqueID='%s', AttrObjectID='%s', PropertyObjectID='%s'",
            self._attr_name,
            self._attr_unique_id,
            self._attr_object_id,
            self.object_id  # This calls the object_id property
        )

        self._attr_is_closed: bool | None = None  # Position is unknown
        self._attr_is_opening: bool = False
        self._attr_is_closing: bool = False
        self._attr_current_cover_position: int | None = None # Position is unknown

        # Zeptrion API does not provide position feedback for blinds.
        # supported_features will not include SET_POSITION.
        self._attr_supported_features = (
            CoverEntityFeature.OPEN |
            CoverEntityFeature.CLOSE |
            CoverEntityFeature.STOP
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
            await self._api_client.async_channel_open(self._channel_id)
            # Optimistic updates (optional, as per instructions)
            # self._attr_is_opening = True
            # self._attr_is_closing = False
            # self._attr_is_closed = False
            # self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to open blind %s: %s", self._attr_name, e)


    async def async_close_cover(self) -> None:
        """Close the cover."""
        _LOGGER.debug("Closing blind %s (Channel %s)", self._attr_name, self._channel_id)
        try:
            await self._api_client.async_channel_close(self._channel_id)
            # Optimistic updates (optional)
            # self._attr_is_closing = True
            # self._attr_is_opening = False
            # self._attr_is_closed = False # Assuming it's not fully closed yet
            # self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to close blind %s: %s", self._attr_name, e)

    async def async_stop_cover(self) -> None:
        """Stop the cover movement."""
        _LOGGER.debug("Stopping blind %s (Channel %s)", self._attr_name, self._channel_id)
        try:
            await self._api_client.async_channel_stop(self._channel_id)
            # Optimistic updates (optional)
            # self._attr_is_opening = False
            # self._attr_is_closing = False
            # self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to stop blind %s: %s", self._attr_name, e)

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
        await super().async_added_to_hass() # CoverEntity base class does not have this,
                                            # but good practice if a future intermediate class does.

        platform = entity_platform.async_get_current_platform()

        platform.async_register_entity_service(
            SERVICE_BLIND_UP_STEP,
            {}, # No service call schema
            self.async_blind_up_step.__name__ # Method name string "async_blind_up_step"
        )
        platform.async_register_entity_service(
            SERVICE_BLIND_DOWN_STEP,
            {},
            self.async_blind_down_step.__name__ # "async_blind_down_step"
        )
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
            self.async_blind_recall_s4.__name__ # "async_blind_recall_s4"
        )

    async def async_blind_up_step(self) -> None:
        """Move the blind up by a step (default 500ms)."""
        _LOGGER.debug("Stepping up blind %s (Channel %s)", self.name, self._channel_id)
        try:
            await self._api_client.async_channel_move_open(self._channel_id) # Uses default 500ms
        except Exception as e:
            _LOGGER.error("Failed to step up blind %s: %s", self.name, e)

    async def async_blind_down_step(self) -> None:
        """Move the blind down by a step (default 500ms)."""
        _LOGGER.debug("Stepping down blind %s (Channel %s)", self.name, self._channel_id)
        try:
            await self._api_client.async_channel_move_close(self._channel_id) # Uses default 500ms
        except Exception as e:
            _LOGGER.error("Failed to step down blind %s: %s", self.name, e)

    async def async_blind_recall_s1(self) -> None:
        """Recall scene S1 for the blind."""
        _LOGGER.debug("Recalling S1 for blind %s (Channel %s)", self.name, self._channel_id)
        try:
            await self._api_client.async_channel_recall_s1(self._channel_id)
        except Exception as e:
            _LOGGER.error("Failed to recall S1 for blind %s: %s", self.name, e)

    async def async_blind_recall_s2(self) -> None:
        """Recall scene S2 for the blind."""
        _LOGGER.debug("Recalling S2 for blind %s (Channel %s)", self.name, self._channel_id)
        try:
            await self._api_client.async_channel_recall_s2(self._channel_id)
        except Exception as e:
            _LOGGER.error("Failed to recall S2 for blind %s: %s", self.name, e)

    async def async_blind_recall_s3(self) -> None:
        """Recall scene S3 for the blind."""
        _LOGGER.debug("Recalling S3 for blind %s (Channel %s)", self.name, self._channel_id)
        try:
            await self._api_client.async_channel_recall_s3(self._channel_id)
        except Exception as e:
            _LOGGER.error("Failed to recall S3 for blind %s: %s", self.name, e)

    async def async_blind_recall_s4(self) -> None:
        """Recall scene S4 for the blind."""
        _LOGGER.debug("Recalling S4 for blind %s (Channel %s)", self.name, self._channel_id)
        try:
            await self._api_client.async_channel_recall_s4(self._channel_id)
        except Exception as e:
            _LOGGER.error("Failed to recall S4 for blind %s: %s", self.name, e)
