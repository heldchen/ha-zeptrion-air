"""ZeptrionAirEntity class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ZeptrionAirDataUpdateCoordinator


class ZeptrionAirEntity(CoordinatorEntity[ZeptrionAirDataUpdateCoordinator]):
    """ZeptrionAirEntity class."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZeptrionAirDataUpdateCoordinator, channel_id: int | None = None) -> None:
        """Initialize."""
        super().__init__(coordinator)
        runtime_data = coordinator.config_entry.runtime_data
        hub_serial = runtime_data.hub_serial
        hub_device_info = runtime_data.hub_device_info
        if channel_id is not None:
            self._attr_unique_id = f"zapp_{hub_serial}_ch{channel_id}"

            # Find channel info to populate device info
            channel_info = next((ch for ch in runtime_data.identified_channels if ch["id"] == channel_id), {})
            cat_int = channel_info.get("cat")
            panel_type_mapping = {5: "Blinds", 6: "Markise", 1: "Light Switch", 3: "Light Dimmer"}
            model = f"Zeptrion Air Channel {channel_id} - {panel_type_mapping.get(cat_int, 'Unknown')}"

            self._attr_device_info = DeviceInfo(
                identifiers={(coordinator.config_entry.domain, f"{hub_serial}_ch{channel_id}")},
                via_device=(coordinator.config_entry.domain, hub_serial),
                name=channel_info.get("entity_base_name", f"Channel {channel_id}"),
                manufacturer="Feller AG",
                model=model,
                sw_version=hub_device_info.get("sw_version"),
            )
        else:
            self._attr_unique_id = f"zapp_{hub_serial}"
            self._attr_device_info = DeviceInfo(
                identifiers={(coordinator.config_entry.domain, hub_serial)},
                name=hub_device_info.get("name"),
                manufacturer="Feller AG",
                model=hub_device_info.get("model"),
                sw_version=hub_device_info.get("sw_version"),
            )
