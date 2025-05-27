"""
Support for zeptrion_air_api.smt_btn.

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/zeptrionAirApi
"""
from .button import Button


class LightButton(Button):
    """The Smart Button represents a Zeptrion Air Smartbutton."""

    def __init__(self, panel, info):
        """Initialize the Smart Button."""
        super().__init__(panel, info, is_smart_button=False)

    def change_info_configuration(
            self, name, group
    ):
        """Change the Configuration."""
        super().change_info_configuration(name, group)

    def turn_on_light(self):
        """Turn the real light switch off."""
        self._control("cmd=on")

    def turn_off_light(self):
        """Turn the real light switch off."""
        self._control("cmd=off")

    def toggle_light(self):
        """Toggles the real light switch."""
        self._control("cmd=toggle")
