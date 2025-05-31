"""Custom types for zeptrion_air."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from homeassistant.config_entries import ConfigEntry # Added this line

if TYPE_CHECKING:
    # from homeassistant.config_entries import ConfigEntry # No longer needed here
    from homeassistant.loader import Integration

    from .api import ZeptrionAirApiClient
    from .coordinator import ZeptrionAirDataUpdateCoordinator
    from .websocket_listener import ZeptrionAirWebsocketListener # MODIFIED: Added import

#MODIFIED: Replaced type alias with dataclass definition
#type ZeptrionAirConfigEntry = ConfigEntry[ZeptrionAirData]


@dataclass
class ZeptrionAirData:
    """Data for the ZeptrionAir integration."""

    client: ZeptrionAirApiClient
    coordinator: ZeptrionAirDataUpdateCoordinator
    integration: Integration
    websocket_listener: "ZeptrionAirWebsocketListener | None" = None # MODIFIED: Added field

@dataclass
class ZeptrionAirConfigEntry(ConfigEntry):
    """Typed ConfigEntry for Zeptrion Air."""
    runtime_data: ZeptrionAirData | None = None # MODIFIED: field(default=None) is implicit
    # options: ZeptrionAirOptions = field(default_factory=ZeptrionAirOptions) # If options are used
