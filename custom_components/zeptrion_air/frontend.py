from homeassistant.components.http import HomeAssistantView
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.lovelace import dashboard
from homeassistant.helpers.event import async_call_later
from homeassistant.util import executor
from aiohttp import web
import os
import logging

_LOGGER = logging.getLogger(__name__)

class ZeptrionAirCardView(HomeAssistantView):
    """Serve the custom card."""
    
    url = "/api/zeptrion_air/zeptrion-air-blinds-card.js"
    name = "api:zeptrion_air:card"
    requires_auth = False

    async def get(self, request):
        """Serve the card JS file."""
        card_path = os.path.join(os.path.dirname(__file__), "www", "zeptrion-air-blinds-card.js")
        
        if not os.path.exists(card_path):
            return web.Response(status=404)
        
        def _read_file():
            """Read file in executor."""
            with open(card_path, 'r') as f:
                return f.read()
        
        try:
            content = await request.app["hass"].async_add_executor_job(_read_file)
        except Exception as e:
            _LOGGER.error("Error reading card file: %s", e)
            return web.Response(status=500)
            
        return web.Response(
            text=content,
            content_type="text/javascript",
            headers={
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )

async def async_setup_frontend(hass, entry):
    """Set up frontend components."""
    _LOGGER.info("Setting up Zeptrion Air frontend")
    
    # Register the view
    hass.http.register_view(ZeptrionAirCardView())
    
    # Wait a bit for Home Assistant to fully initialize
    async def delayed_setup(_):
        _LOGGER.info("Delayed setup for Zeptrion Air frontend")
        
        # Add the extra JS URL
        add_extra_js_url(hass, "/api/zeptrion_air/zeptrion-air-blinds-card.js")
        
        # Try to register with Lovelace resources
        try:
            if "lovelace" in hass.data:
                lovelace_data = hass.data["lovelace"]
                
                # Use attribute access instead of dictionary access
                if hasattr(lovelace_data, "resources"):
                    resources = lovelace_data.resources
                    
                    # Check if our resource is already there
                    resource_url = "/api/zeptrion_air/zeptrion-air-blinds-card.js"
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
