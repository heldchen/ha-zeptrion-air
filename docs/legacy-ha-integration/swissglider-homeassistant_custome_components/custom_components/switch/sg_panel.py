"""
Swiss glider Panel.

Version V.0.0.2

Package:
    custom_components.sg_panel.py
    custom_components.switch.sg_panel.py

configuration.yaml:
    # musst: name / opt: group, donain_filter, attr_filter, group_filter
    sg_panel:
    - name: Hello World
        domain_filter:
            hello_world
    - name: Zeptrion Lights Stube
        domain_filter:
            light
        attr_filter:
            is_zeptrion_group
        group_filter:
            Stube

ToDo:
- Splitt into two Components
- Change to hide insteed of remove group
- Change the add Main Panel to be added
- Auto Update

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/homeassistant_custome_components
"""

import logging

from homeassistant.components.switch import SwitchDevice
import homeassistant.helpers.entity as entity_helper
from homeassistant.components.switch import ENTITY_ID_FORMAT as SWITCH_ENTITY_ID_FORMAT
from homeassistant.components.group import ENTITY_ID_FORMAT as GROUP_ID_FORMAT
from homeassistant.const import (STATE_OFF, STATE_ON)

# Initialize the logger
_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices, discovery_info=None):
    test = 1
    switche_names_attr =  hass.data['switche_names_attr']
    switch_entity_names = []

    devices = []

    for attr in switche_names_attr:

        name = switche_names_attr[attr]['name']
        group = switche_names_attr[attr]['group']

        overview_panel = switche_names_attr[attr]['overview_panel']
        DOMAIN = switche_names_attr[attr]['domain']
        entity_name = entity_helper.generate_entity_id(SWITCH_ENTITY_ID_FORMAT, name, hass=hass)
        devices.append(PanelSwitch(name, group, overview_panel, DOMAIN, hass))
        switch_entity_names.append(entity_name)
    
    add_devices(devices)

    sub_group = {
            'object_id': 'panel',
            'name': 'Panel Switch',
            # 'view': True,
            'view': False,
            'visible': True,
            'add_entities': switch_entity_names
        }
    hass.services.call("group", "set", sub_group)

    # entities = hass.states.entity_ids()
    # printout = '$$$$$$$$$$$$$$$$$$$\n'
    # for entity in entities:
    #     printout += '\t entity_name: ' + entity + '\n'
        
    # _LOGGER.error(printout)

    # default_group_view = hass.states.get('group.default_view')
    # _LOGGER.error(default_group_view)
    # dv_attr = default_group_view.attributes
    # _LOGGER.error(dv_attr)

    panel_group_name = entity_helper.generate_entity_id(GROUP_ID_FORMAT, 'panel', hass=hass)

    default_panel = {
            'object_id': 'default_view',
            # 'object_id': 'test_panel',
            'name': 'Home',
            'view': True,
            'visible': True,
            'add_entities': ['group.panel']
        }
    hass.services.call("group", "set", default_panel)

class PanelSwitch(SwitchDevice):

    def __init__(self, name, group, overview_panel, domain, hass):
        self._name = name
        self._group = group
        self._state = STATE_OFF
        self._overview_panel = overview_panel
        self._domain = domain
        self.hass = hass

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name
    
    @property
    def should_poll(self):
        """No polling needed for a demo switch."""
        return True
    
    @property
    def state(self):
        """Return the state of the device."""
        return self._state
    
    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        self._state = STATE_ON
        self._overview_panel.show()

    def turn_off(self, **kwargs):
        self._state = STATE_OFF
        self._overview_panel.hide()
    
    def update(self):
        return True
    
    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        # get Group Name
        attributes = {}
        attributes['group'] = self._group
        attributes['friendly_name'] = self._name
        return attributes
