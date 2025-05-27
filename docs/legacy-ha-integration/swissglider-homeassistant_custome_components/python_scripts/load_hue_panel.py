#name = data.get('name', 'world')
#logger.info("Hello {}".format(name))
#hass.bus.fire(name, { "wow": "from a Python script!" })
command: python3 -c "import requests

entities = hass.states.entity_ids()


sup_group_entities = []
for entity in entities:
    entity_states = hass.states.get(entity)
    entity_attributes = entity_states.attributes
    if 'emulated_hue_hidden' in entity_attributes:
        data = {}
        registry = async_get_registry(hass)
        data['name'] = 'Test this Name'
        new_entry = registry.async_update_entity(entity, **data)
        sup_group_entities.append(entity)

dictMainGroup = {}
dictMainGroup['object_id'] = "hue_lights"
dictMainGroup['name'] = "Hue Lights"
dictMainGroup['view'] = True
dictMainGroup['visible'] = True
dictMainGroup['add_entities'] = sup_group_entities
hass.services.call("group", "set", dictMainGroup)
