import asyncio
import time
import json
import yaml
from zeptrion_air_api import Hub

config = {'ZeptrionAirConfig' : {}}
confi_yaml_file = 'async_server_config.yml'

def write_config_to_yaml_file():
    """write to the configFile"""
    # print(json.dumps(config, indent=4))
    # print(yaml.dump(config, default_flow_style=False))
    with open(confi_yaml_file, 'w') as yaml_file:
        yaml.dump(config, yaml_file, default_flow_style=False, canonical=False)

def read_config_yaml_file(config):
    """Read config yaml file into config"""
    try:
        with open(confi_yaml_file, 'r') as stream:
            config = yaml.load(stream)
    except FileNotFoundError:
        return None
    except yaml.YAMLError:
        return None
    else:
        return config

async def do_close(hub):
    """ Close the System. """
    write_config_to_yaml_file()
    await hub.close()

def generate_config(discovered_panel):
    if discovered_panel.name in config['ZeptrionAirConfig']:
        temp_panel_conf = config['ZeptrionAirConfig'][discovered_panel.name]
        for button_nr, button_conf in temp_panel_conf['buttons'].items():
            temp_button = discovered_panel.get_button(int(button_nr))
            if (not  temp_button.name == button_conf['name']) or (not temp_button.group == button_conf['group']):
                print(temp_button.name, button_conf['name'])
                print(temp_button.group, button_conf['group'])
                temp_button.change_info_configuration(
                    button_conf['name'],
                    button_conf['group']
                )

    if discovered_panel.name not in config['ZeptrionAirConfig']:
        print('Discovered new zeptrion device [%s][%s]' % (discovered_panel.ip, discovered_panel.name))
        buttons_struct = {}
        for index, button in enumerate(discovered_panel.all_buttons, start=0):
            if button is not None:
                button_struct = {
                    'name' : button.name,
                    'group' : button.group,
                }
                buttons_struct[index] = button_struct
        panel_struct = {
            # 'ip' : discovered_panel.ip,
            'buttons' : buttons_struct
        }
        config['ZeptrionAirConfig'][discovered_panel.name] = panel_struct

def press_info_handler(press_info):
    """ Handle if the button is pressed. """
    print(press_info)

def found_new_panels(panel):
    """ Handle if a new Zeptrion Air Panel is found. """
    # print('Register new zeptrion device [%s][%s]' % (panel.ip, panel.name))
    generate_config(panel)
    for button in panel.all_buttons:
        if button:
            button.listen_to(press_info_handler)


if __name__ == '__main__':
    """ Init the main test. """
    temp_conf = read_config_yaml_file(config)
    if temp_conf is not None:
        config = temp_conf
    loop = asyncio.get_event_loop()
    za_hub = Hub(loop, found_new_panels)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Unregistering...")
        loop.run_until_complete(do_close(za_hub))
    finally:
        loop.close()
