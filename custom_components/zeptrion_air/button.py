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
    CONF_STEP_DURATION_MS,
    DEFAULT_STEP_DURATION_MS
)
from .api import ZeptrionAirApiClientError, ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClient

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
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zeptrion Air button entities from a config entry."""
    _LOGGER.info("Setting up Zeptrion Air button entities.")
    platform_data: dict[str, Any] | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    if not platform_data:
        _LOGGER.error("button.py: No platform_data found for entry ID %s", entry.entry_id)
        return

    identified_channels_list: list[dict[str, Any]] = platform_data.get("identified_channels", [])
    hub_entry_title: str = platform_data.get("entry_title", "Zeptrion Air Hub")
    hub_serial_maybe: str | None = platform_data.get("hub_serial")

    if not hub_serial_maybe:
        _LOGGER.error("button.py: Hub serial not found in platform_data.")
        return
    hub_serial: str = hub_serial_maybe

    new_entities: list[ZeptrionAirActionButton] = []
    for channel_info_dict in identified_channels_list:
        device_type: str | None = channel_info_dict.get('device_type')
        channel_id_maybe: int | None = channel_info_dict.get('id')

        if channel_id_maybe is None:
            _LOGGER.debug(f"Skipping channel due to missing id: {channel_info_dict}")
            continue
        channel_id: int = channel_id_maybe

        # Get the entity_base_name for display purposes
        parent_device_name_maybe: str | None = channel_info_dict.get("entity_base_name")
        parent_device_name: str = parent_device_name_maybe if parent_device_name_maybe is not None else f"{hub_entry_title} Channel {channel_id}"

        # Create a stable base name for entity IDs (slugified version of entity_base_name)
        # This will be used to generate consistent entity IDs regardless of friendly name changes
        entity_base_slug = parent_device_name.lower().replace(' ', '_').replace('-', '_').replace('.', '_').replace(':', '_')
        # Remove any double underscores and strip leading/trailing underscores
        entity_base_slug = '_'.join(filter(None, entity_base_slug.split('_')))

        if device_type == "cover":
            _LOGGER.debug(f"Found cover channel {channel_id} for buttons. Parent device name: '{parent_device_name}', Entity base slug: '{entity_base_slug}'")
            for action_def in BUTTON_ACTIONS:
                new_entities.append(
                    ZeptrionAirActionButton(
                        config_entry=entry, 
                        hub_entry_title=hub_entry_title,
                        parent_device_name=parent_device_name, 
                        entity_base_slug=entity_base_slug,
                        channel_id=channel_id,
                        hub_serial=hub_serial,
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

class ZeptrionAirActionButton(ButtonEntity):
    """Representation of a Zeptrion Air action button for a cover channel."""

    _attr_should_poll = False

    def __init__(
        self,
        config_entry: ConfigEntry,
        hub_entry_title: str, 
        parent_device_name: str,
        entity_base_slug: str,
        channel_id: int,
        hub_serial: str, 
        action_type: str, 
        action_label: str,
        action_type_slug: str,
        icon: str, 
    ) -> None:
        """Initialize the Zeptrion Air action button."""
        self.config_entry: ConfigEntry = config_entry
        self._hub_serial: str = hub_serial
        self._hub_entry_title: str = hub_entry_title
        self._channel_id: int = channel_id
        self._action_type: str = action_type
        
        self._attr_has_entity_name = True
        self._attr_name: str = f"{action_label}"
        self._attr_unique_id = f"zapp_{self._hub_serial}_ch{self._channel_id}_{action_type_slug}"
        
        #        self._attr_unique_id: str = f"{self._hub_serial}_ch{self._channel_id}_{action_type_slug}_button"
        
        self._attr_icon: str = icon

        _LOGGER.debug(
            "Button __init__ for action '%s' on channel %s for hub_serial '%s' (entry_title: '%s'):",
            self._action_type, self._channel_id, self._hub_serial, self._hub_entry_title
        )
        _LOGGER.debug("  Friendly name: '%s'", self._attr_name)
        _LOGGER.debug("  Unique ID: '%s'", self._attr_unique_id)

        # Link this button to the specific cover channel's device entry in HA
        self._attr_device_info: dict[str, set[tuple[str, str]]] = {
            "identifiers": {(DOMAIN, f"{hub_serial}_ch{channel_id}")},
        }

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
