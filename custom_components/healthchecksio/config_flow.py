"""Config flow for HealthChecks.io integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, MutableMapping
import logging
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .const import (
    CONF_CREATE_BINARY_SENSOR,
    CONF_CREATE_SENSOR,
    CONF_PING_ENDPOINT,
    CONF_PING_UUID,
    CONF_SELF_HOSTED,
    CONF_SITE_ROOT,
    DEFAULT_CREATE_BINARY_SENSOR,
    DEFAULT_CREATE_SENSOR,
    DEFAULT_PING_ENDPOINT,
    DEFAULT_SELF_HOSTED,
    DEFAULT_SITE_ROOT,
    DOMAIN,
    INTEGRATION_NAME,
)
from .helpers import clean_url

_LOGGER: logging.Logger = logging.getLogger(__name__)


async def _test_credentials(
    hass: HomeAssistant,
    api_key: str,
    site_root: str,
    ping_endpoint: str,
    ping_uuid: str | None = None,
) -> bool:
    """Return true if credentials are valid."""
    _LOGGER.debug("Testing Credentials")
    check_verify_ssl: bool = site_root.startswith("https")
    check_session: ClientSession = async_get_clientsession(hass, check_verify_ssl)
    timeout10: ClientTimeout = ClientTimeout(total=10)
    headers: MutableMapping[str, Any] = {"X-Api-Key": api_key}
    if ping_uuid:
        ping_verify_ssl: bool = ping_endpoint.startswith("https")
        ping_session: ClientSession = async_get_clientsession(hass, ping_verify_ssl)
        ping_url: str = f"{ping_endpoint}/{ping_uuid}"
        _LOGGER.debug("ping_url: %s", ping_url)
        await asyncio.sleep(1)  # needed for self-hosted instances

        try:
            ping_response = await ping_session.get(ping_url, timeout=timeout10)
        except ClientError as e:
            _LOGGER.error(
                "Could Not Send Ping using URL: %s. %s: %s",
                ping_url,
                e.__class__.__qualname__,
                e,
            )
            return False
        else:
            if ping_response.ok:
                _LOGGER.debug("Send Ping HTTP Status Code: %s", ping_response.status)
            else:
                _LOGGER.error("Error: Send Ping HTTP Status Code: %s", ping_response.status)
                return False
    else:
        _LOGGER.debug("Send Ping is not defined")

    try:
        data = await check_session.get(
            f"{site_root}/api/v1/checks/", headers=headers, timeout=timeout10
        )
    except (TimeoutError, ClientError) as e:
        _LOGGER.error(
            "Could Not Update Data. %s: %s",
            e.__class__.__qualname__,
            e,
        )
        return False
    else:
        if not data.ok:
            _LOGGER.error("Error: Get Data HTTP Status Code: %s", data.status)
            return False
        _LOGGER.debug("Get Data HTTP Status Code: %s", data.status)
        return True


def _build_user_input_schema(
    user_input: MutableMapping[str, Any] | None,
    fallback: Mapping[str, Any] | None = None,
    reconf: bool = False,
) -> vol.Schema:
    """Build the user-input schema.

    Args:
        user_input: Submitted values, which take precedence when selecting defaults.
        fallback: Existing values used as defaults when no submitted value exists.
        reconf: Whether to omit ``CONF_NAME`` for a reconfigure flow.
    """
    if user_input is None:
        user_input = {}
    if fallback is None:
        fallback = {}
    schema_data: dict[vol.Marker, object] = {
        vol.Required(
            CONF_API_KEY,
            default=user_input.get(CONF_API_KEY, fallback.get(CONF_API_KEY, "")),
        ): str,
    }
    if not reconf:
        schema_data.update(
            {
                vol.Optional(
                    CONF_NAME,
                    default=user_input.get(
                        CONF_NAME,
                        fallback.get(CONF_NAME, INTEGRATION_NAME),
                    ),
                ): str,
            }
        )
    schema: vol.Schema = vol.Schema(schema_data)
    return schema.extend(
        {
            vol.Optional(
                CONF_PING_UUID,
                default=user_input.get(CONF_PING_UUID, fallback.get(CONF_PING_UUID, "")),
            ): str,
            vol.Optional(
                CONF_CREATE_BINARY_SENSOR,
                default=user_input.get(
                    CONF_CREATE_BINARY_SENSOR,
                    fallback.get(CONF_CREATE_BINARY_SENSOR, DEFAULT_CREATE_BINARY_SENSOR),
                ),
            ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
            vol.Optional(
                CONF_CREATE_SENSOR,
                default=user_input.get(
                    CONF_CREATE_SENSOR, fallback.get(CONF_CREATE_SENSOR, DEFAULT_CREATE_SENSOR)
                ),
            ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
            vol.Optional(
                CONF_SELF_HOSTED,
                default=user_input.get(
                    CONF_SELF_HOSTED, fallback.get(CONF_SELF_HOSTED, DEFAULT_SELF_HOSTED)
                ),
            ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
        }
    )


def _build_self_hosted_schema(
    user_input: MutableMapping[str, Any] | None,
    fallback: Mapping[str, Any] | None = None,
) -> vol.Schema:
    if user_input is None:
        user_input = {}
    if fallback is None:
        fallback = {}

    return vol.Schema(
        {
            vol.Required(
                CONF_SITE_ROOT,
                default=user_input.get(
                    CONF_SITE_ROOT, fallback.get(CONF_SITE_ROOT, DEFAULT_SITE_ROOT)
                ),
            ): str,
            vol.Optional(
                CONF_PING_ENDPOINT,
                default=user_input.get(CONF_PING_ENDPOINT, fallback.get(CONF_PING_ENDPOINT, "")),
            ): str,
        }
    )


def _build_options_schema(config_entry: ConfigEntry) -> vol.Schema:
    """Build the schema for selecting which entity types to create."""
    return vol.Schema(
        {
            vol.Required(
                CONF_CREATE_BINARY_SENSOR,
                default=config_entry.options.get(
                    CONF_CREATE_BINARY_SENSOR,
                    config_entry.data.get(CONF_CREATE_BINARY_SENSOR, DEFAULT_CREATE_BINARY_SENSOR),
                ),
            ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
            vol.Required(
                CONF_CREATE_SENSOR,
                default=config_entry.options.get(
                    CONF_CREATE_SENSOR,
                    config_entry.data.get(CONF_CREATE_SENSOR, DEFAULT_CREATE_SENSOR),
                ),
            ): selector.BooleanSelector(selector.BooleanSelectorConfig()),
        }
    )


def _get_entry_title(data: Mapping[str, Any]) -> str:
    """Return the configured entry title or the integration name."""
    name = data.get(CONF_NAME)
    return name.strip() if isinstance(name, str) and name.strip() else INTEGRATION_NAME


def _pop_entity_type_options(data: MutableMapping[str, Any]) -> dict[str, bool]:
    """Remove entity-type choices from entry data and return them as options."""
    return {
        CONF_CREATE_BINARY_SENSOR: data.pop(
            CONF_CREATE_BINARY_SENSOR, DEFAULT_CREATE_BINARY_SENSOR
        ),
        CONF_CREATE_SENSOR: data.pop(CONF_CREATE_SENSOR, DEFAULT_CREATE_SENSOR),
    }


class HealthchecksioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for HealthChecks.io integration."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}
        self._initial_data: MutableMapping[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow for this integration."""
        return HealthchecksioOptionsFlow()

    def _finish_configuration(self, data: MutableMapping[str, Any]) -> ConfigFlowResult:
        """Create a new entry or update the reconfigured one."""
        options = _pop_entity_type_options(data)
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            entry_data = dict(entry.data)
            entry_data.update(data)
            _pop_entity_type_options(entry_data)
            return self.async_update_reload_and_abort(
                entry,
                unique_id=data[CONF_API_KEY],
                data=entry_data,
                options=options,
            )
        return self.async_create_entry(
            title=_get_entry_title(data),
            data=data,
            options=options,
        )

    async def _async_validate_input(
        self, user_input: MutableMapping[str, Any]
    ) -> ConfigFlowResult | None:
        """Validate shared user and reconfigure input."""
        if not user_input.get(CONF_CREATE_BINARY_SENSOR) and not user_input.get(CONF_CREATE_SENSOR):
            self._errors["base"] = "need_a_sensor"
            return None
        if user_input.get(CONF_SELF_HOSTED):
            self._initial_data = user_input
            return await self.async_step_self_hosted()

        user_input[CONF_SITE_ROOT] = DEFAULT_SITE_ROOT
        user_input[CONF_PING_ENDPOINT] = DEFAULT_PING_ENDPOINT
        user_input[CONF_SELF_HOSTED] = False
        valid: bool = await _test_credentials(
            hass=self.hass,
            api_key=user_input[CONF_API_KEY],
            site_root=user_input[CONF_SITE_ROOT],
            ping_endpoint=user_input[CONF_PING_ENDPOINT],
            ping_uuid=user_input.get(CONF_PING_UUID),
        )
        if valid:
            return self._finish_configuration(user_input)
        self._errors["base"] = "auth"
        return None

    async def async_step_user(
        self,
        user_input: MutableMapping[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """User Input step."""
        self._errors = errors or {}
        if user_input is not None:
            # https://developers.home-assistant.io/docs/config_entries_config_flow_handler#unique-ids
            await self.async_set_unique_id(user_input.get(CONF_API_KEY))
            self._abort_if_unique_id_configured()

            result = await self._async_validate_input(user_input)
            if result is not None:
                return result

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_input_schema(user_input=user_input),
            errors=self._errors,
        )

    async def async_step_reconfigure(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure an existing entry."""
        config_entry = self._get_reconfigure_entry()
        self._errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_API_KEY])
            existing_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, user_input[CONF_API_KEY]
            )
            if existing_entry is not None and existing_entry.entry_id != config_entry.entry_id:
                return self.async_abort(reason="already_configured")
            result = await self._async_validate_input(user_input)
            if result is not None:
                return result

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_user_input_schema(
                user_input=user_input,
                fallback={**config_entry.data, **config_entry.options},
                reconf=True,
            ),
            errors=self._errors,
        )

    async def async_step_self_hosted(
        self, user_input: MutableMapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step for a self-hosted instance."""
        self._errors = {}
        if user_input is not None:
            user_input[CONF_SITE_ROOT] = clean_url(user_input[CONF_SITE_ROOT])
            if user_input.get(CONF_PING_ENDPOINT) is None:
                user_input[CONF_PING_ENDPOINT] = f"{user_input.get(CONF_SITE_ROOT)}/ping"
            user_input[CONF_PING_ENDPOINT] = clean_url(user_input[CONF_PING_ENDPOINT])
            api_key: str = self._initial_data[CONF_API_KEY]
            ping_uuid: str | None = self._initial_data.get(CONF_PING_UUID)
            valid: bool = await _test_credentials(
                hass=self.hass,
                api_key=api_key,
                site_root=user_input[CONF_SITE_ROOT],
                ping_endpoint=user_input[CONF_PING_ENDPOINT],
                ping_uuid=ping_uuid,
            )
            if valid:
                # merge data from initial config flow and this flow
                data: MutableMapping[str, Any] = {**self._initial_data, **user_input}
                return self._finish_configuration(data)
            self._errors["base"] = "auth_self"

        return self.async_show_form(
            step_id="self_hosted",
            data_schema=_build_self_hosted_schema(
                user_input=user_input,
                fallback=(
                    self._get_reconfigure_entry().data
                    if self.source == SOURCE_RECONFIGURE
                    else None
                ),
            ),
            errors=self._errors,
        )


class HealthchecksioOptionsFlow(OptionsFlowWithReload):
    """Manage HealthChecks.io integration options."""

    async def async_step_init(
        self, user_input: MutableMapping[str, bool] | None = None
    ) -> ConfigFlowResult:
        """Manage the enabled HealthChecks.io entity types."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_CREATE_BINARY_SENSOR] and not user_input[CONF_CREATE_SENSOR]:
                errors["base"] = "need_a_sensor"
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(self.config_entry),
            errors=errors,
        )
