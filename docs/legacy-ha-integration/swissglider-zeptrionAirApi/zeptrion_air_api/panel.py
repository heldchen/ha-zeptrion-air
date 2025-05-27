"""
Support for zeptrion_air_api.panel.

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/zeptrionAirApi
"""

import xml.etree.ElementTree as ET
import json
import requests
from .smt_btn import SmartButton
from .light_button import LightButton
from .blind_button import BlindButton


class Panel:  # pylint: disable=too-many-instance-attributes
    """
    Support for ZeptrionAir Panel.

    For more details about this Class, please refer to the documentation at
    https://github.com/swissglider/zeptrionAirApi
    """

    def __init__(self, name, ip, port, loop, button_action_listen_handler):
        # pylint: disable=too-many-arguments
        """Init the ZeptrionAir Panel."""
        self._name = name
        self._ip = ip
        self._port = port
        url = "http://" + str(self._ip)
        url += ":" + str(self._port)
        self._url = url
        # smartBtn 0-3 / channel1 -> 4 / channel2 -> 6
        self._buttons = [None] * 8
        self._is_smart_panel = False
        # only for smart buttons
        self._storage_place = ['a', 'c', 'e', 'g', 'i', 'k', 'm', 'o']
        self.loop = loop
        self.button_action_listen_handler = button_action_listen_handler
        self._read_smart_panel_info()
        self._read_button()
        self._start_listen_to_button_pressed()

    @property
    def name(self):
        """Return the Name from the panel."""
        return self._name

    @property
    def ip(self):  # pylint: disable=invalid-name
        """Return the IP from the panel."""
        return self._ip

    @property
    def port(self):
        """Return the Port from the panel."""
        return self._port

    @property
    def is_smart_panel(self):
        """Return if smart panel or not."""
        return self._is_smart_panel

    @property
    def url(self):
        """Return Panel URL."""
        return self._url

    @property
    def all_buttons(self):
        """Retrun an Array with all Butonns."""
        return self._buttons

    def __repr__(self):
        """Return a String representing the ZeptrionAirPanel."""
        return_string = "Panel Name: " + self.name + '\n'
        return_string += "\tPanel IP:Port: " + self.ip
        return_string += ":" + str(self.port) + '\n'
        # for channel in self.panel_channels:
        #     return_string += "\t\tPanel URL: " + channel.channel_id
        #     return_string += "\tPanel Name: " + channel.channel_name + '\n'
        # return_string += '\n'
        return return_string

    def get_device_rssi(self):
        """
        Return the RSSSI from that panel.

        RSSI = (Received Signal Strength Indication)
        Checking the RSSI may help to fix connection problems!
        If the RSSI is below about -75 dBm
        then the connection may become unreliable
        and whenever it drops for too long the device
        will reboot to find a better connection.
        """
        device_info_response = requests.get(self._url + "/zrap/rssi")
        if device_info_response.status_code == 200:
            root = ET.fromstring(device_info_response.text)
            return root[0].text
        return ''  # pragma: no cover

    def _read_smart_panel_info(self):
        """Read all the smart panel info if it is a smart panel."""
        device_info_response = requests.get(self._url + "/zapi/smartfront/id/")
        if device_info_response.status_code == 200:
            self._is_smart_panel = True
        else:
            return
        resp_value = json.loads(device_info_response.text)
        self._buttons = resp_value['btfu'].split(',')
        for index, button_value in enumerate(self._buttons, start=0):
            if button_value == '1000' or button_value == 1000:
                storage = self._storage_place[index]
                self._buttons[index] = SmartButton(self, storage)
            else:
                self._buttons[index] = None

    def _read_button(self):
        """Read all the non smart button info."""
        device_info_response = requests.get(self.url + "/zrap/chdes")
        if device_info_response.status_code == 200:
            root = ET.fromstring(device_info_response.text)
            # get Channel Informations
            for channel_xml in root:
                channel_info = {}
                channel_info['id'] = channel_xml.tag
                channel_info['name'] = channel_xml[0].text
                channel_info['group'] = channel_xml[1].text
                channel_info['icon'] = channel_xml[2].text
                channel_info['type'] = channel_xml[3].text
                channel_info['cat'] = channel_xml[4].text
                channel_info['friendly_name'] = channel_info['name']
                if channel_info['cat'] == '1':  # Light On/Off
                    button = LightButton(self, channel_info)
                    self._set_new_button(channel_info['id'], button)
                elif channel_info['cat'] == '3':  # Light dimmible
                    button = LightButton(self, channel_info)
                    self._set_new_button(channel_info['id'], button)
                elif channel_info['cat'] == '5':  # blind
                    button = BlindButton(self, channel_info)
                    self._set_new_button(channel_info['id'], button)
                elif channel_info['cat'] == '6':  # Markise
                    button = BlindButton(self, channel_info)
                    self._set_new_button(channel_info['id'], button)
                elif channel_info['cat'] == '-1':  # unused
                    pass
                else:  # unknown
                    pass

    def _set_new_button(self, channel_id, button):
        """Set new Button."""
        if channel_id == 'ch1':
            self._buttons[4] = button
        elif channel_id == 'ch2':
            self._buttons[6] = button

    def get_button(self, number):
        """Get new Button."""
        return self._buttons[number]

    def _start_listen_to_button_pressed(self):
        """
        Register the panel to listening to pressed buttons.

        If Button pressed, the callback will be called
        """
        self.button_action_listen_handler.register_new_listener(
            self, self.button_pressed_listener
        )

    def button_pressed_listener(self, info):
        """Listen to the pressed buttons."""
        if self._buttons[info.button_nr]:
            self._buttons[info.button_nr].status_update_listener(info)
