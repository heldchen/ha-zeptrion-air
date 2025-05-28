import unittest
import time
import json
import asyncio
from zeptrion_air_api import Hub

def press_info_handler(press_info):
    """ Handle if the button is pressed. """
    print(press_info)

def found_new_panels(panel):
    """ Handle if a new Zeptrion Air Panel is found. """
    print('Register new zeptrion device [%s][%s]' % (panel.ip, panel.name))
    for button in panel.all_buttons:
        if button:
            button.listen_to(press_info_handler)

class TestZeptrionAir(unittest.TestCase):
    def setup_class(self):
        self.loop = asyncio.get_event_loop()
        self.hub = Hub(self.loop, found_new_panels)

# ============================================
# Hub tests
# ============================================

    def test_if_Hub_is_not_None(self):
        ''' Test if hub is initialized. '''
        self.assertTrue(self.hub is not None)