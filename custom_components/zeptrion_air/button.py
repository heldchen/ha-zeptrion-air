from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.button import ButtonEntity # Add this import

if TYPE_CHECKING:
    # Import your data coordinator and API client if they are typed in hass.data
    # For now, we'll assume they are not strictly typed here for simplicity in this step
    pass

from .const import DOMAIN, SERVICE_BLIND_UP_STEP, SERVICE_BLIND_DOWN_STEP, SERVICE_BLIND_RECALL_S1, SERVICE_BLIND_RECALL_S2, SERVICE_BLIND_RECALL_S3, SERVICE_BLIND_RECALL_S4 
# ZeptrionAirActionButton will be defined in the same file, later in the plan.

_LOGGER = logging.getLogger(__name__)

# Define action types and their corresponding labels and service names
BUTTON_ACTIONS = [
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
    platform_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    if not platform_data:
        _LOGGER.error("button.py: No platform_data found for entry ID %s", entry.entry_id)
        return

    # api_client = platform_data.get("client") # Not directly used by async_setup_entry for buttons if buttons call services
    identified_channels_list = platform_data.get("identified_channels", [])
    hub_entry_title = platform_data.get("entry_title", "Zeptrion Air Hub") # e.g., "zapp-123456"
    hub_serial = platform_data.get("hub_serial") # e.g., "123456"

    if not hub_serial: # hub_entry_title might also be a good check
        _LOGGER.error("button.py: Hub serial not found in platform_data.")
        return

    new_entities = []
    for channel_info_dict in identified_channels_list:
        device_type = channel_info_dict.get('device_type')
        channel_id = channel_info_dict.get('id')

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
        parent_device_name = channel_info_dict.get("entity_base_name")
        # Fallback if entity_base_name is somehow not available
        parent_device_name = parent_device_name if parent_device_name else f"{hub_entry_title} Channel {channel_id}"


        if device_type == "cover": # Buttons are only for cover entities
            _LOGGER.debug(f"Found cover channel {channel_id} for buttons. Parent device name for buttons: '{parent_device_name}'")
            for action_def in BUTTON_ACTIONS:
                new_entities.append(
                    ZeptrionAirActionButton(
                        hass=hass, # Pass hass
                        hub_entry_title=hub_entry_title, 
                        parent_device_name=parent_device_name, # Use the resolved name
                        channel_id=channel_id,
                        hub_serial=hub_serial, # Needed for device_info linking
                        action_type=action_def["type"],
                        action_label=action_def["label"],
                        service_to_call=action_def["service"],
                        icon=action_def["icon"],
                        parent_cover_unique_id=parent_cover_unique_id 
                    )
                )
        else:
            _LOGGER.debug("Skipping channel %s for buttons, not a cover.", channel_id)
            
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
        hass: HomeAssistant,
        hub_entry_title: str, # e.g., "zapp-123456"
        parent_device_name: str, # The friendly name of the cover device, e.g., "zapp-123456 Office Blinds"
        channel_id: int,
        hub_serial: str, # Serial of the main hub, e.g., "123456"
        action_type: str, # e.g., "short_up", "recall_s1"
        action_label: str, # e.g., "Short Up", "Scene S1"
        service_to_call: str, # e.g., SERVICE_BLIND_UP_STEP
        icon: str, # mdi icon string
        parent_cover_unique_id: str # The unique_id of the parent cover entity, e.g. "{hub_entry_title}-ch{channel_id}"
    ) -> None:
        """Initialize the Zeptrion Air action button."""
        self.hass = hass
        self._hub_entry_title = hub_entry_title # Used for unique ID construction
        self._channel_id = channel_id
        self._action_type = action_type
        self._service_to_call = service_to_call
        
        # Construct the entity_id of the parent cover.
        # This assumes HA's default slugification (lowercase, hyphen to underscore).
        # parent_cover_unique_id is like "zapp-123456-ch1"
        # Entity ID would be like "cover.zapp_123456_ch1"
        slugified_parent_unique_id = parent_cover_unique_id.replace('-', '_').lower()
        self._parent_cover_entity_id = f"cover.{slugified_parent_unique_id}"
        
        # Set attributes before logging them
        self._attr_name = f"{parent_device_name} {action_label}"
        self._attr_unique_id = f"{self._hub_entry_title}_ch{self._channel_id}_{self._action_type}_button"
        self._attr_icon = icon

        # Enhanced logging as per plan
        _LOGGER.debug(
            "Button __init__ for action '%s' on channel %s for hub '%s':",
            self._action_type,
            self._channel_id,
            self._hub_entry_title 
        )
        _LOGGER.debug(
            "  Parent device name: '%s', Action label: '%s'",
            parent_device_name, action_label
        )
        _LOGGER.debug(
            "  Received parent_cover_unique_id: '%s'", parent_cover_unique_id
        )
        _LOGGER.debug(
            "  Constructed _parent_cover_entity_id (target for service call): '%s'", self._parent_cover_entity_id
        )
        _LOGGER.debug(
            "  Button's own _attr_name set to: '%s'", self._attr_name 
        )
        _LOGGER.debug(
            "  Button's own _attr_unique_id set to: '%s'", self._attr_unique_id 
        )

        # Link this button to the specific cover channel's device entry in HA
        # This uses the same identifier as the cover entity for that channel.
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{hub_serial}_ch{channel_id}")},
            # "name" and "model" etc. for this device entry are defined by the cover platform.
            # Buttons are just entities associated with that device.
        }

    async def async_press(self) -> None:
        """Handle the button press by calling the respective service on the parent cover entity."""
        _LOGGER.debug(
            "Button '%s' pressed, calling service '%s' on entity '%s'",
            self.name,
            self._service_to_call,
            self._parent_cover_entity_id
        )
        try:
            await self.hass.services.async_call(
                DOMAIN, # zeptrion_air domain
                self._service_to_call,
                {"entity_id": self._parent_cover_entity_id},
                blocking=True # Wait for service to complete
            )
        except Exception as e:
            _LOGGER.error(
                "Error calling service %s for button %s on entity %s: %s",
                self._service_to_call,
                self.name,
                self._parent_cover_entity_id,
                e
            )
