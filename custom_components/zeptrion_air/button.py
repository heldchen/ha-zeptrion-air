from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.button import ButtonEntity

from .const import (
    DOMAIN, 
    SERVICE_BLIND_RECALL_S1, 
    SERVICE_BLIND_RECALL_S2, 
    SERVICE_BLIND_RECALL_S3, 
    SERVICE_BLIND_RECALL_S4,
)
from .api import ZeptrionAirApiClientError, ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClient
from .data import ZeptrionAirConfigEntry
from .entity import ZeptrionAirEntity

_LOGGER = logging.getLogger(__name__)

# Define action types and their corresponding labels and service names
BUTTON_ACTIONS: list[dict[str, str]] = [
    {"type": "blind_recall_s1", "label": "Scene S1", "service": SERVICE_BLIND_RECALL_S1, "icon": "mdi:numeric-1-box-outline"},
    {"type": "blind_recall_s2", "label": "Scene S2", "service": SERVICE_BLIND_RECALL_S2, "icon": "mdi:numeric-2-box-outline"},
    {"type": "blind_recall_s3", "label": "Scene S3", "service": SERVICE_BLIND_RECALL_S3, "icon": "mdi:numeric-3-box-outline"},
    {"type": "blind_recall_s4", "label": "Scene S4", "service": SERVICE_BLIND_RECALL_S4, "icon": "mdi:numeric-4-box-outline"},
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZeptrionAirConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zeptrion Air button entities from a config entry."""
    _LOGGER.info("Setting up Zeptrion Air button entities.")
    data = entry.runtime_data

    identified_channels_list = data.identified_channels

    new_entities: list[ZeptrionAirActionButton] = []
    for channel_info_dict in identified_channels_list:
        device_type: str | None = channel_info_dict.get('device_type')
        channel_id_maybe: int | None = channel_info_dict.get('id')

        if channel_id_maybe is None:
            _LOGGER.debug(f"Skipping channel due to missing id: {channel_info_dict}")
            continue
        channel_id: int = channel_id_maybe

        if device_type == "cover":
            for action_def in BUTTON_ACTIONS:
                new_entities.append(
                    ZeptrionAirActionButton(
                        entry=entry,
                        channel_id=channel_id,
                        action_type=action_def["service"], 
                        action_label=action_def["label"],
                        action_type_slug=action_def["type"],
                        icon=action_def["icon"]
                    )
                )
        else:
            _LOGGER.debug("Skipping channel %s for buttons, not a cover.", channel_id_maybe)
            
    if new_entities:
        _LOGGER.info("Adding %s Zeptrion Air button entities.", len(new_entities))
        async_add_entities(new_entities)
    else:
        _LOGGER.info("No Zeptrion Air button entities to add.")

class ZeptrionAirActionButton(ZeptrionAirEntity, ButtonEntity):
    """Representation of a Zeptrion Air action button for a cover channel."""

    _attr_should_poll = False

    def __init__(
        self,
        entry: ZeptrionAirConfigEntry,
        channel_id: int,
        action_type: str, 
        action_label: str,
        action_type_slug: str,
        icon: str, 
    ) -> None:
        """Initialize the Zeptrion Air action button."""
        super().__init__(entry.runtime_data.coordinator, channel_id)
        self.config_entry = entry
        self._channel_id = channel_id
        self._action_type = action_type
        
        self._attr_name = action_label
        self._attr_unique_id = f"{self._attr_unique_id}_{action_type_slug}"
        self._attr_icon = icon

        _LOGGER.debug(
            "Button __init__ for action '%s' on channel %s",
            self._action_type, self._channel_id
        )

    async def async_press(self) -> None:
        """Handle the button press by making a direct API call."""
        _LOGGER.debug(
            "Button '%s' pressed for action type '%s' on channel %s.",
            self.name, self._action_type, self._channel_id
        )
        
        client: ZeptrionAirApiClient = self.config_entry.runtime_data.client

        try:
            if self._action_type == SERVICE_BLIND_RECALL_S1:
                await client.async_channel_recall_s1(self._channel_id)
            elif self._action_type == SERVICE_BLIND_RECALL_S2:
                await client.async_channel_recall_s2(self._channel_id)
            elif self._action_type == SERVICE_BLIND_RECALL_S3:
                await client.async_channel_recall_s3(self._channel_id)
            elif self._action_type == SERVICE_BLIND_RECALL_S4:
                await client.async_channel_recall_s4(self._channel_id)
            else:
                _LOGGER.warning(
                    "Button '%s' pressed with unhandled action type '%s' for channel %s.",
                    self.name, self._action_type, self._channel_id
                )
                return

            _LOGGER.info(
                "Successfully executed action '%s' for button '%s' on channel %s.",
                self._action_type, self.name, self._channel_id
            )

        except (ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClientError) as e:
            _LOGGER.error(
                "API error executing action '%s' for button '%s' on channel %s: %s",
                self._action_type, self.name, self._channel_id, e
            )
            raise HomeAssistantError(f"Failed to execute action {self._action_type} for button {self.name}: An API error occurred. {e}") from e
        except Exception as e:
            _LOGGER.error(
                "Unexpected error executing action '%s' for button '%s' on channel %s: %s",
                self._action_type, self.name, self._channel_id, e
            )
            raise HomeAssistantError(f"Failed to execute action {self._action_type} for button {self.name}: An unexpected error occurred. {e}") from e
