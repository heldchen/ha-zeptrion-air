"""Adds config flow for Zeptrion Air."""

from __future__ import annotations

import zeroconf

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.components import onboarding
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    ZeptrionAirApiClient,
    ZeptrionAirApiClientCommunicationError,
    ZeptrionAirApiClientError,
)
from .const import DOMAIN, LOGGER, CONF_NAME, CONF_HOSTNAME, CONF_IP_ADDRESS


class ZeptrionAirFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Zeptrion Air."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    discovery_info: dict

    def __init__(self):
        """Initialize the Zeptrion Air config flow."""
        self.discovery_info = None

    async def async_step_zeroconf(self, discovery_info: zeroconf.ZeroconfServiceInfo):
        """Prepare configuration for a discovered Zeptrion Air device."""
        # LOGGER.info("Zeroconf discovery_info: %s", discovery_info)

        self.discovery_info = {
            CONF_NAME: discovery_info.name,
            CONF_HOSTNAME: discovery_info.hostname[:-1],
            CONF_IP_ADDRESS: str(discovery_info.ip_address),
            'port': discovery_info.port,
            'properties': discovery_info.properties
        }

        await self.async_set_unique_id(unique_id=self.discovery_info.get(CONF_NAME))

        self._abort_if_unique_id_configured(
            updates={
                CONF_HOSTNAME: self.discovery_info.get(CONF_HOSTNAME),
                CONF_IP_ADDRESS: self.discovery_info.get(CONF_IP_ADDRESS),
            }
        )

        self.context.update(
            {
                "title_placeholders": {
                    CONF_NAME: self.discovery_info.get(CONF_HOSTNAME).replace('.local', ''),
                },
            }
        )

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm a discovery."""

        if user_input is not None:
            try:
                api = ZeptrionAirApiClient(
                    hostname=self.discovery_info.get(CONF_HOSTNAME),
                    session=async_create_clientsession(self.hass),
                )

                device_info = await api.async_get_device_identification()
                LOGGER.info("ZAPI: get_device_identification: %s", device_info)

            except ZeptrionAirApiClientCommunicationError as exception:
                LOGGER.error(exception)
                return self.async_abort(reason="connection")
            except ZeptrionAirApiClientError as exception:
                LOGGER.exception(exception)
                return self.async_abort(reason="unknown")

            return self.async_create_entry(
                title=self.discovery_info.get(CONF_HOSTNAME).replace('.local', ''),
                description='Zeptrion Air Hub',
                data={
                    CONF_HOSTNAME: self.discovery_info.get(CONF_HOSTNAME),
                    CONF_IP_ADDRESS: self.discovery_info.get(CONF_IP_ADDRESS),
                },
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                CONF_NAME: self.discovery_info.get(CONF_NAME),
                CONF_HOSTNAME: self.discovery_info.get(CONF_HOSTNAME),
                CONF_IP_ADDRESS: self.discovery_info.get(CONF_IP_ADDRESS),
            },
        )
    