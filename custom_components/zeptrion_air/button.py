from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.button import ButtonEntity

# Removed TYPE_CHECKING block as it's not currently used for strict typing here.
# If needed later, it can be re-added with specific imports.

from .const import (
    DOMAIN, 
    SERVICE_BLIND_UP_STEP, 
    SERVICE_BLIND_DOWN_STEP, 
    SERVICE_BLIND_RECALL_S1, 
    SERVICE_BLIND_RECALL_S2, 
    SERVICE_BLIND_RECALL_S3, 
    SERVICE_BLIND_RECALL_S4,
    CONF_STEP_DURATION_MS,  # Added import
    DEFAULT_STEP_DURATION_MS # Added import
)
from .api import ZeptrionAirApiClientError, ZeptrionAirApiClientCommunicationError, ZeptrionAirApiClient

_LOGGER = logging.getLogger(__name__)

# Define action types and their corresponding labels and service names
BUTTON_ACTIONS: list[dict[str, str]] = [
    {"type": "short_up", "label": "Short Up", "service": SERVICE_BLIND_UP_STEP, "icon": "mdi:arrow-up-bold-outline"},
    {"type": "short_down", "label": "Short Down", "service": SERVICE_BLIND_DOWN_STEP, "icon": "mdi:arrow-down-bold-outline"},
    {"type": "recall_s1", "label": "Scene S1", "service": SERVICE_BLIND_RECALL_S1, "icon": "mdi:numeric-1-box-outline"},
    {"type": "recall_s2", "label": "Scene S2", "service": SERVICE_BLIND_RECALL_S2, "icon": "mdi:numeric-2-box-outline"},
    {"type": "recall_s3", "label": "Scene S3", "service": SERVICE_BLIND_RECALL_S3, "icon": "mdi:numeric-3-box-outline"},
    {"type": "recall_s4", "label": "Scene S4", "service": SERVICE_BLIND_RECALL_S4, "icon": "mdi:numeric-4-box-outline"},
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

    # api_client = platform_data.get("client")
    identified_channels_list: list[dict[str, Any]] = platform_data.get("identified_channels", [])
    hub_entry_title: str = platform_data.get("entry_title", "Zeptrion Air Hub") # e.g., "zapp-123456"
    hub_serial_maybe: str | None = platform_data.get("hub_serial") # e.g., "123456"

    if not hub_serial_maybe: # hub_entry_title might also be a good check
        _LOGGER.error("button.py: Hub serial not found in platform_data.")
        return
    hub_serial: str = hub_serial_maybe # hub_serial is now effectively str

    new_entities: list[ZeptrionAirActionButton] = []
    for channel_info_dict in identified_channels_list:
        device_type: str | None = channel_info_dict.get('device_type')
        channel_id_maybe: int | None = channel_info_dict.get('id')

        if channel_id_maybe is None:
            _LOGGER.debug(f"Skipping channel due to missing id: {channel_info_dict}")
            continue
        channel_id: int = channel_id_maybe # channel_id is now effectively int

        # Use the detailed name constructed by cover.py if available,
        # or construct a similar one for button parent naming.
        # For now, use the 'name' from channel_info_dict which is group or api_name.
        # This will be refined in Plan Step 5.
        # Example: channel_api_group = channel_info_dict.get('api_group')
        # channel_api_name = channel_info_dict.get('api_name')
        # if channel_api_group and channel_api_name:
        #     parent_cover_base_name = f"{hub_entry_title} {channel_api_group} - {channel_api_name}"
        # elif channel_api_group:
        #     parent_cover_base_name = f"{hub_entry_title} {channel_api_group}"
        # elif channel_api_name:
        #     parent_cover_base_name = f"{hub_entry_title} {api_name}"
        # else:
        #     parent_cover_base_name = f"{hub_entry_title} Channel {channel_id}"
        
        # For now, let's use a simpler name construction that will be improved in Step 5
        # This name is used to form part of the button's friendly name.
        # The cover entity's actual name will be the true "parent name".
        # We need the cover entity's unique_id or entity_id to target services.
        # The cover entity's unique_id is f"{hub_entry_title}-ch{channel_id}"
        
        parent_cover_unique_id = f"{hub_entry_title}-ch{channel_id}" # This is the unique_id of the cover entity
        # The actual entity_id will be derived by HA, e.g., cover.zapp_123456_ch1
        # This construction needs to be robust.
        
        # This construction needs to be robust.
        
        # Use the entity_base_name (constructed in __init__.py) for the parent device name.
        parent_device_name_maybe: str | None = channel_info_dict.get("entity_base_name")
        # Fallback if entity_base_name is somehow not available
        parent_device_name: str = parent_device_name_maybe if parent_device_name_maybe is not None else f"{hub_entry_title} Channel {channel_id}"


        if device_type == "cover": # Buttons are only for cover entities
            _LOGGER.debug(f"Found cover channel {channel_id} for buttons. Parent device name for buttons: '{parent_device_name}'")
            for action_def in BUTTON_ACTIONS:
                new_entities.append(
                    ZeptrionAirActionButton(
                        config_entry=entry, 
                        hub_entry_title=hub_entry_title,
                        parent_device_name=parent_device_name, 
                        channel_id=channel_id, # type is int here
                        hub_serial=hub_serial, # type is str here
                        action_type=action_def["service"], 
                        action_label=action_def["label"],
                        icon=action_def["icon"]
                    )
                )
        else:
            _LOGGER.debug("Skipping channel %s for buttons, not a cover.", channel_id_maybe) # Use maybe here as it might be None
            
    if new_entities:
        _LOGGER.info("Adding %s Zeptrion Air button entities.", len(new_entities))
        async_add_entities(new_entities)
    else:
        _LOGGER.info("No Zeptrion Air button entities to add.")

# The ZeptrionAirActionButton class will be added below this in the next step.
# Replace the placeholder class ZeptrionAirActionButton with this:
class ZeptrionAirActionButton(ButtonEntity):
    """Representation of a Zeptrion Air action button for a cover channel."""

    _attr_should_poll = False # Buttons are stateless actions

    def __init__(
        self,
        config_entry: ConfigEntry, # Using ConfigEntry as ZeptrionAirConfigEntry not defined
        hub_entry_title: str, 
        parent_device_name: str, 
        channel_id: int,
        hub_serial: str, 
        action_type: str, 
        action_label: str, 
        icon: str, 
    ) -> None:
        """Initialize the Zeptrion Air action button."""
        self.config_entry: ConfigEntry = config_entry 
        self._hub_entry_title: str = hub_entry_title 
        self._channel_id: int = channel_id
        self._action_type: str = action_type
        
        # Set attributes before logging them
        self._attr_name: str = f"{parent_device_name} {action_label}"
        # Use a slugified action_label for unique_id to avoid issues with potentially long service names in action_type
        action_label_slug: str = action_label.lower().replace(' ', '_').replace('-', '_')
        self._attr_unique_id: str = f"{self._hub_entry_title}_ch{self._channel_id}_{action_label_slug}_button"
        self._attr_icon: str = icon

        _LOGGER.debug(
            "Button __init__ for action '%s' on channel %s for hub '%s':",
            self._action_type, self._channel_id, self._hub_entry_title
        )
        _LOGGER.debug(
            "  Parent device name: '%s', Action label: '%s'", parent_device_name, action_label
        )
        _LOGGER.debug(
            "  Button's own _attr_name set to: '%s'", self._attr_name
        )
        _LOGGER.debug(
            "  Button's own _attr_unique_id set to: '%s'", self._attr_unique_id
        )

        # Link this button to the specific cover channel's device entry in HA
        # This uses the same identifier as the cover entity for that channel.
        self._attr_device_info: dict[str, set[tuple[str, str]]] = {
            "identifiers": {(DOMAIN, f"{hub_serial}_ch{channel_id}")},
            # "name" and "model" etc. for this device entry are defined by the cover platform.
            # Buttons are just entities associated with that device.
        }

    async def async_press(self) -> None:
        """Handle the button press by making a direct API call."""
        _LOGGER.debug(
            "Button '%s' pressed for action type '%s' on channel %s.",
            self.name, self._action_type, self._channel_id
        )
        
        client: ZeptrionAirApiClient = self.config_entry.runtime_data.client

        try:
            # self._action_type now holds service name strings like SERVICE_BLIND_UP_STEP
            if self._action_type == SERVICE_BLIND_UP_STEP:
                # Prioritize options, then data, then default for step_duration
                step_duration: int = self.config_entry.options.get(
                    CONF_STEP_DURATION_MS,
                    self.config_entry.data.get(CONF_STEP_DURATION_MS, DEFAULT_STEP_DURATION_MS)
                )
                await client.async_channel_move_open(self._channel_id, time_ms=step_duration)
            elif self._action_type == SERVICE_BLIND_DOWN_STEP:
                # Prioritize options, then data, then default for step_duration
                step_duration: int = self.config_entry.options.get(
                    CONF_STEP_DURATION_MS,
                    self.config_entry.data.get(CONF_STEP_DURATION_MS, DEFAULT_STEP_DURATION_MS)
                )
                await client.async_channel_move_close(self._channel_id, time_ms=step_duration)
            elif self._action_type == SERVICE_BLIND_RECALL_S1:
                await client.async_channel_recall_s1(self._channel_id)
            elif self._action_type == SERVICE_BLIND_RECALL_S2:
                await client.async_channel_recall_s2(self._channel_id)
            elif self._action_type == SERVICE_BLIND_RECALL_S3:
                await client.async_channel_recall_s3(self._channel_id)
            elif self._action_type == SERVICE_BLIND_RECALL_S4:
                await client.async_channel_recall_s4(self._channel_id)
            else:
                _LOGGER.warning(
                    "Button '%s' pressed with unhandled action type (service name) '%s' for channel %s.",
                    self.name, self._action_type, self._channel_id
                )
                return # No action to take

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
        except Exception as e: # Catch any other unexpected errors
            _LOGGER.error(
                "Unexpected error executing action '%s' for button '%s' on channel %s: %s",
                self._action_type, self.name, self._channel_id, e
            )
            raise HomeAssistantError(f"Failed to execute action {self._action_type} for button {self.name}: An unexpected error occurred. {e}") from e

