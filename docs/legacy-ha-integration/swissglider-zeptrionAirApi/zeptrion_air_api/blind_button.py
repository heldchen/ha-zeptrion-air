"""
Support for zeptrion_air_api.smt_btn.

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/zeptrionAirApi
"""
import time
from .button import Button


class BlindButton(Button):
    """The Smart Button represents a Zeptrion Air Smartbutton."""

    def __init__(self, panel, info):
        """Initialize the Smart Button."""
        self._blind_position = None
        super().__init__(panel, info, is_smart_button=False)

    def change_info_configuration(
            self, name, group
    ):
        """Change the Configuration."""
        super().change_info_configuration(name, group)

    def move_up_blind(self):
        """Move up blind."""
        self._control("cmd=open")
        self._blind_position = None

    def move_down_blind(self):
        """Move down blind."""
        self._control("cmd=close")
        self._blind_position = None

    def stop_blind(self):
        """Move stop blind."""
        self._control("cmd=stop")
        self._blind_position = None

    def tilt_up_blind(self):
        """Tilt up blind."""
        self.move_up_blind()
        time.sleep(float(0.2))
        self.stop_blind()
        self._blind_position = None

    def tilt_down_blind(self):
        """Tilt up blind."""
        self.move_down_blind()
        time.sleep(float(0.2))
        self.stop_blind()
        self._blind_position = None

    def blind_is_stoped(self):
        """Tilt up blind."""
        return self._update()

    def go_to_position(self, postion):
        """
        Move blind to position.

        If position is not yet set, it goes first totally down
        0 = open
        100 = close
        """
        sleep_time = None
        if self._blind_position is None:
            payload = "cmd=open"
            self._control(payload)
            time.sleep(float(0.2))
            while self._update():
                time.sleep(float(0.2))
            payload = "cmd=close"
            self._control(payload)
            sleep_time = float(53.7/100*postion)
        elif postion < self._blind_position:
            payload = "cmd=open"
            self._control(payload)
            sleep_time = float(55.3/100*(self._blind_position-postion))
        elif postion > self._blind_position:
            payload = "cmd=close"
            self._control(payload)
            sleep_time = float(53.7/100*(postion-self._blind_position))
        time.sleep(sleep_time)
        payload = "cmd=stop"
        self._control(payload)
        self._blind_position = postion
