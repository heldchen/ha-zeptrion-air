"""
Supports the Zeptrion Air Devices.

Version V.0.0.1

Package:
    custom_components.zeptrionairhub.py
    custom_components.light.zeptrionairhub.py
    custom_components.cover.zeptrionairhub.py

configuration.yaml:
    zeptrionairhub:

ToDo:

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/homeassistant_custome_components
"""
import logging

import voluptuous as vol

# Import the device class from the component that you want to support
from homeassistant.components.cover import (
    CoverDevice, SUPPORT_OPEN, SUPPORT_CLOSE, ATTR_POSITION,
    ATTR_TILT_POSITION, SUPPORT_CLOSE, SUPPORT_CLOSE_TILT, SUPPORT_OPEN_TILT, SUPPORT_STOP_TILT,
    SUPPORT_OPEN, SUPPORT_SET_POSITION, SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP)
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity as entity_helper
from homeassistant.components.cover import ENTITY_ID_FORMAT as COVER_ENTITY_ID_FORMAT
from homeassistant.components.group import ENTITY_ID_FORMAT as GROUP_ENTITY_ID_FORMAT

import custom_components.zeptrionairhub as zeptrionairhub

REQUIREMENTS = ['zeptrionAirApi']

_LOGGER = logging.getLogger(__name__)

DATA_ZEPTRIONAIRHUB = 'ZeptrionAirHub'
DEFAULT_GROUP_NAME = 'Zeptrion Blinds no Group'

def setup_platform(hass, config, add_devices, discovery_info=None):
    hub = hass.data[zeptrionairhub.DATA_ZEPTRIONAIRHUB]

    #add_devices(ZeptrionLBlindChannel(blind, hass) for blind in hub.get_all_channels_by_cat(5))

    
    group_names_with_enitities = {}
    blinds = []

    for blind in hub.get_all_channels_by_cat(5):
        temp_blind = ZeptrionLBlindChannel(blind, hass)
        blinds.append(temp_blind)

        # get Groups Info
        group_name = blind.channel_group
        entity_id = entity_helper.generate_entity_id(COVER_ENTITY_ID_FORMAT, temp_blind.name, hass=hass)
        if not group_name:
            group_name = DEFAULT_GROUP_NAME
        if group_name not in group_names_with_enitities:
            group_names_with_enitities[group_name] = []
        group_names_with_enitities[group_name].append(entity_id)

    add_devices(blinds)

    # creates the group
    # sup_group_entities = []
    # for group_name in group_names_with_enitities:
    #     entity_id = entity_helper.generate_entity_id(GROUP_ENTITY_ID_FORMAT, group_name, hass=hass)
    #     sup_group_entities.append(entity_id)
    #     dictSubGroup = {}
    #     dictSubGroup['object_id'] = entity_id.partition('group.')[2]
    #     dictSubGroup['name'] = "Stube"
    #     dictSubGroup['view'] = False
    #     dictSubGroup['visible'] = True
    #     dictSubGroup['add_entities'] = group_names_with_enitities[group_name]
    #     hass.services.call("group", "set", dictSubGroup)

    # dictMainGroup = {}
    # dictMainGroup['object_id'] = "zeptrion_air_blinds"
    # dictMainGroup['name'] = "Zeptrion Blinds"
    # dictMainGroup['view'] = True
    # dictMainGroup['visible'] = True
    # dictMainGroup['add_entities'] = sup_group_entities
    # hass.services.call("group", "set", dictMainGroup)  


class ZeptrionLBlindChannel(CoverDevice):
    
    def __init__(self, blind, hass):
        """Initialize an AwesomeLight."""
        self._blind = blind
        self._state = False
        self.hass = hass
        #super.hass.services.call("light", "toggle", {"entity_id": "light.esszimmer"})

    @property
    def should_poll(self):
        """No polling needed."""
        return False
    
    @property
    def name(self):
        """Return the display name of this light."""
        return self._blind.channel_name
    
    @property
    def unique_id(self):
        """Return the ID of this Zeptrion light."""
        # self._light.channel_uniq_id
        return str(self._blind.panel_name)+str(self._blind.channel_id)

    @property
    def is_closed(self):
        """..."""
        return self._state
    
    @property
    def supported_features(self):
        """Flag supported features."""
        return (SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_STOP)
        # return (SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_STOP | SUPPORT_CLOSE_TILT | SUPPORT_OPEN_TILT | SUPPORT_STOP_TILT)
    
    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'window'
    
    def close_cover(self, **kwargs):
        """..."""
        self._blind.blind_controller.move_down_blind()

    def open_cover(self, **kwargs):
        """..."""
        self._blind.blind_controller.move_up_blind()

    def stop_cover(self, **kwargs):
        """..."""
        self._blind.blind_controller.stop_blind()

    def open_cover_tilt(self, **kwargs):
        """..."""
        self._blind.blind_controller.tilt_up_blind()

    def close_cover_tilt(self, **kwargs):
        """..."""
        self._blind.blind_controller.tilt_down_blind()

    def stop_cover_tilt(self, **kwargs):
        """..."""
        self._blind.blind_controller.stop_blind()

    def set_cover_position(self, **kwargs):
        """..."""
        position = kwargs.get(ATTR_POSITION)
        self._blind.blind_controller.go_to_position(position)
        # self._blind.move_up_blind()

    @property
    def current_cover_position(self):
        return self._blind.channel_blind_state

    @property
    def current_cover_tilt_position(self):
        return None

    #def set_cover_tilt_position(self, **kwargs):
    #    """..."""
    #    tilt_position = kwargs.get(ATTR_TILT_POSITION)
    #    # self._blind.move_up_blind()

    #def update(self):
    #    """Fetch new state data for this light.

    #    This is the only method that should fetch new data for Home Assistant.
    #    """
    #    self._blind.blind_controller.stop_blind()
    #    self._state = False
    
    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        attributes['assumed_state'] = True
        attributes['is_zeptrion_group'] = True
        attributes['group'] = self._blind.channel_group
        attributes['zeptrion_channel_icon'] = self._blind.channel_icon
        attributes['zeptrion_channel_type'] = self._blind.channel_type
        attributes['zeptrion_channel_cat'] = self._blind.channel_cat
        attributes['zeptrion_panel_name'] = self._blind.panel_name
        attributes['zeptrion_panel_type'] = self._blind.panel_type
        attributes['zeptrion_panel_ip'] = self._blind.panel_ip
        return attributes