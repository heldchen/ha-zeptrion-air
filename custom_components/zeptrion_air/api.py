"""Sample API Client."""

from __future__ import annotations

import logging
import json
import socket
import xmltodict

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

    async def async_get_device_identification(self) -> Any:
        """Get the device identification from the API."""
        return await self._api_xml_wrapper(
            method="get",
            path="/zrap/id",
        )

    async def _api_json_wrapper(
        self,
        method: str,
        path: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        """Get information from the API."""
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
        data: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        """Get information from the API."""
        try:
            # _LOGGER.info("[API] --> %s %s", method, self._baseurl + path)
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=self._baseurl + path,
                    headers=headers,
                    data=data,
                )
                _verify_response_or_raise(response)

                data = await response.text()
                # _LOGGER.info("[API] <-- %s %s", response.status, data)
                return xmltodict.parse(data)

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

