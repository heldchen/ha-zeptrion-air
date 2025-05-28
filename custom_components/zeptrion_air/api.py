"""Sample API Client."""

from __future__ import annotations

import logging
import json
import socket
import xmltodict
from urllib.parse import urlencode # Added import

from typing import Any

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)


class ZeptrionAirApiClientError(Exception):
    """Exception to indicate a general API error."""


class ZeptrionAirApiClientCommunicationError(
    ZeptrionAirApiClientError,
):
    """Exception to indicate a communication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    response.raise_for_status()


class ZeptrionAirApiClient:
    """Sample API Client."""

    def __init__(
        self,
        hostname: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Sample API Client."""
        self._hostname = hostname
        self._baseurl = 'http://' + hostname
        self._session = session

    async def async_get_device_identification(self) -> dict[str, Any]:
        """Get the device identification from the API."""
        return await self._api_xml_wrapper(
            method="get",
            path="/zrap/id",
        )

    async def _api_json_wrapper(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get information from the API via XML."""
        try:
            # _LOGGER.info("[API] --> %s %s", method, self._baseurl + path)
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=self._baseurl + path,
                    headers=headers,
                    json=data,
                )
                _verify_response_or_raise(response)

                data = await response.json()
                # _LOGGER.info("[API] <-- %s %s", response.status, data)
                return data

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise ZeptrionAirApiClientCommunicationError(
                msg,
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise ZeptrionAirApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise ZeptrionAirApiClientError(
                msg,
            ) from exception
        
    async def _api_xml_wrapper(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get information from the API."""
        try:
            # _LOGGER.info("[API] --> %s %s", method, self._baseurl + path)
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=self._baseurl + path,
                    headers=headers,
                    data=data, # For GET, data is typically None or query params in URL
                )
                _verify_response_or_raise(response)

                text_response = await response.text()
                # _LOGGER.info("[API] <-- %s %s", response.status, text_response)
                if not text_response: # Handle empty responses for POST/302 potentially
                    return {}
                return xmltodict.parse(text_response)

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise ZeptrionAirApiClientCommunicationError(
                msg,
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise ZeptrionAirApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise ZeptrionAirApiClientError(
                msg,
            ) from exception

    async def _api_post_url_encoded_wrapper(
        self,
        path: str,
        data: dict[str, Any], # Expecting a dict to be URL-encoded
    ) -> dict[str, Any]:
        """Post URL-encoded data to the API and parse XML response."""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        encoded_data = urlencode(data)
        try:
            # _LOGGER.info("[API] --> POST %s with %s", self._baseurl + path, encoded_data)
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method="post",
                    url=self._baseurl + path,
                    headers=headers,
                    data=encoded_data,
                )
                # Responses to POST /zrap/chctrl are 302 Found,
                # aiohttp follows redirects by default.
                # The final response after redirect might be empty or HTML.
                # We attempt to parse XML for consistency, but handle errors.
                _verify_response_or_raise(response)


                # The API doc says 302 for /zrap/chctrl.
                # aiohttp handles redirects by default. The final page might not be XML.
                # Or it might be an error page in XML.
                # If the final response is empty or not XML, xmltodict will raise an ExpatError.
                text_response = await response.text()
                # _LOGGER.info("[API] <-- %s %s", response.status, text_response)
                if not text_response: # Handle empty responses
                    return {}
                try:
                    return xmltodict.parse(text_response)
                except xmltodict.expat.ExpatError:
                    _LOGGER.debug("Response was not XML after POST to %s: %s", path, text_response)
                    return {"non_xml_response": text_response}


        except TimeoutError as exception:
            msg = f"Timeout error posting URL-encoded data to {path} - {exception}"
            raise ZeptrionAirApiClientCommunicationError(
                msg,
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error posting URL-encoded data to {path} - {exception}"
            raise ZeptrionAirApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened posting URL-encoded data to {path}! - {exception}"
            raise ZeptrionAirApiClientError(
                msg,
            ) from exception

    async def async_get_channel_scan_info(self, channel: int) -> dict[str, Any]:
        """Get the scan info for a specific channel."""
        return await self._api_xml_wrapper(
            method="get",
            path=f"/zrap/chscan/ch{channel}",
        )

    async def async_get_all_channels_scan_info(self) -> dict[str, Any]:
        """Get the scan info for all channels."""
        return await self._api_xml_wrapper(
            method="get",
            path="/zrap/chscan",
        )

    async def async_channel_open(self, channel: int) -> dict[str, Any]:
        """Send 'open' command to a channel."""
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data={"cmd": "open"},
        )

    async def async_channel_close(self, channel: int) -> dict[str, Any]:
        """Send 'close' command to a channel."""
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data={"cmd": "close"},
        )

    async def async_channel_stop(self, channel: int) -> dict[str, Any]:
        """Send 'stop' command to a channel."""
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data={"cmd": "stop"},
        )

    async def async_channel_move_open(self, channel: int, time_ms: int) -> dict[str, Any]:
        """Send 'move_open_{time_ms}' command to a channel."""
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data={"cmd": f"move_open_{time_ms}"},
        )

    async def async_channel_move_close(self, channel: int, time_ms: int) -> dict[str, Any]:
        """Send 'move_close_{time_ms}' command to a channel."""
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data={"cmd": f"move_close_{time_ms}"},
        )

    async def async_channel_recall_s1(self, channel: int) -> dict[str, Any]:
        """Send 'recall_s1' command to a channel."""
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data={"cmd": "recall_s1"},
        )

    async def async_channel_recall_s2(self, channel: int) -> dict[str, Any]:
        """Send 'recall_s2' command to a channel."""
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data={"cmd": "recall_s2"},
        )

    async def async_channel_recall_s3(self, channel: int) -> dict[str, Any]:
        """Send 'recall_s3' command to a channel."""
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data={"cmd": "recall_s3"},
        )

    async def async_channel_recall_s4(self, channel: int) -> dict[str, Any]:
        """Send 'recall_s4' command to a channel."""
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data={"cmd": "recall_s4"},
        )

    async def async_get_channel_descriptions(self) -> dict[str, Any]:
        """Fetch channel descriptions from /zrap/chdes."""
        # This assumes /zrap/chdes returns descriptions for all configured channels.
        # If it needs to be called per channel (e.g., /zrap/chdes/ch1), this design would need adjustment.
        _LOGGER.debug(f"Fetching channel descriptions from /zrap/chdes for {self._hostname}")
        try:
            response_data = await self._api_xml_wrapper(
                method="get",
                path="/zrap/chdes", # Assuming this is the correct path for all channel descriptions
            )
            # Add logging for the raw response if helpful for debugging later
            # _LOGGER.debug(f"/zrap/chdes response: {response_data}")
            return response_data
        except ZeptrionAirApiClientCommunicationError as e:
            _LOGGER.error(f"Communication error fetching channel descriptions from {self._hostname}: {e}")
            # Re-raise or return empty dict/None to allow caller to handle
            raise # Or handle more gracefully if preferred (e.g., return {})
        except ZeptrionAirApiClientError as e: # Catch other client errors
            _LOGGER.error(f"API client error fetching channel descriptions from {self._hostname}: {e}")
            raise # Or return {}

    async def async_channel_on(self, channel: int) -> dict[str, Any]:
        """Send 'on' command to a channel for light control."""
        _LOGGER.debug(f"Sending 'on' command to channel {channel} on {self._hostname}")
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data={"cmd": "on"},
        )

    async def async_channel_off(self, channel: int) -> dict[str, Any]:
        """Send 'off' command to a channel for light control."""
        _LOGGER.debug(f"Sending 'off' command to channel {channel} on {self._hostname}")
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data={"cmd": "off"},
        )

    async def async_channel_set_brightness(self, channel: int, brightness_0_255: int) -> dict[str, Any]:
        """Send 'dim' command with brightness value to a channel."""
        # Convert HA brightness (0-255) to API brightness (0-100)
        api_brightness = int(round(brightness_0_255 * 100 / 255))

        # Ensure api_brightness is within the 0-100 range after conversion,
        # though standard rounding should keep it within bounds if input is 0-255.
        api_brightness = max(0, min(100, api_brightness))

        data_payload = {"cmd": "dim", "val": api_brightness}
        
        _LOGGER.debug(
            f"Sending 'dim' command to channel {channel} on {self._hostname} "
            f"with HA brightness {brightness_0_255} (API value: {api_brightness})"
        )
        
        return await self._api_post_url_encoded_wrapper(
            path=f"/zrap/chctrl/ch{channel}",
            data=data_payload,
        )


