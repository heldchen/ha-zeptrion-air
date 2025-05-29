"""DataUpdateCoordinator for zeptrion_air."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ZeptrionAirApiClientError,
)
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    
    from .api import ZeptrionAirApiClient
    from .data import ZeptrionAirConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class ZeptrionAirDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: ZeptrionAirConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: ZeptrionAirApiClient,
    ) -> None:
        """Initialize."""
        self.client = client
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library, including device identification and RSSI."""
        if self.config_entry.runtime_data is None:
            LOGGER.error("Coordinator: Cannot update data, runtime_data is not available. Integration might not have been set up correctly or has been unloaded.")
            raise UpdateFailed("runtime_data not available")
        if self.client is None:
            LOGGER.error("Coordinator: Cannot update data, API client is not available. Integration might not have been set up correctly.")
            raise UpdateFailed("API client not available")
        try:
            # Fetch device identification data
            data: dict[str, Any] = await self.client.async_get_device_identification()
            
            # Fetch RSSI data
            # async_get_rssi is expected to return int | None
            # It will raise ZeptrionAirApiClientCommunicationError on communication issues,
            # or return None on parsing issues/other non-communication API errors.
            rssi_value: int | None = await self.client.async_get_rssi()
            
            # Add RSSI to the data dictionary
            # Storing None if RSSI could not be fetched/parsed, allows entities to handle it.
            data['rssi_dbm'] = rssi_value
            
            LOGGER.info("Coordinator full data update (with RSSI): %s", data)
            return data
        except ZeptrionAirApiClientError as exception:
            # This will catch errors from both async_get_device_identification and async_get_rssi
            LOGGER.error("Coordinator: Error updating data: %s", exception)
            raise UpdateFailed(f"Error communicating with API: {exception}") from exception
