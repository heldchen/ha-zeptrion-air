"""Custom types for zeptrion_air."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import ZeptrionAirApiClient
    from .coordinator import ZeptrionAirDataUpdateCoordinator


type ZeptrionAirConfigEntry = ConfigEntry[ZeptrionAirData]


@dataclass
class ZeptrionAirData:
    """Data for the ZeptrionAir integration."""

    client: ZeptrionAirApiClient
    coordinator: ZeptrionAirDataUpdateCoordinator
    integration: Integration
