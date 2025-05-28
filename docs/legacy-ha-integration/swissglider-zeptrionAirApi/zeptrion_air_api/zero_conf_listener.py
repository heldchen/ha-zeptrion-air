"""
Support for zeptrion_air_api.zero_conf_listener.

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/zeptrionAirApi
"""

import socket
from zeroconf import ServiceBrowser, Zeroconf


class ZeroConfListener():
    """
    The ZeroConfListener handles the browse off all Zeptrion Air.

    It listen for all Zeptrion Air devices available on zeroconf.

    """

    def __init__(self, add_service_handler):
        """
        Init the ZeroConfListener.

            :param add_service_handler: -- that gets the new found devices
        """
        self._add_service_handler = add_service_handler
        self._zeroconf = None
        self._browser = None
        self._service_type = "_zapp._tcp.local."

    def start_searching(self):
        """Start searching."""
        self._zeroconf = Zeroconf()
        self._browser = ServiceBrowser(
            self._zeroconf,
            self._service_type, self
        )

    def stop_searching(self):
        """Stop searching."""
        self._browser.cancel()
        self._zeroconf.close()

    @staticmethod
    def is_a_zapp_device(name):
        """Test id the device is a zeptrionAir device."""
        return name.startswith('zapp-') and name[5:13].isdigit()

    def remove_service(self, zeroconf, _type, name):
        """Remove a service."""
        pass

    def add_service(self, zeroconf, _type, name):
        """Add a zeptrion Service and call the add_service_handler."""
        info = zeroconf.get_service_info(_type, name)
        if info:
            if self.is_a_zapp_device(info.name):
                _ip = socket.inet_ntoa(info.address)
                self._add_service_handler(name, _ip, info.port)
