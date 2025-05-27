"""
Support for zeptrion_air_api.button.

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/zeptrionAirApi
"""

import xml.etree.ElementTree as ET
import requests


class Button:
    """The Button is the base class of all buttons."""

    def __init__(self, panel, info, is_smart_button=False):
        """
        Init the Button.

            :param info: -- dictornary with at least
                :info['id']
                :info['name']
                :info['group']
                :info['friendly_name']
                :info['cat']
                    --> -1 unused
                    -->  1 light on/of
                    -->  3 light dimmable
                    -->  5 blind
                    -->  6 Markise
                    --> 17 Smart Btn
        """
        self._is_smt_btn = is_smart_button
        self._panel = panel
        self._info = info
        self._last_update_info = None
        self._status_update_callback = None

    @property
    def panel_url(self):
        """Return the panel URL."""
        return self._panel.url

    @property
    def uniq_id(self):
        """Return the uniq ID from the channel."""
        return str(self._panel.name)+str(self._info.id)

    @property
    def id(self):  # pylint: disable=invalid-name
        """Return the ID from the channel."""
        return self._info['id']

    @property
    def name(self):
        """Return the Name from the channel."""
        return self._info['name']

    @property
    def group(self):
        """Return the Group Name from the channel."""
        return self._info['group']

    @property
    def icon(self):
        """Return the Icon from the channel."""
        if self._info['icon']:
            return self._info['icon']
        return None

    @property
    def type(self):
        """Return the Type from the channel."""
        if self.cat == -1:
            return 'unused'
        elif self.cat == 1:
            return 'light on/of'
        elif self.cat == 3:
            return 'light dimmable'
        elif self.cat == 5:
            return 'blind'
        elif self.cat == 6:
            return 'Markise'
        elif self.cat == 17:
            return 'Smart Btn'
        else:
            return 'unknown'

    @property
    def cat(self):
        """Return the Category from the channel."""
        return self._info['cat']

    @property
    def panel(self):
        """Return the Panel from the button."""
        return self._panel

    @property
    def is_smart(self):
        """Return the is_smart from the button."""
        return self._is_smt_btn

    def __repr__(self):
        """Return a String representing the ZeptrionAirChannel."""
        return_str = "IP: " + str(self.panel_url)
        return_str += "\tName: " + str(self.name)
        return_str += "\tGroup: " + str(self.group)
        return_str += "\tCat: " + str(self.cat)
        return_str += "\tID: " + str(self.id)
        return return_str

    def change_info_configuration(
            self, name, group
    ):
        """Change the Configuration."""
        if str(self.cat) in ['1', '3', '5', '6']:
            payload = ''
            if name:
                payload += 'name=' + str(name) + '&'
            if group:
                payload += 'group=' + str(group) + '&'

            payload = payload[:-1]
            full_url = self.panel_url
            full_url += "/zrap/chdes/" + self.id
            requests.post(full_url, data=payload)

    def _control(self, payload):
        """Send controll command to zeptrion air device."""
        if str(self.cat) in ['1', '3', '5', '6']:
            full_url = self.panel_url
            full_url += "/zrap/chdes/" + self.id
            requests.post(full_url, data=payload)

    def _update(self):
        """Update the real status of the channel switch."""
        if not self._is_smt_btn:
            full_url = self.panel_url
            full_url += "/zrap/chscan/" + self.cat
            device_info_response = requests.get(full_url)
            if device_info_response.status_code == 200:
                root = ET.fromstring(device_info_response.text)
                if root[0][0].text == '100':
                    return True
                return False
            return False  # pragma: no cover
        return False

    def listen_to(self, callback):  # pylint: disable=protected-access
        """Register button to listen for update change."""
        self._status_update_callback = callback

    def status_update_listener(self, info):
        """Listen to the callback for the button pressed events."""
        self._last_update_info = info
        if self._status_update_callback:
            self._status_update_callback(info)
