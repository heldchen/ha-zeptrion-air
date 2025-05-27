"""
Support for zeptrion_air_api.smt_btn.

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/zeptrionAirApi
"""

import json
import requests
from .button import Button


class SmartButton(Button):
    """The Smart Button represents a Zeptrion Air Smartbutton."""

    def __init__(self, panel, storage_place):
        """Initialize the Smart Button."""
        self._storage = storage_place
        # self.reset_btn_configuration(panel)
        info = self._get_stored_info(panel)
        super().__init__(panel, info, is_smart_button=True)

    def _get_stored_info(self, panel):
        """Read the configuration or set standard if not yet set."""
        device_info_response = requests.get(
            panel.url + "/zapi/smartbt/prgs/" + self._storage
        )
        info = None
        response = device_info_response.text
        if device_info_response.status_code == 200:
            response = json.loads(response)
            if response['type'] and response['type'] == 'zeptrion_Air':
                info = response
        if not info:
            self.reset_btn_configuration(panel)
        return info

    def reset_btn_configuration(self, panel=None):
        """Reset Info Configuration."""
        info = self.change_info_configuration(
            "New_smart_panel_" + self._storage,
            "new",
            "New_smart_panel_" + self._storage,
            panel=panel
        )
        return info

    def change_info_configuration(
            self, name, group
    ):
        """Change the Configuration."""
        full_url = self.panel.url
        full_url += "/zapi/smartbt/prgs/" + self._storage
        info = {
            "type": "zeptrion_Air",
            "name": name,
            "group": group,
            "friendly_name": name,
            "id": self._storage,
            "cat": '17'
        }
        requests.post(full_url, data=json.dumps(info))
        return info
