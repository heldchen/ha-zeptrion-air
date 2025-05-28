# The domain of your component. Should be equal to the name of your component.
DOMAIN = 'hello_service'

ATTR_NAME = 'name'
DEFAULT_NAME = 'World'


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    def handle_hello(call):
        name = call.data.get(ATTR_NAME, DEFAULT_NAME)

        hass.states.set('hello_service.hello', name)

    hass.services.register(DOMAIN, 'hello', handle_hello)

    # Return boolean to indicate that initialization was successfully.
    return True