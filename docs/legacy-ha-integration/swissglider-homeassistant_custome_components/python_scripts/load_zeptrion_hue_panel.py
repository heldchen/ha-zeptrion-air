entities = hass.states.entity_ids()
sup_groups =[]
sup_group_entities = {}
for entity in entities:
    entity_attributes = hass.states.get(entity).attributes
    if 'is_zeptrion_hue_group' in entity_attributes:
        group_name_entity = entity_attributes['zeptrion_hue_group_entity']
        group_name = entity_attributes['zeptrion_hue_group']
        if group_name_entity not in sup_groups:
            sup_groups.append(group_name_entity)
            sup_group_entities[group_name_entity] = {}
            dictSubGroup = {}
            dictSubGroup['object_id'] = group_name_entity.partition('group.')[2]
            dictSubGroup['name'] = group_name
            dictSubGroup['view'] = False
            dictSubGroup['visible'] = True
            dictSubGroup['add_entities'] = []
            sup_group_entities[group_name_entity] = dictSubGroup
        sup_group_entities[group_name_entity]['add_entities'].append(entity)

for group in sup_group_entities:
    hass.services.call("group", "set", sup_group_entities[group])

dictMainGroup = {}
dictMainGroup['object_id'] = 'zeptrion_hue_lights'
dictMainGroup['name'] = "Zeptrion Hue Lights"
dictMainGroup['view'] = True
dictMainGroup['visible'] = True
dictMainGroup['add_entities'] = sup_groups
hass.services.call("group", "set", dictMainGroup)