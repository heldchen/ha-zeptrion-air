"""
Hello World Component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/developers/development_101/
"""

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

# Initialize the logger
_LOGGER = logging.getLogger(__name__)

# The domain of your component. Equal to the filename of your component.
DOMAIN = "hello_world"


# define the dependencies
DEPENDENCIES = []

CONF_TEXT = 'text'
DEFAULT_TEXT = 'No text!'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
      vol.Required(CONF_TEXT): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the hello_world component."""
    # Get the text from the configuration. Use DEFAULT_TEXT if no name is provided.
    text = config[DOMAIN].get(CONF_TEXT, DEFAULT_TEXT)

    # States are in the format DOMAIN.OBJECT_ID.
    hass.states.set('hello_world.Hello_State', text)

    # Return boolean to indicate that initialization was successfully.
    return True