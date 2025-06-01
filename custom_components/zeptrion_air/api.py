"""Sample API Client."""

from __future__ import annotations

import asyncio # Added import
import logging
import json
import socket
import xmltodict
from urllib.parse import urlencode # Added import

from typing import Any

import aiohttp
from aiohttp import ClientResponseError # Added import
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

# Typing helper for the request coroutine
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


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

    async def async_get_rssi(self) -> int | None:
        """Fetch and parse the RSSI value from the device."""
        response_data = None # Initialize response_data
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
                if dbm_value_str is None: # Handle cases where dbm tag might be empty e.g. <dbm/>
                    _LOGGER.error(
                        "RSSI 'dbm' tag was empty in response from %s. Response: %s",
                        self._hostname,
                        response_data,
                    )
                    return None
                return int(dbm_value_str)
            else:
                _LOGGER.error(
                    "Unexpected structure for RSSI data from %s. Missing 'rssi' or 'dbm' key. Response: %s",
                    self._hostname,
                    response_data,
                )
                return None
        except (ValueError, TypeError) as e: # ValueError for int(), TypeError for None access
            _LOGGER.error(
                "Failed to parse RSSI value from %s: %s. Response data: %s",
                self._hostname,
                e,
                response_data, # type: ignore # response_data might be unbound if _api_xml_wrapper failed early
            )
            return None
        except ZeptrionAirApiClientCommunicationError as e:
            # Logged by _api_xml_wrapper, re-raise or handle if needed differently here
            _LOGGER.debug("Communication error fetching RSSI for %s: %s (already logged by wrapper)", self._hostname, e)
            raise # Re-raise to be handled by the caller (e.g. coordinator)
        except ZeptrionAirApiClientError as e:
            _LOGGER.error("Generic API client error fetching RSSI for %s: %s", self._hostname, e)
            # Depending on desired behavior, could return None or re-raise
            return None # Or raise, if the coordinator should handle this as a critical failure
        except Exception as e: # Catch any other unexpected errors during parsing
            _LOGGER.error(
                "Unexpected error fetching or parsing RSSI from %s: %s. Response data: %s",
                self._hostname,
                e,
                response_data, # type: ignore
                exc_info=True # Include stack trace for unexpected errors
            )
            return None

    async def _execute_request_with_retry(
        self,
        request_coro: Callable[..., Awaitable[T]],
        method_name_for_log: str,
        path_for_log: str,
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute a request coroutine with retry logic for specific errors."""
        retries = 3
        last_exception: Exception | None = None

        for attempt in range(retries):
            try:
                # Pass through args and kwargs to the actual request coroutine
                return await request_coro(*args, **kwargs)
            except ClientResponseError as error:
                last_exception = error
                if error.status == 500:
                    if attempt < retries - 1:
                        delay = 0.5 * (2**attempt)  # 0.5s, then 1s
                        _LOGGER.warning(
                            "Request %s %s failed with status 500 (attempt %d/%d). Retrying in %.1f seconds...",
                            method_name_for_log, path_for_log, attempt + 1, retries, delay
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        _LOGGER.error(
                            "Request %s %s failed with status 500 after %d attempts.",
                            method_name_for_log, path_for_log, retries
                        )
                        # Re-raise the original error to be wrapped by the caller
                        raise
                else:
                    # Not a 500 error, re-raise immediately for the caller to handle
                    raise
            except TimeoutError as exception: # This is an asyncio.TimeoutError
                last_exception = exception
                if attempt < retries - 1:
                    delay = 0.5 * (2**attempt)
                    _LOGGER.warning(
                        "Timeout error for %s %s (attempt %d/%d). Retrying in %.1f seconds... - %s",
                        method_name_for_log, path_for_log, attempt + 1, retries, delay, exception
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    _LOGGER.error(
                        "Timeout error for %s %s after %d attempts. - %s",
                        method_name_for_log, path_for_log, retries, exception
                    )
                    # Re-raise the original error to be wrapped by the caller
                    raise
            # Other exceptions (like aiohttp.ClientError, socket.gaierror, xmltodict.expat.ExpatError, etc.)
            # will propagate directly from request_coro and should be handled by the calling wrapper.

        # This part should only be reached if all retries failed and an exception was caught and handled by 'continue'
        # If an exception was re-raised, it would have exited the function.
        # Thus, if last_exception is set, it means retries were exhausted for a retryable error.
        if last_exception: # Should always be true if loop exhausted
            # Re-raise the last caught retryable exception if all retries are exhausted
            raise last_exception

        # Fallback, should ideally not be reached if logic is correct
        raise ZeptrionAirApiClientError(f"Request {method_name_for_log} {path_for_log} failed after all retries without specific exception.")


    async def _perform_json_request(
        self,
        method: str,
        path: str,
        json_payload: dict[str, Any] | None = None, # renamed data to json_payload
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Actual JSON request logic."""
        # _LOGGER.info("[API-JSON-PERFORM] --> %s %s", method, self._baseurl + path)
        async with async_timeout.timeout(10):
            response = await self._session.request(
                method=method,
                url=self._baseurl + path,
                headers=headers,
                json=json_payload, # use json_payload
            )
            _verify_response_or_raise(response)
            # _LOGGER.info("[API-JSON-PERFORM] <-- %s", response.status)
            return await response.json() # type: ignore[no-any-return]


    async def _api_json_wrapper(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None, # Original 'data' name for external consistency
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get information from the API via JSON with retry logic managed by helper."""
        try:
            return await self._execute_request_with_retry(
                self._perform_json_request,
                f"JSON {method}", # method_name_for_log
                path,             # path_for_log
                method,           # args for _perform_json_request
                path,             # args for _perform_json_request
                data,             # args for _perform_json_request (will be json_payload)
                headers,          # args for _perform_json_request
            )
        except ClientResponseError as error: # Caught from _execute_request_with_retry or _perform_json_request
            # If it's a non-500 or 500 after retries
            msg = f"Error fetching JSON information from {path} - {error}"
            raise ZeptrionAirApiClientCommunicationError(msg) from error
        except TimeoutError as exception: # Caught from _execute_request_with_retry after retries
            msg = f"Timeout error fetching JSON information from {path} after retries - {exception}"
            raise ZeptrionAirApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            # These are not retried by _execute_request_with_retry, they propagate from _perform_json_request
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
        # _LOGGER.info("[API-XML-PERFORM] --> %s %s", method, self._baseurl + path)
        async with async_timeout.timeout(10):
            response = await self._session.request(
                method=method,
                url=self._baseurl + path,
                headers=headers,
                data=data,
            )
            _verify_response_or_raise(response)
            text_response = await response.text()
            # _LOGGER.info("[API-XML-PERFORM] <-- %s", response.status)
            if not text_response:
                return {}
            try:
                return xmltodict.parse(text_response) # type: ignore[no-any-return]
            except xmltodict.expat.ExpatError as expat_error:
                _LOGGER.error("Failed to parse XML response from %s %s: %s. Response: %s", method, self._baseurl + path, expat_error, text_response[:200])
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
                f"XML {method}", # method_name_for_log
                path,            # path_for_log
                method,          # args for _perform_xml_request
                path,            # args for _perform_xml_request
                data,            # args for _perform_xml_request
                headers,         # args for _perform_xml_request
            )
        except ClientResponseError as error: # Caught from _execute_request_with_retry or _perform_xml_request
            msg = f"Error fetching XML information from {path} - {error}"
            raise ZeptrionAirApiClientCommunicationError(msg) from error
        except TimeoutError as exception: # Caught from _execute_request_with_retry after retries
            msg = f"Timeout error fetching XML information from {path} after retries - {exception}"
            raise ZeptrionAirApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Client/network error fetching XML information from {path} - {exception}"
            raise ZeptrionAirApiClientCommunicationError(msg) from exception
        except ZeptrionAirApiClientError: # Catch specific XML parsing error re-raised
            raise # Already correctly typed and logged
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened fetching XML from {path}! - {exception}"
            raise ZeptrionAirApiClientError(msg) from exception


    async def _perform_post_url_encoded_request(
        self,
        path: str,
        form_data: dict[str, Any], # Changed name from 'data'
    ) -> dict[str, Any]:
        """Actual POST URL-encoded request logic."""
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        encoded_data = urlencode(form_data)
        # _LOGGER.info("[API-POST-PERFORM] --> POST %s with %s", self._baseurl + path, encoded_data)
        async with async_timeout.timeout(10):
            response = await self._session.request(
                method="post",
                url=self._baseurl + path,
                headers=headers,
                data=encoded_data,
            )
            _verify_response_or_raise(response)
            text_response = await response.text()
            # _LOGGER.info("[API-POST-PERFORM] <-- %s", response.status)
            if not text_response:
                return {}
            try:
                return xmltodict.parse(text_response) # type: ignore[no-any-return]
            except xmltodict.expat.ExpatError:
                _LOGGER.debug("Response was not XML after POST to %s: %s", path, text_response[:200])
                return {"non_xml_response": text_response}


    async def _api_post_url_encoded_wrapper(
        self,
        path: str,
        data: dict[str, Any], # Original 'data' name for external consistency
    ) -> dict[str, Any]:
        """Post URL-encoded data to the API and parse XML response with retry logic managed by helper."""
        try:
            return await self._execute_request_with_retry(
                self._perform_post_url_encoded_request,
                "POST URL-ENCODED", # method_name_for_log
                path,               # path_for_log
                path,               # args for _perform_post_url_encoded_request
                data,               # args for _perform_post_url_encoded_request (will be form_data)
            )
        except ClientResponseError as error: # Caught from _execute_request_with_retry
            msg = f"Error posting URL-encoded data to {path} - {error}"
            raise ZeptrionAirApiClientCommunicationError(msg) from error
        except TimeoutError as exception: # Caught from _execute_request_with_retry after retries
            msg = f"Timeout error posting URL-encoded data to {path} after retries - {exception}"
            raise ZeptrionAirApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Client/network error posting URL-encoded data to {path} - {exception}"
            raise ZeptrionAirApiClientCommunicationError(msg) from exception
        # Note: ExpatError is handled within _perform_post_url_encoded_request and returns a dict,
        # so it won't propagate here as an exception unless re-raised differently.
        # ZeptrionAirApiClientError could be raised if XML parsing fails critically in _perform_xml_request if it were used.
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
            # _LOGGER.debug(f"/zrap/chdes response: {response_data}")
            return response_data
        except ZeptrionAirApiClientCommunicationError as e:
            _LOGGER.error(f"Communication error fetching channel descriptions from {self._hostname}: {e}")
            raise
        except ZeptrionAirApiClientError as e: # Catch other client errors
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


