"""Zeptrion Air API Client."""

from __future__ import annotations

import asyncio
import logging
import json
import random
import socket
import xmltodict
from urllib.parse import urlencode

from typing import Any, ParamSpec, TypeVar

import aiohttp
from aiohttp import ClientResponseError
import async_timeout

_LOGGER = logging.getLogger(__name__)

# Type variables for generic retry wrapper
T = TypeVar("T")
P = ParamSpec("P")


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
    """Zeptrion Air API Client."""

    def __init__(
        self,
        hostname: str,
        session: aiohttp.ClientSession,
        max_retries: int = 3,
        base_delay: float = 0.5,
        enable_jitter: bool = True,
        request_timeout: float = 10.0,
    ) -> None:
        self._hostname = hostname
        self._baseurl = f'http://{hostname}'
        self._session = session
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._enable_jitter = enable_jitter
        self._request_timeout = request_timeout

    async def async_get_device_identification(self) -> dict[str, Any]:
        """Get the device identification from the API."""
        return await self._api_xml_wrapper(
            method="get",
            path="/zrap/id",
        )

    async def async_get_rssi(self) -> int | None:
        """Fetch and parse the RSSI value from the device."""
        response_data = None
        try:
            response_data = await self._api_xml_wrapper(
                method="get",
                path="/zrap/rssi",
            )
            # Expected structure from xmltodict: {'rssi': {'dbm': '-62'}}
            if response_data and 'rssi' in response_data and \
               isinstance(response_data['rssi'], dict) and \
               'dbm' in response_data['rssi']:
                dbm_value_str = response_data['rssi']['dbm']
                if dbm_value_str is None:  # Handle cases where dbm tag might be empty e.g. <dbm/>
                    _LOGGER.error(
                        f"RSSI 'dbm' tag was empty in response from {self._hostname}. Response: {response_data}"
                    )
                    return None
                return int(dbm_value_str)
            else:
                _LOGGER.error(
                    f"Unexpected structure for RSSI data from {self._hostname}. "
                    f"Missing 'rssi' or 'dbm' key. Response: {response_data}"
                )
                return None
        except (ValueError, TypeError) as e:  # ValueError for int(), TypeError for None access
            _LOGGER.error(
                f"Failed to parse RSSI value from {self._hostname}: {e}. Response data: {response_data}"
            )
            return None
        except ZeptrionAirApiClientCommunicationError as e:
            # Logged by _api_xml_wrapper, re-raise or handle if needed differently here
            _LOGGER.debug(f"Communication error fetching RSSI for {self._hostname}: {e} (already logged by wrapper)")
            raise  # Re-raise to be handled by the caller (e.g. coordinator)
        except ZeptrionAirApiClientError as e:
            _LOGGER.error(f"Generic API client error fetching RSSI for {self._hostname}: {e}")
            # Depending on desired behavior, could return None or re-raise
            return None  # Or raise, if the coordinator should handle this as a critical failure
        except Exception as e:  # Catch any other unexpected errors during parsing
            _LOGGER.error(
                f"Unexpected error fetching or parsing RSSI from {self._hostname}: {e}. "
                f"Response data: {response_data}",
                exc_info=True
            )
            return None

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt with exponential backoff and optional jitter."""
        base_delay = self._base_delay * (2 ** attempt)
        if self._enable_jitter:
            jitter = random.uniform(0, 0.1)
            return base_delay + jitter
        return base_delay

    async def _execute_request_with_retry(
        self,
        request_coro: Callable[P, Awaitable[T]],
        method_name_for_log: str,
        path_for_log: str,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Execute a request coroutine with retry logic for specific errors."""
        for attempt in range(self._max_retries):
            try:
                return await request_coro(*args, **kwargs)
            except ClientResponseError as error:
                if error.status != 500 or attempt == self._max_retries - 1:
                    _LOGGER.error(
                        f"Request {method_name_for_log} {path_for_log} failed with status {error.status} "
                        f"after {attempt + 1} attempts."
                    )
                    raise
                
                delay = self._calculate_retry_delay(attempt)
                _LOGGER.warning(
                    f"Request {method_name_for_log} {path_for_log} failed with status 500 "
                    f"(attempt {attempt + 1}/{self._max_retries}). Retrying in {delay:.1f} seconds..."
                )
                await asyncio.sleep(delay)
                
            except asyncio.TimeoutError as error:
                if attempt == self._max_retries - 1:
                    _LOGGER.error(
                        f"Timeout error for {method_name_for_log} {path_for_log} after "
                        f"{self._max_retries} attempts: {error}"
                    )
                    raise
                    
                delay = self._calculate_retry_delay(attempt)
                _LOGGER.warning(
                    f"Timeout error for {method_name_for_log} {path_for_log} "
                    f"(attempt {attempt + 1}/{self._max_retries}). Retrying in {delay:.1f} seconds: {error}"
                )
                await asyncio.sleep(delay)
        
        # This line should never be reached due to the logic above
        raise ZeptrionAirApiClientError(
            f"Request {method_name_for_log} {path_for_log} failed unexpectedly after all retries"
        )

    async def _perform_json_request(
        self,
        method: str,
        path: str,
        json_payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Actual JSON request logic."""
        async with async_timeout.timeout(self._request_timeout):
            response = await self._session.request(
                method=method,
                url=f"{self._baseurl}{path}",
                headers=headers,
                json=json_payload,
            )
            _verify_response_or_raise(response)
            return await response.json()  # type: ignore[no-any-return]

    async def _api_json_wrapper(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get information from the API via JSON with retry logic managed by helper."""
        try:
            return await self._execute_request_with_retry(
                self._perform_json_request,
                f"JSON {method}",
                path,
                method,
                path,
                data,
                headers,
            )
        except ClientResponseError as error:
            # If it's a non-500 or 500 after retries
            msg = f"Error fetching JSON information from {path} - {error}"
            raise ZeptrionAirApiClientCommunicationError(msg) from error
        except asyncio.TimeoutError as exception:
            msg = f"Timeout error fetching JSON information from {path} after retries - {exception}"
            raise ZeptrionAirApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Client/network error fetching JSON information from {path} - {exception}"
            raise ZeptrionAirApiClientCommunicationError(msg) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened fetching JSON from {path}! - {exception}"
            raise ZeptrionAirApiClientError(msg) from exception

    async def _perform_xml_request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Actual XML request logic."""
        async with async_timeout.timeout(self._request_timeout):
            response = await self._session.request(
                method=method,
                url=f"{self._baseurl}{path}",
                headers=headers,
                data=data,
            )
            _verify_response_or_raise(response)
            text_response = await response.text()
            if not text_response:
                return {}
            try:
                return xmltodict.parse(text_response)  # type: ignore[no-any-return]
            except xmltodict.expat.ExpatError as expat_error:
                _LOGGER.error(
                    f"Failed to parse XML response from {method} {self._baseurl}{path}: {expat_error}. "
                    f"Response: {text_response[:200]}"
                )
                # Raise specific error that won't be retried by _execute_request_with_retry's specific catches
                raise ZeptrionAirApiClientError(f"Failed to parse XML response: {expat_error}") from expat_error

    async def _api_xml_wrapper(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get information from the API via XML with retry logic managed by helper."""
        try:
            return await self._execute_request_with_retry(
                self._perform_xml_request,
                f"XML {method}",
                path,
                method,
                path,
                data,
                headers,
            )
        except ClientResponseError as error:
            msg = f"Error fetching XML information from {path} - {error}"
            raise ZeptrionAirApiClientCommunicationError(msg) from error
        except asyncio.TimeoutError as exception:
            msg = f"Timeout error fetching XML information from {path} after retries - {exception}"
            raise ZeptrionAirApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Client/network error fetching XML information from {path} - {exception}"
            raise ZeptrionAirApiClientCommunicationError(msg) from exception
        except ZeptrionAirApiClientError:
            raise
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened fetching XML from {path}! - {exception}"
            raise ZeptrionAirApiClientError(msg) from exception

    async def _perform_post_url_encoded_request(
        self,
        path: str,
        form_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Actual POST URL-encoded request logic."""
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        encoded_data = urlencode(form_data)
        async with async_timeout.timeout(self._request_timeout):
            response = await self._session.request(
                method="post",
                url=f"{self._baseurl}{path}",
                headers=headers,
                data=encoded_data,
            )
            _verify_response_or_raise(response)
            text_response = await response.text()
            if not text_response:
                return {}
            try:
                return xmltodict.parse(text_response)  # type: ignore[no-any-return]
            except xmltodict.expat.ExpatError:
                _LOGGER.debug(f"Response was not XML after POST to {path}: {text_response[:200]}")
                return {"non_xml_response": text_response}

    async def _api_post_url_encoded_wrapper(
        self,
        path: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Post URL-encoded data to the API and parse XML response with retry logic managed by helper."""
        try:
            return await self._execute_request_with_retry(
                self._perform_post_url_encoded_request,
                "POST URL-ENCODED",
                path,
                path,
                data,
            )
        except ClientResponseError as error:
            msg = f"Error posting URL-encoded data to {path} - {error}"
            raise ZeptrionAirApiClientCommunicationError(msg) from error
        except asyncio.TimeoutError as exception:
            msg = f"Timeout error posting URL-encoded data to {path} after retries - {exception}"
            raise ZeptrionAirApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Client/network error posting URL-encoded data to {path} - {exception}"
            raise ZeptrionAirApiClientCommunicationError(msg) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened posting URL-encoded data to {path}! - {exception}"
            raise ZeptrionAirApiClientError(msg) from exception

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
        _LOGGER.debug(f"Fetching channel descriptions from /zrap/chdes for {self._hostname}")
        try:
            response_data = await self._api_xml_wrapper(
                method="get",
                path="/zrap/chdes",
            )
            return response_data
        except ZeptrionAirApiClientCommunicationError as e:
            _LOGGER.error(f"Communication error fetching channel descriptions from {self._hostname}: {e}")
            raise
        except ZeptrionAirApiClientError as e:  # Catch other client errors
            _LOGGER.error(f"API client error fetching channel descriptions from {self._hostname}: {e}")
            raise

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
