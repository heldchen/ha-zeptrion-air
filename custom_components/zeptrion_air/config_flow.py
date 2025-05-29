"""Adds config flow for Zeptrion Air."""

from __future__ import annotations

from typing import Any # Added
import zeroconf

import voluptuous as vol
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME 
from homeassistant.core import callback 
from homeassistant.components import onboarding 
from homeassistant.helpers import selector 
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    ZeptrionAirApiClient,
    ZeptrionAirApiClientCommunicationError,
    ZeptrionAirApiClientError,
)
# Updated const import
from .const import (
    DOMAIN,
    LOGGER,
    CONF_NAME,
    CONF_HOSTNAME,
    CONF_IP_ADDRESS, # Added for clarity, was implicitly used
    CONF_STEP_DURATION_MS,
    DEFAULT_STEP_DURATION_MS,
    MIN_STEP_DURATION_MS,
    MAX_STEP_DURATION_MS,
)


class ZeptrionAirConfigFlow(config_entries.ConfigFlow, domain=DOMAIN): # Renamed class
    """Config flow for Zeptrion Air."""

    VERSION: int = 1
    CONNECTION_CLASS: str = config_entries.CONN_CLASS_LOCAL_POLL 

    @staticmethod
    @callback
    def async_get_options_flow( # Using ConfigEntry as ZeptrionAirConfigEntry not defined
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow: 
        """Get the options flow for this handler."""
        return ZeptrionAirOptionsFlowHandler(config_entry)

    discovery_info: dict[str, Any] # Typed attribute

    def __init__(self) -> None:
        """Initialize the Zeptrion Air config flow."""
        self.discovery_info = {} 

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult: 
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                api: ZeptrionAirApiClient = ZeptrionAirApiClient(
                    hostname=user_input[CONF_HOSTNAME], # CONF_HOSTNAME is str
                    session=async_create_clientsession(self.hass),
                )
                device_info: dict[str, Any] = await api.async_get_device_identification()
                LOGGER.info("ZAPI (user flow): get_device_identification: %s", device_info)
                
                # ---> START NEW LOGIC <---
                zrap_id_data: dict[str, Any] = device_info.get('id', {})
                serial_number: str | None = None
                if isinstance(zrap_id_data, dict): # Ensure zrap_id_data is a dict before .get
                    serial_number = zrap_id_data.get('sn')

                if serial_number:
                    await self.async_set_unique_id(serial_number)
                    self._abort_if_unique_id_configured()
                else:
                    LOGGER.error("Could not determine serial number from device %s for user setup.", user_input[CONF_HOSTNAME])
                    errors["base"] = "unknown" # Placeholder, ideally "no_serial"
                # ---> END NEW LOGIC <---
            except ZeptrionAirApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except ZeptrionAirApiClientError:
                errors["base"] = "unknown"
            except Exception: 
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            
            if not errors:
                # user_input[CONF_HOSTNAME] is str
                # user_input[CONF_STEP_DURATION_MS] is int (due to vol.Coerce(int))
                data_to_store: dict[str, str | int] = {
                    CONF_HOSTNAME: user_input[CONF_HOSTNAME],
                    CONF_STEP_DURATION_MS: user_input[CONF_STEP_DURATION_MS],
                }
                title: str = str(user_input[CONF_HOSTNAME]).replace(".local", "")

                return self.async_create_entry(title=title, data=data_to_store)

        DATA_SCHEMA: vol.Schema = vol.Schema(
            {
                vol.Required(CONF_HOSTNAME): str,
                vol.Optional(
                    CONF_STEP_DURATION_MS, 
                    default=DEFAULT_STEP_DURATION_MS
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_STEP_DURATION_MS, max=MAX_STEP_DURATION_MS)),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(self, discovery_info: zeroconf.ZeroconfServiceInfo) -> data_entry_flow.FlowResult:
        """Prepare configuration for a discovered Zeptrion Air device."""
        # discovery_info.name is str
        # discovery_info.hostname is str
        # discovery_info.ip_address is IPv4Address | IPv6Address
        # discovery_info.port is int
        # discovery_info.properties is Mapping[str, Any]
        
        hostname: str = discovery_info.hostname[:-1] if discovery_info.hostname.endswith('.') else discovery_info.hostname
        
        # Extract serial number from hostname
        unique_id_to_set: str = hostname # Fallback to full hostname
        try:
            # Hostname format is typically "zapp-SERIALNUMBER.local"
            # or just "zapp-SERIALNUMBER" if .local is already stripped (e.g. by discovery_info.name)
            name_part = hostname.split(".")[0] # Get "zapp-SERIALNUMBER"
            serial_from_hostname = name_part.split("-")[1] # Get "SERIALNUMBER"
            if serial_from_hostname: # Ensure it's not empty
                unique_id_to_set = serial_from_hostname
            else:
                LOGGER.warning(
                    "Could not parse serial number from hostname part: '%s' (derived from '%s'). Falling back to full hostname.",
                    name_part,
                    hostname
                )
        except IndexError:
            LOGGER.warning(
                "Could not parse serial number from hostname: '%s' due to unexpected format. Falling back to full hostname.",
                hostname,
                exc_info=True # Add exception info for better debugging
            )

        self.discovery_info = {
            CONF_NAME: discovery_info.name, 
            CONF_HOSTNAME: hostname, 
            CONF_IP_ADDRESS: str(discovery_info.ip_address),
            'port': discovery_info.port, # int
            'properties': dict(discovery_info.properties) # Convert Mapping to dict
        }
        
        await self.async_set_unique_id(unique_id_to_set)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOSTNAME: self.discovery_info[CONF_HOSTNAME],
                CONF_IP_ADDRESS: self.discovery_info[CONF_IP_ADDRESS],
            }
        )

        self.context.update(
            {
                "title_placeholders": {
                    CONF_NAME: self.discovery_info[CONF_HOSTNAME].replace('.local', ''),
                },
            }
        )
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult: 
        """Confirm a discovery and allow setting step duration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                api: ZeptrionAirApiClient = ZeptrionAirApiClient(
                    hostname=str(self.discovery_info[CONF_HOSTNAME]), 
                    session=async_create_clientsession(self.hass),
                )
                device_info_full: dict[str, Any] = await api.async_get_device_identification() 
                # ---> START NEW LOGIC <---
                zrap_id_data: dict[str, Any] = device_info_full.get('id', {})
                serial_number: str | None = None
                if isinstance(zrap_id_data, dict): # Ensure zrap_id_data is a dict
                    serial_number = zrap_id_data.get('sn')

                if serial_number:
                    # Unique ID might have been set by hostname in zeroconf step.
                    # Update it to the more stable serial number.
                    await self.async_set_unique_id(serial_number, raise_on_progress=False)
                    # Now, abort if this serial number is already configured for another entry.
                    # Pass updates to ensure IP/hostname are updated if serial matches an existing entry.
                    self._abort_if_unique_id_configured(updates={
                        CONF_HOSTNAME: str(self.discovery_info[CONF_HOSTNAME]),
                        CONF_IP_ADDRESS: str(self.discovery_info[CONF_IP_ADDRESS]),
                    })
                else:
                    LOGGER.error("Could not determine serial number from discovered device %s for confirmation step.", self.discovery_info.get(CONF_HOSTNAME))
                    errors["base"] = "unknown" # Placeholder, ideally "no_serial"
                # ---> END NEW LOGIC <---

            except ZeptrionAirApiClientCommunicationError:
                errors["base"] = "cannot_connect" 
            except ZeptrionAirApiClientError:
                errors["base"] = "unknown" 
            
            if not errors:
                # self.discovery_info[CONF_HOSTNAME] is str
                # self.discovery_info[CONF_IP_ADDRESS] is str
                # user_input[CONF_STEP_DURATION_MS] is int
                data_to_store: dict[str, str | int] = {
                    CONF_HOSTNAME: str(self.discovery_info[CONF_HOSTNAME]),
                    CONF_IP_ADDRESS: str(self.discovery_info[CONF_IP_ADDRESS]), 
                    CONF_STEP_DURATION_MS: user_input[CONF_STEP_DURATION_MS],
                }
                return self.async_create_entry(
                    title=str(self.discovery_info[CONF_HOSTNAME]).replace('.local', ''),
                    data=data_to_store,
                )

        CONFIRM_SCHEMA: vol.Schema = vol.Schema(
            {
                vol.Optional(
                    CONF_STEP_DURATION_MS, 
                    default=DEFAULT_STEP_DURATION_MS
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_STEP_DURATION_MS, max=MAX_STEP_DURATION_MS)),
            }
        )

        return self.async_show_form(
            step_id="confirm",
            data_schema=CONFIRM_SCHEMA, # Add schema to confirmation step
            description_placeholders={ # These are shown to the user
                CONF_NAME: self.discovery_info.get(CONF_NAME, self.discovery_info.get(CONF_HOSTNAME)),
                CONF_HOSTNAME: self.discovery_info[CONF_HOSTNAME],
                CONF_IP_ADDRESS: self.discovery_info[CONF_IP_ADDRESS],
            },
            errors=errors, # Show errors on the confirm form
        )

# Options Flow Handler
class ZeptrionAirOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Zeptrion Air options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None: # Using ConfigEntry
        """Initialize options flow."""
        self.config_entry: config_entries.ConfigEntry = config_entry
        self.options: dict[str, Any] = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult: 
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        current_duration: int = self.config_entry.options.get(
            CONF_STEP_DURATION_MS,
            self.config_entry.data.get(CONF_STEP_DURATION_MS, DEFAULT_STEP_DURATION_MS)
        )

        options_schema: vol.Schema = vol.Schema(
            {
                vol.Optional(
                    CONF_STEP_DURATION_MS,
                    default=current_duration,
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_STEP_DURATION_MS, max=MAX_STEP_DURATION_MS)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )
