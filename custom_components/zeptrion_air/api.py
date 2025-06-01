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


    async def _api_json_wrapper(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get information from the API via JSON with retry logic."""
        retries = 3
        last_exception = None

        for attempt in range(retries):
            try:
                # _LOGGER.info("[API] --> %s %s (Attempt %d/%d)", method, self._baseurl + path, attempt + 1, retries)
                async with async_timeout.timeout(10):
                    response = await self._session.request(
                        method=method,
                        url=self._baseurl + path,
                        headers=headers,
                        json=data,
                    )
                    _verify_response_or_raise(response)

                    json_data = await response.json() # Renamed variable to avoid conflict
                    # _LOGGER.info("[API] <-- %s %s", response.status, json_data)
                    return json_data

            except ClientResponseError as error:
                last_exception = error
                if error.status == 500:
                    if attempt < retries - 1:
                        delay = 0.5 * (2 ** attempt) # 0.5s, then 1s
                        _LOGGER.warning(
                            "API request %s %s failed with status 500 (attempt %d/%d). Retrying in %.1f seconds...",
                            method, self._baseurl + path, attempt + 1, retries, delay
                        )
                        await asyncio.sleep(delay)
                        continue # Go to next retry iteration
                    else:
                        _LOGGER.error(
                            "API request %s %s failed with status 500 after %d attempts.",
                            method, self._baseurl + path, retries
                        )
                        # Re-raise the last caught ClientResponseError if all retries exhausted
                        raise ZeptrionAirApiClientCommunicationError(
                            f"API request failed after {retries} retries with status 500: {error}",
                        ) from error
                else:
                    # Not a 500 error, re-raise immediately as a communication error
                    msg = f"Error fetching information - {error}"
                    raise ZeptrionAirApiClientCommunicationError(
                        msg,
                    ) from error
            except TimeoutError as exception:
                last_exception = exception
                # This is an asyncio.TimeoutError from async_timeout.timeout(10)
                if attempt < retries - 1:
                    delay = 0.5 * (2 ** attempt) # Using same delay logic for timeout
                    _LOGGER.warning(
                        "Timeout error fetching information for %s %s (attempt %d/%d). Retrying in %.1f seconds... - %s",
                        method, self._baseurl + path, attempt + 1, retries, delay, exception
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    _LOGGER.error(
                        "Timeout error fetching information for %s %s after %d attempts. - %s",
                        method, self._baseurl + path, retries, exception
                    )
                    msg = f"Timeout error fetching information after {retries} attempts - {exception}"
                    raise ZeptrionAirApiClientCommunicationError(
                        msg,
                    ) from exception
            except (aiohttp.ClientError, socket.gaierror) as exception:
                # This catches other aiohttp client errors (not ClientResponseError) or DNS errors
                last_exception = exception
                # No retry for these errors, they are likely more permanent or network related
                msg = f"Error fetching information - {exception}"
                raise ZeptrionAirApiClientCommunicationError(
                    msg,
                ) from exception
            except Exception as exception:  # pylint: disable=broad-except
                last_exception = exception
                # Catch any other unexpected error
                msg = f"Something really wrong happened! - {exception}"
                raise ZeptrionAirApiClientError(
                    msg,
                ) from exception
        
        # This part should ideally not be reached if retries are exhausted and exceptions are re-raised.
        # However, to satisfy linters and ensure an exception is always raised if the loop finishes.
        if last_exception:
            raise ZeptrionAirApiClientError(
                f"API request failed after all retries. Last error: {last_exception}"
            ) from last_exception
        # Should not happen, but as a fallback:
        raise ZeptrionAirApiClientError("API request failed after all retries without specific exception.")


    async def _api_xml_wrapper(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get information from the API via XML with retry logic."""
        retries = 3
        last_exception = None

        for attempt in range(retries):
            try:
                # _LOGGER.info("[API-XML] --> %s %s (Attempt %d/%d)", method, self._baseurl + path, attempt + 1, retries)
                async with async_timeout.timeout(10):
                    response = await self._session.request(
                        method=method,
                        url=self._baseurl + path,
                        headers=headers,
                        data=data, # For GET, data is typically None or query params in URL
                    )
                    _verify_response_or_raise(response)

                    text_response = await response.text()
                    # _LOGGER.info("[API-XML] <-- %s %s", response.status, text_response)
                    if not text_response: # Handle empty responses
                        return {}
                    return xmltodict.parse(text_response)

            except ClientResponseError as error:
                last_exception = error
                if error.status == 500:
                    if attempt < retries - 1:
                        delay = 0.5 * (2 ** attempt) # 0.5s, then 1s
                        _LOGGER.warning(
                            "API-XML request %s %s failed with status 500 (attempt %d/%d). Retrying in %.1f seconds...",
                            method, self._baseurl + path, attempt + 1, retries, delay
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        _LOGGER.error(
                            "API-XML request %s %s failed with status 500 after %d attempts.",
                            method, self._baseurl + path, retries
                        )
                        raise ZeptrionAirApiClientCommunicationError(
                            f"API-XML request failed after {retries} retries with status 500: {error}",
                        ) from error
                else:
                    msg = f"Error fetching XML information - {error}"
                    raise ZeptrionAirApiClientCommunicationError(
                        msg,
                    ) from error
            except TimeoutError as exception: # This is an asyncio.TimeoutError from async_timeout
                last_exception = exception
                if attempt < retries - 1:
                    delay = 0.5 * (2 ** attempt)
                    _LOGGER.warning(
                        "Timeout error fetching XML information for %s %s (attempt %d/%d). Retrying in %.1f seconds... - %s",
                        method, self._baseurl + path, attempt + 1, retries, delay, exception
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    _LOGGER.error(
                        "Timeout error fetching XML information for %s %s after %d attempts. - %s",
                        method, self._baseurl + path, retries, exception
                    )
                    msg = f"Timeout error fetching XML information after {retries} attempts - {exception}"
                    raise ZeptrionAirApiClientCommunicationError(
                        msg,
                    ) from exception
            except (aiohttp.ClientError, socket.gaierror) as exception:
                last_exception = exception
                msg = f"Error fetching XML information - {exception}"
                raise ZeptrionAirApiClientCommunicationError(
                    msg,
                ) from exception
            except xmltodict.expat.ExpatError as exception: # Specific error for XML parsing
                last_exception = exception
                _LOGGER.error("Failed to parse XML response from %s %s: %s", method, self._baseurl + path, exception)
                # Do not retry on parsing errors, raise specific error
                raise ZeptrionAirApiClientError(
                    f"Failed to parse XML response: {exception}",
                ) from exception
            except Exception as exception:  # pylint: disable=broad-except
                last_exception = exception
                msg = f"Something really wrong happened in XML wrapper! - {exception}"
                raise ZeptrionAirApiClientError(
                    msg,
                ) from exception

        # Fallback if loop completes, should be covered by re-raises in practice
        if last_exception:
            raise ZeptrionAirApiClientError(
                f"API-XML request failed after all retries. Last error: {last_exception}"
            ) from last_exception
        # Should not happen:
        raise ZeptrionAirApiClientError("API-XML request failed after all retries without specific exception.")

    async def _api_post_url_encoded_wrapper(
        self,
        path: str,
        data: dict[str, Any], # Expecting a dict to be URL-encoded
    ) -> dict[str, Any]:
        """Post URL-encoded data to the API and parse XML response with retry logic."""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        encoded_data = urlencode(data)
        retries = 3
        last_exception = None

        for attempt in range(retries):
            try:
                # _LOGGER.info("[API-POST] --> POST %s with %s (Attempt %d/%d)", self._baseurl + path, encoded_data, attempt + 1, retries)
                async with async_timeout.timeout(10):
                    response = await self._session.request(
                        method="post",
                        url=self._baseurl + path,
                        headers=headers,
                        data=encoded_data,
                    )
                    _verify_response_or_raise(response)

                    text_response = await response.text()
                    # _LOGGER.info("[API-POST] <-- %s %s", response.status, text_response)
                    if not text_response: # Handle empty responses
                        return {}
                    try:
                        return xmltodict.parse(text_response)
                    except xmltodict.expat.ExpatError:
                        _LOGGER.debug("Response was not XML after POST to %s (attempt %d/%d): %s", path, attempt + 1, retries, text_response)
                        # This is tricky: a non-XML response might be "success" for some POSTs
                        # or an HTML error page. We return it as is, and the caller must decide.
                        # No retry here as the server did respond.
                        return {"non_xml_response": text_response}

            except ClientResponseError as error:
                last_exception = error
                if error.status == 500:
                    if attempt < retries - 1:
                        delay = 0.5 * (2 ** attempt) # 0.5s, then 1s
                        _LOGGER.warning(
                            "API-POST request to %s failed with status 500 (attempt %d/%d). Retrying in %.1f seconds...",
                            path, attempt + 1, retries, delay
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        _LOGGER.error(
                            "API-POST request to %s failed with status 500 after %d attempts.", path, retries
                        )
                        raise ZeptrionAirApiClientCommunicationError(
                            f"API-POST request to {path} failed after {retries} retries with status 500: {error}",
                        ) from error
                else:
                    # For other client errors (e.g., 400, 401, 403, 404), do not retry.
                    msg = f"Error posting URL-encoded data to {path} - {error}"
                    raise ZeptrionAirApiClientCommunicationError(msg) from error
            except TimeoutError as exception: # This is an asyncio.TimeoutError from async_timeout
                last_exception = exception
                if attempt < retries - 1:
                    delay = 0.5 * (2 ** attempt)
                    _LOGGER.warning(
                        "Timeout error posting URL-encoded data to %s (attempt %d/%d). Retrying in %.1f seconds... - %s",
                        path, attempt + 1, retries, delay, exception
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    _LOGGER.error(
                        "Timeout error posting URL-encoded data to %s after %d attempts. - %s",
                        path, retries, exception
                    )
                    msg = f"Timeout error posting URL-encoded data to {path} after {retries} attempts - {exception}"
                    raise ZeptrionAirApiClientCommunicationError(msg) from exception
            except (aiohttp.ClientError, socket.gaierror) as exception: # Other client/network errors
                last_exception = exception
                msg = f"Error posting URL-encoded data to {path} - {exception}"
                raise ZeptrionAirApiClientCommunicationError(msg) from exception
            # xmltodict.expat.ExpatError is handled inside the try block for successful requests
            except Exception as exception:  # pylint: disable=broad-except
                last_exception = exception
                msg = f"Something really wrong happened posting URL-encoded data to {path}! - {exception}"
                raise ZeptrionAirApiClientError(msg) from exception

        # Fallback if loop completes, should be covered by re-raises
        if last_exception:
            raise ZeptrionAirApiClientError(
                f"API-POST request to {path} failed after all retries. Last error: {last_exception}"
            ) from last_exception
        # Should not happen:
        raise ZeptrionAirApiClientError(f"API-POST request to {path} failed after all retries without specific exception.")

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


