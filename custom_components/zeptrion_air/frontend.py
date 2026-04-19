from homeassistant.components.frontend import add_extra_js_url
from homeassistant.helpers.event import async_call_later
import os
import logging
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_frontend(hass, entry):
    """Set up frontend components."""
    if DOMAIN + "_frontend_registered" in hass.data:
        return
    hass.data[DOMAIN + "_frontend_registered"] = True

    _LOGGER.info("Setting up Zeptrion Air frontend")
    
    # Register the static path
    card_path = os.path.join(os.path.dirname(__file__), "www", "zeptrion-air-blinds-card.js")
    hass.http.register_static_path("/zeptrion_air/zeptrion-air-blinds-card.js", card_path)
    
    # Wait a bit for Home Assistant to fully initialize
    async def delayed_setup(_):
        _LOGGER.info("Delayed setup for Zeptrion Air frontend")
        
        # Add the extra JS URL
        add_extra_js_url(hass, "/zeptrion_air/zeptrion-air-blinds-card.js")
        
        # Try to register with Lovelace resources
        try:
            if "lovelace" in hass.data:
                lovelace_data = hass.data["lovelace"]
                
                # Use attribute access instead of dictionary access
                if hasattr(lovelace_data, "resources"):
                    resources = lovelace_data.resources
                    
                    # Check if our resource is already there
                    resource_url = "/zeptrion_air/zeptrion-air-blinds-card.js"
                    existing = False
                    
                    if hasattr(resources, 'data') and resources.data:
                        existing = any(
                            resource.get("url") == resource_url 
                            for resource in resources.data.values()
                        )
                    
                    if not existing and hasattr(resources, 'async_create_item'):
                        await resources.async_create_item({
                            "url": resource_url,
                            "type": "module"
                        })
                        _LOGGER.info("Added Zeptrion Air card to Lovelace resources")
        except Exception as e:
            _LOGGER.warning("Could not add to Lovelace resources: %s", e)
        
        # Fire an event to refresh frontend
        hass.bus.async_fire("frontend_reload")
    
    # Delay the setup by 5 seconds
    async_call_later(hass, 5, delayed_setup)
