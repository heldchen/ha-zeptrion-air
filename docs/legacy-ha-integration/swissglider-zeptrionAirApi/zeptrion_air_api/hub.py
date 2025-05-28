"""
Support for zeptrion_air_api.hub.

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/zeptrionAirApi
"""
from .zero_conf_listener import ZeroConfListener
from .panel import Panel
from .button_action_listener import ButtonActionListenerHandler


class Hub:
    """
    The ZeptrionAir Hub handles all the ZeptrionAir Panels.

    The Hub is searching (browse) the panels with mDNS (zeroconf).
    If panels are found with mDNS the Hub is requesting the panels
    for all additional needed informations.

    In the initialization it browses already the first time.
    On the
    """

    def __init__(self, loop, found_new_panels):
        """
        Init the ZeptrionAirHub and start searchin for devices.

            :param found_new_panels: -- callback when new panels are found
        """
        self.loop = loop
        self.button_action_listen_handler = ButtonActionListenerHandler(loop)
        self._found_new_panels = [found_new_panels]
        self._zero_conf_listener = ZeroConfListener(self.found_new_devices)
        self.start_searching_new_devices()
        self._panels = []

    @property
    def all_panels(self):
        """Return all found panesl."""
        return self._panels

    def start_searching_new_devices(self):
        """Start searching new devices with zeroconf."""
        # start searching new zeptrionAir devices
        self._zero_conf_listener.start_searching()

    def stop_searching_new_devices(self):
        """Stop searching new devices with zeroconf."""
        self._zero_conf_listener.stop_searching()

    def register_for_new_found_panels(self, found_new_panels):
        """Register the found_new_panels function."""
        self._found_new_panels.append(found_new_panels)

    def found_new_devices(self, name, _ip, port):
        """Listen to callback function for the zero_conf_listener."""
        new_panel = self.get_new_panel(name, _ip, port)
        if new_panel:
            self._panels.append(new_panel)
            for callback in self._found_new_panels:
                callback(new_panel)

    def get_new_panel(self, name, _ip, port):
        """Create and return new found panel."""
        for panel in self.all_panels:
            if panel.ip == _ip and panel.port == port and panel.name == name:
                return None
        return Panel(
            name, _ip, port,
            self.loop, self.button_action_listen_handler
        )

    async def close(self):
        """Close the Button Action listen handler."""
        self.stop_searching_new_devices()
        await self.button_action_listen_handler.close()
