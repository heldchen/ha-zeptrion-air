"""
Merges Zeptrion Lights together with Hue Lights in one new Light.

Version V.0.0.1

Package:
    custom_components.light.zeptrion_hue_lights.py

configuration.yaml:
    light:
        - platform: zeptrion_hue_lights
            mappings:
                # Name: [zeptrion_entity_name, hue_entity_name, group_name]
                "Licht Küche": [light.kueche_kueche_2, light.kueche_kueche, 'Kueche']
                "Licht Stube": [light.stube_stube_2, light.stube_stube, 'Stube']
            scan_interval: 1

ToDo:

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/homeassistant_custome_components
"""
import logging

# Import the device class from the component that you want to support
from homeassistant.components.light import Light
from homeassistant.components.group import ENTITY_ID_FORMAT as GROUP_ENTITY_ID_FORMAT
import homeassistant.helpers.entity as entity_helper

REQUIREMENTS = ['zeptrionAirApi']
DEPENDENCIES = ['zeptrionairhub','hue']

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices, discovery_info=None):
    lights = []
    
    mappings = config.get('mappings')
    for key in mappings:
        name = key
        zeptrion_entity = mappings[key][0]
        hue_entity = mappings[key][1]
        group_name = mappings[key][2]
        entity_id = entity_helper.generate_entity_id(GROUP_ENTITY_ID_FORMAT, group_name, hass=hass)
        lights.append(ZeptrionHueLights(name, entity_id, group_name, zeptrion_entity, hue_entity, hass))
    add_devices(lights) 

class ZeptrionHueLights(Light):
    
    def __init__(self, name, group, friendly_group_name, zeptrion_entity, hue_entity, hass):
        """Initialize an AwesomeLight."""
        self._zeptrion_entity = zeptrion_entity
        self._hue_entity = hue_entity
        self._name = name
        self._state_hue = None
        self._state_zeptrion = None
        self.hass = hass
        self._group = group
        self._friendly_group_name = friendly_group_name 

    
    @property
    def unique_id(self):
        """Return the ID of this Zeptrion light."""
        return self._zeptrion_entity + self._hue_entity
    
    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of the light."""
        temp_param = 'brightness'
        return self._get_return_value(temp_param, self._state_hue)

    @property
    def xy_color(self):
        """Return the XY color value."""
        temp_param = 'xy_color'
        return self._get_return_value(temp_param, self._state_hue)

    @property
    def color_temp(self):
        """Return the CT color value."""
        temp_param = 'color_temp'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def supported_features(self):
        """Flag supported features."""
        temp_param = 'supported_features'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def effect_list(self):
        """Return the list of supported effect_list."""
        temp_param = 'effect_list'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def rgb_color(self):
        """Return the list of supported rgb_color."""
        temp_param = 'rgb_color'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def min_mireds(self):
        """Return the list of supported min_mireds."""
        temp_param = 'min_mireds'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def max_mireds(self):
        """Return the list of supported max_mireds."""
        temp_param = 'max_mireds'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def effect(self):
        """Return the list of supported effects."""
        temp_param = 'effect'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def brightness_pct(self):
        """Return the list of supported brightness_pct."""
        temp_param = 'brightness_pct'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def kelvin(self):
        """Return the list of supported kelvin."""
        temp_param = 'kelvin'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def flash(self):
        """Return the list of supported flash."""
        temp_param = 'flash'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def white_value(self):
        """Return the list of supported white_value."""
        temp_param = 'white_value'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def profile(self):
        """Return the list of supported profile."""
        temp_param = 'profile'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def transition(self):
        """Return the list of supported transition."""
        temp_param = 'transition'
        return self._get_return_value(temp_param, self._state_hue)
    
    @property
    def last_updated(self):
        """Return the list of supported effects."""
        if self._state_hue and self._state_hue.last_updated:
            return self._state_hue.last_updated
        return None
    
    @property
    def last_changed(self):
        """Return the list of supported last_changed."""
        if self._state_hue and self._state_hue.attributes:
            return self._state_hue.last_changed
        return None

    @property
    def is_on(self):
        """Return true if light is on."""
        # if zeptrion is off --> return False
        if self._state_zeptrion and self._state_zeptrion.state and self._state_zeptrion.state == 'on':
            return True
        return False

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        self.hass.services.call("light", "turn_on", self._get_kwargs_payload(self._zeptrion_entity))
        self.hass.services.call("light", "turn_on", self._get_kwargs_payload(self._hue_entity, kwargs))
        self.update()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self.hass.services.call("light", "turn_off", self._get_kwargs_payload(self._zeptrion_entity))
        self.hass.services.call("light", "turn_off", self._get_kwargs_payload(self._hue_entity, kwargs))
        self.update()

    def TOGGLE(self, **kwargs):
        """Instruct the light toggle."""
        self.hass.services.call("light", "toogle", self._get_kwargs_payload(self._zeptrion_entity))
        self.hass.services.call("light", "toogle", self._get_kwargs_payload(self._hue_entity, kwargs))
        self.update()

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._state_hue = self.hass.states.get(self._hue_entity)
        self._state_zeptrion = self.hass.states.get(self._zeptrion_entity)
    
    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        # get Group Name
        attributes = {}
        attributes['group'] = self._friendly_group_name
        attributes['zeptrion_hue_group_entity'] = self._group  
        attributes['is_zeptrion_hue_group'] = True
        attributes['binded_devices'] = [self._zeptrion_entity, self._hue_entity]
        return attributes

    @ classmethod
    def _get_kwargs_payload(self, entity, kwargs = None):
        dictMainGroup = {}
        if kwargs:
            for arg in kwargs:
                dictMainGroup[arg] = kwargs[arg]
        dictMainGroup['entity_id'] = entity
        return dictMainGroup

    @ classmethod
    def _get_return_value(self, arg_name, t_state):
        if t_state and t_state.attributes and arg_name in t_state.attributes:
            return t_state.attributes[arg_name]
        return None