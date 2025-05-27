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
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_FLASH, ATTR_RGB_COLOR,
    ATTR_TRANSITION, ATTR_XY_COLOR, EFFECT_COLORLOOP, EFFECT_RANDOM,
    FLASH_LONG, FLASH_SHORT, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_FLASH, SUPPORT_RGB_COLOR,
    SUPPORT_TRANSITION, SUPPORT_XY_COLOR, Light)
from homeassistant.const import CONF_HOST, CONF_NAME
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity as entity_helper
from homeassistant.components.light import ENTITY_ID_FORMAT as LIGHT_ENTITY_ID_FORMAT
from homeassistant.components.group import ENTITY_ID_FORMAT as GROUP_ENTITY_ID_FORMAT

import custom_components.zeptrionairhub as zeptrionairhub

REQUIREMENTS = ['zeptrionAirApi']

_LOGGER = logging.getLogger(__name__)

DATA_ZEPTRIONAIRHUB = 'ZeptrionAirHub'
DEFAULT_GROUP_NAME = 'Zeptrion Lights no Group'

def setup_platform(hass, config, add_devices, discovery_info=None):
    hub = hass.data[zeptrionairhub.DATA_ZEPTRIONAIRHUB]

    # add_devices(ZeptrionLightChannel(light) for light in hub.get_all_light_channels())
    group_names_with_enitities = {}
    lights = []

    for light in hub.get_all_light_channels():
        temp_light = ZeptrionLightChannel(light, hass)
        lights.append(temp_light)

        # get Groups Info
        group_name = light.channel_group
        entity_id = entity_helper.generate_entity_id(LIGHT_ENTITY_ID_FORMAT, temp_light.name, hass=hass)
        if not group_name:
            group_name = DEFAULT_GROUP_NAME
        if group_name not in group_names_with_enitities:
            group_names_with_enitities[group_name] = []
        group_names_with_enitities[group_name].append(entity_id)

    add_devices(lights)

    """
    # creates the group
    sup_group_entities = []
    for group_name in group_names_with_enitities:
        entity_id = entity_helper.generate_entity_id(GROUP_ENTITY_ID_FORMAT, group_name, hass=hass)
        sup_group_entities.append(entity_id)
        dictSubGroup = {}
        dictSubGroup['object_id'] = entity_id.partition('group.')[2]
        dictSubGroup['name'] = group_name
        dictSubGroup['view'] = False
        dictSubGroup['visible'] = True
        dictSubGroup['add_entities'] = group_names_with_enitities[group_name]
        hass.services.call("group", "set", dictSubGroup)

    dictMainGroup = {}
    dictMainGroup['object_id'] = "zeptrion_air_lights"
    dictMainGroup['name'] = "Zeptrion Lights"
    dictMainGroup['view'] = True
    dictMainGroup['visible'] = True
    dictMainGroup['add_entities'] = sup_group_entities
    hass.services.call("group", "set", dictMainGroup)  
    """

class ZeptrionLightChannel(Light):
    
    def __init__(self, light, hass):
        """Initialize an AwesomeLight."""
        self._light = light
        self._state = None
        self.hass = hass
    
    @property
    def unique_id(self):
        """Return the ID of this Zeptrion light."""
        # self._light.channel_uniq_id
        return str(self._light.panel_name)+str(self._light.channel_id)
    
    @property
    def name(self):
        """Return the display name of this light."""
        return self._light.channel_name

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._light.channel_blind_state

    def turn_on(self, **kwargs):
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """
        #self.brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._light.light_controller.turn_on_light()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.light_controller.turn_off_light()

    def TOGGLE(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.light_controller.toggle_light()

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._state = self._light.light_controller.update()
    
    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        attributes['is_zeptrion_group'] = True
        attributes['group'] = self._light.channel_group
        attributes['zeptrion_channel_cat'] = self._light.channel_cat
        attributes['zeptrion_panel_ip'] = self._light.panel_ip
        return attributes