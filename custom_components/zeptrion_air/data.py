"""Custom types for zeptrion_air."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable
from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from homeassistant.loader import Integration

    from .api import ZeptrionAirApiClient
    from .coordinator import ZeptrionAirDataUpdateCoordinator
    from .websocket_listener import ZeptrionAirWebsocketListener

@dataclass
class ZeptrionAirData:
    """Data for the ZeptrionAir integration."""

    client: ZeptrionAirApiClient
    coordinator: ZeptrionAirDataUpdateCoordinator
    integration: Integration
    identified_channels: list[dict[str, Any]]
    hub_serial: str
    hub_device_info: dict[str, Any]
    websocket_listener: "ZeptrionAirWebsocketListener | None" = None
    websocket_watchdog_cancel_callback: Callable[[], None] | None = None

type ZeptrionAirConfigEntry = ConfigEntry[ZeptrionAirData]

