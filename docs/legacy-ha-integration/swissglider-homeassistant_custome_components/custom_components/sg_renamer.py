"""
Renames the friendly_name from entity_name and writtes it into the entity_registry.

Version V.0.0.1

Package:
    sg_renamer.py

configuration.yaml:
    # entity_name musst be --> <<group_name>> --> without spaces and 
    sg_renamer:
        - platform_name: hue    --> plattform_name to rename all entities
            domain: 
                light           --> domains to rename from the platform

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/homeassistant_custome_components
"""
import logging
import yaml

import homeassistant.helpers.entity as entity_helper
from homeassistant.helpers.event import track_state_change
from homeassistant.components.group import ENTITY_ID_FORMAT as GROUP_ID_FORMAT

# Initialize the logger
_LOGGER = logging.getLogger(__name__)

# The domain of your component. Equal to the filename of your component.
DOMAIN = "sg_renamer"

def setup(hass, config):
    
    conf = config.get(DOMAIN, {})
    to_rename_comp = {}

    for panel in conf:
        if 'platform_name' not in panel:
            _LOGGER.critical('Error in config: following Parameter nor set - name')
            return False
        platform_name = panel['platform_name']
    
        domain_filter = []
        if 'domain' in panel:
            filters = panel['domain'].split( )
            for filter in filters:
                domain_filter.append(filter)

        to_rename_comp[platform_name] = {
            'platform_name': platform_name,
            'domain': domain_filter
        }

    #entity_id = entity_helper.generate_entity_id('{}','renamer', hass=hass)
    name_changer = NameChanger(to_rename_comp, hass, DOMAIN)
    hass.services.register(DOMAIN, 'rename', name_changer.rename)

    # Return boolean to indicate that initialization was successfully.
    return True

class NameChanger:
    def __init__(self, to_rename_comp, hass, domain):
        self._to_rename_comp = to_rename_comp
        self._hass = hass
        self._domain = domain

    def rename(self, call):
        for comp_name in self._to_rename_comp:
            comp = self._to_rename_comp[comp_name]
            entities = self._get_all_entities(comp['domain'])
            entities = self._get_filtered_by_plattform(entities, comp['platform_name'])
            self._rename_all_frienly_names(entities)

    def _get_all_entities(self, domain_filters):
        entities = []
        if domain_filters and len(domain_filters) != 0:
            for domain_filter in domain_filters:
                entities = entities + self._hass.states.entity_ids(domain_filter)
        else:
            entities = self._hass.states.entity_ids()
        return entities

    def _get_filtered_by_plattform(self, entities, platform_name):
        return_entities = []

        PATH_REGISTRY = 'entity_registry.yaml'
        path = self._hass.config.path(PATH_REGISTRY)
        data = None
        with open(path) as fp:
            data = yaml.load(fp)
        for entity_id, info in data.items():
            if (entity_id in entities) and (str(info['platform']) == str(platform_name)):
                return_entities.append(entity_id)
        
        return return_entities

    def _get_friendly_name(self, name):
        ''' return a friendly name from name. '''
        if name:
            name = name.replace(".", " ")
            name = name.replace("_", " ")
            name = name.title()
        return name
    
    # ========================================================
    # ========================== Change Registry Name
    # ========================================================

    def _changeFriendlyName(self, enitity_name, friendly_name):
        ''' Change the Registry Name of the entity. '''
        import requests
        import json
        url = 'http://localhost:8123/api/config/entity_registry/' + str(enitity_name)
        payload = {'name': str(friendly_name)}
        headers = {'content-type': 'application/json'}
        r = requests.post(url, data=json.dumps(payload), headers=headers)
        if r.status_code is not 200:
            _LOGGER.warning('Frienly Name(' + friendly_name + ') change was not successfull for Entity: ' + str(enitity_name) + " Status-Code: " + str(r.status_code))

    def _rename_all_frienly_names(self, entities):
        ''' Change all entities Registry Names to friendly name. '''
        for entity in entities:
            object_name = entity.partition('.')[2]
            friendly_name = object_name.partition('_')[2]
            friendly_name = self._get_friendly_name(friendly_name)
            self._changeFriendlyName(entity, friendly_name)
