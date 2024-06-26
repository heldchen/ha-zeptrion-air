"""
Custom integration to integrate Zeptrion Air devices with Home Assistant.

For more details about this integration, please refer to
https://github.com/heldchen/ha-zeptrion-air
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration
from homeassistant.helpers import device_registry

from .api import ZeptrionAirApiClient
from .coordinator import ZeptrionAirDataUpdateCoordinator
from .data import ZeptrionAirData

from .const import DOMAIN, LOGGER, CONF_HOSTNAME, CONF_IP_ADDRESS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import ZeptrionAirConfigEntry

PLATFORMS: list[Platform] = [
#    Platform.SENSOR,
#    Platform.BINARY_SENSOR,
#    Platform.SWITCH,
]

# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZeptrionAirConfigEntry,
) -> bool:
    """Set up the Zeptrion Air Hub from a config entry."""

    coordinator = ZeptrionAirDataUpdateCoordinator(
        hass=hass,
    )
    entry.runtime_data = ZeptrionAirData(
        client=ZeptrionAirApiClient(
            hostname=entry.data[CONF_HOSTNAME],
            session=async_get_clientsession(hass),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    LOGGER.info("Coordinator data: %s", coordinator.data)

    # add hub as device
    registry = device_registry.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(device_registry.CONNECTION_UPNP, entry.data[CONF_HOSTNAME])},
        identifiers={(DOMAIN, entry.data[CONF_HOSTNAME])},
        manufacturer="Feller",
        name=entry.data[CONF_HOSTNAME].replace('.local', ''),
        model=coordinator.data['id']['type'],
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ZeptrionAirConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ZeptrionAirConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
