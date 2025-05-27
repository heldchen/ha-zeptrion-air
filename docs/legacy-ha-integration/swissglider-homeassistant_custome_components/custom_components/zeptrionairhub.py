"""
Supports the Zeptrion Air Devices.

Version V.0.0.1

Package:
    custom_components.zeptrionairhub.py
    custom_components.light.zeptrionairhub.py
    custom_components.cover.zeptrionairhub.py

configuration.yaml:
    zeptrionairhub:

ToDo:

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/homeassistant_custome_components
"""

import logging

import voluptuous as vol

from homeassistant.components.light import PLATFORM_SCHEMA
from homeassistant.helpers.discovery import load_platform
from homeassistant.const import CONF_HOST, CONF_NAME
import homeassistant.helpers.config_validation as cv
DOMAIN = 'zeptrionairhub'

REQUIREMENTS = ['zeptrionAirApi']

_LOGGER = logging.getLogger(__name__)

# CONF_BROWSE_TIME = 'browsetime'

# Validation of the user's configuration
# PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
#     vol.Optional(CONF_BROWSE_TIME, default=5): cv.positive_int,
# })

DATA_ZEPTRIONAIRHUB = 'ZeptrionAirHub'

def setup(hass, config):
    from zeptrionAirApi import ZeptrionAirHub
    """Your controller/hub specific code."""
    hass.data[DATA_ZEPTRIONAIRHUB] = ZeptrionAirHub(5)

    #--- snip ---
    load_platform(hass, 'light', DOMAIN)
    load_platform(hass, 'cover', DOMAIN)
    #load_platform(hass, 'switch', DOMAIN)
    return True