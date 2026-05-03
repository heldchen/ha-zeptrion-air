from __future__ import annotations

from pathlib import Path
import logging

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_NEW_URL = "/zeptrion_air/zeptrion-air-blinds-card.js"
_OLD_URL = "/api/zeptrion_air/zeptrion-air-blinds-card.js"


async def _register_static_paths(hass, card_path: str) -> None:
    """Register static paths using the modern Home Assistant API."""
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(_NEW_URL, card_path, cache_headers=False),
            StaticPathConfig(_OLD_URL, card_path, cache_headers=False),
        ]
    )


async def async_setup_frontend(hass, _entry):
    """Set up frontend components."""
    if DOMAIN + "_frontend_registered" in hass.data:
        return
    hass.data[DOMAIN + "_frontend_registered"] = True

    _LOGGER.info("Setting up Zeptrion Air frontend")
    
    # Register the static path (new one and legacy one for compatibility)
    card_path = str(Path(__file__).parent / "www" / "zeptrion-air-blinds-card.js")
    await _register_static_paths(hass, card_path)
    
    # Wait a bit for Home Assistant to fully initialize
    async def delayed_setup(_):
        _LOGGER.info("Delayed setup for Zeptrion Air frontend")
        
        # Add the extra JS URL (new path)
        add_extra_js_url(hass, _NEW_URL)
        
        # Try to register with Lovelace resources and migrate old one
        try:
            if "lovelace" in hass.data:
                lovelace_data = hass.data["lovelace"]
                
                if hasattr(lovelace_data, "resources"):
                    resources = lovelace_data.resources
                    
                    has_new = False
                    old_resource_id = None
                    
                    if hasattr(resources, 'data') and resources.data:
                        for resource_id, resource in resources.data.items():
                            url = resource.get("url")
                            if url == _NEW_URL:
                                has_new = True
                            elif url == _OLD_URL:
                                old_resource_id = resource_id
                    
                    # Migration logic
                    if old_resource_id:
                        _LOGGER.info("Found legacy Zeptrion Air resource, migrating to new URL")
                        if hasattr(resources, 'async_delete_item'):
                            await resources.async_delete_item(old_resource_id)

                        if not has_new and hasattr(resources, 'async_create_item'):
                            await resources.async_create_item({
                                "url": _NEW_URL,
                                "type": "module"
                            })
                            has_new = True

                    if not has_new and hasattr(resources, 'async_create_item'):
                        await resources.async_create_item({
                            "url": _NEW_URL,
                            "type": "module"
                        })
                        _LOGGER.info("Added Zeptrion Air card to Lovelace resources")
        except (AttributeError, TypeError, ValueError) as err:
            _LOGGER.warning("Could not add to Lovelace resources: %s", err)
        
        # Fire an event to refresh frontend
        hass.bus.async_fire("frontend_reload")
    
    # Delay the setup by 5 seconds
    async_call_later(hass, 5, delayed_setup)
