"""End-to-end configuration-flow tests using the Home Assistant flow manager."""

from typing import Any

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.healthchecksio.const import (
    CONF_CREATE_BINARY_SENSOR,
    CONF_CREATE_SENSOR,
    CONF_PING_ENDPOINT,
    CONF_PING_UUID,
    CONF_SELF_HOSTED,
    CONF_SITE_ROOT,
    DEFAULT_PING_ENDPOINT,
    DEFAULT_SITE_ROOT,
    DOMAIN,
    INTEGRATION_NAME,
)

from .conftest import API_KEY, CHECKS_RESPONSE, PING_UUID


async def test_hosted_flow_creates_entry_after_check_and_ping_validation(
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """Create a hosted entry only after both configured Healthchecks endpoints succeed."""
    aioclient_mock.get(f"{DEFAULT_PING_ENDPOINT}/{PING_UUID}", status=200)
    aioclient_mock.get(
        f"{DEFAULT_SITE_ROOT}/api/v1/checks/",
        json=CHECKS_RESPONSE,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            "api_key": API_KEY,
            CONF_CREATE_BINARY_SENSOR: True,
            CONF_CREATE_SENSOR: True,
            CONF_PING_UUID: PING_UUID,
            CONF_SELF_HOSTED: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == INTEGRATION_NAME
    assert result["data"] == {
        "api_key": API_KEY,
        CONF_CREATE_BINARY_SENSOR: True,
        CONF_CREATE_SENSOR: True,
        CONF_PING_UUID: PING_UUID,
        CONF_SELF_HOSTED: False,
        CONF_SITE_ROOT: DEFAULT_SITE_ROOT,
        CONF_PING_ENDPOINT: DEFAULT_PING_ENDPOINT,
    }


async def test_self_hosted_flow_normalizes_urls_before_validating(
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """Collect and normalize self-hosted URLs before creating a validated entry."""
    site_root = "http://healthchecks.example.test/healthchecks//"
    ping_endpoint = "http://healthchecks.example.test//ping///"
    aioclient_mock.get("http://healthchecks.example.test/ping/" + PING_UUID, status=200)
    aioclient_mock.get(
        "http://healthchecks.example.test/healthchecks/api/v1/checks/",
        json=CHECKS_RESPONSE,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            "api_key": API_KEY,
            CONF_CREATE_BINARY_SENSOR: True,
            CONF_CREATE_SENSOR: False,
            CONF_PING_UUID: PING_UUID,
            CONF_SELF_HOSTED: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "self_hosted"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SITE_ROOT: site_root, CONF_PING_ENDPOINT: ping_endpoint},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SITE_ROOT] == "http://healthchecks.example.test/healthchecks"
    assert result["data"][CONF_PING_ENDPOINT] == "http://healthchecks.example.test/ping"


async def test_flow_requires_at_least_one_entity_type(hass: HomeAssistant) -> None:
    """Keep invalid entity selections inside the user flow instead of creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            "api_key": API_KEY,
            CONF_CREATE_BINARY_SENSOR: False,
            CONF_CREATE_SENSOR: False,
            CONF_SELF_HOSTED: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "need_a_sensor"}
