"""Diagnostics support for Zeptrion Air."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .data import ZeptrionAirConfigEntry

TO_REDACT = {"sn", "serial", "unique_id"}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ZeptrionAirConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator_data": async_redact_data(runtime_data.coordinator.data, TO_REDACT),
        "identified_channels": runtime_data.identified_channels,
        "hub_serial": "REDACTED",
        "hub_device_info": runtime_data.hub_device_info,
    }
