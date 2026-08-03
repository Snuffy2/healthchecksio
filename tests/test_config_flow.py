"""End-to-end configuration-flow tests using the Home Assistant flow manager."""

from typing import Any
from unittest.mock import Mock

from aiohttp import ClientConnectionError
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    MockConfigEntry,
)

from custom_components.healthchecksio.config_flow import (
    HealthchecksioConfigFlow,
    _build_self_hosted_schema,
    _build_user_input_schema,
)
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
from custom_components.healthchecksio.helpers import clean_url

from .conftest import API_KEY, CHECKS_RESPONSE, PING_UUID

UPDATED_API_KEY = "updated-api-key"
UPDATED_PING_UUID = "22222222-2222-2222-2222-222222222222"


def _hosted_input(*, ping_uuid: str | None = PING_UUID) -> dict[str, Any]:
    """Return valid hosted-service user input."""
    data = {
        "api_key": API_KEY,
        CONF_CREATE_BINARY_SENSOR: True,
        CONF_CREATE_SENSOR: False,
        CONF_SELF_HOSTED: False,
    }
    if ping_uuid is not None:
        data[CONF_PING_UUID] = ping_uuid
    return data


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
        CONF_PING_UUID: PING_UUID,
        CONF_SELF_HOSTED: False,
        CONF_SITE_ROOT: DEFAULT_SITE_ROOT,
        CONF_PING_ENDPOINT: DEFAULT_PING_ENDPOINT,
    }
    assert result["options"] == {
        CONF_CREATE_BINARY_SENSOR: True,
        CONF_CREATE_SENSOR: True,
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
            CONF_NAME: "Self-hosted",
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
    assert result["title"] == "Self-hosted"
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


@pytest.mark.parametrize(
    ("ping_status", "ping_exception"),
    [(503, None), (None, ClientConnectionError("ping unavailable"))],
)
async def test_hosted_flow_rejects_failed_ping(
    hass: HomeAssistant,
    aioclient_mock: Any,
    monkeypatch: pytest.MonkeyPatch,
    ping_status: int | None,
    ping_exception: ClientConnectionError | None,
) -> None:
    """Reject credentials when the optional ping cannot be delivered."""
    monkeypatch.setattr(
        "custom_components.healthchecksio.config_flow.asyncio.sleep", lambda _: _noop()
    )
    aioclient_mock.get(
        f"{DEFAULT_PING_ENDPOINT}/{PING_UUID}",
        status=ping_status or 200,
        exc=ping_exception,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=_hosted_input()
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth"}


async def _noop() -> None:
    """Provide an awaitable no-op for the self-hosted ping delay."""


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (503, None),
        (None, TimeoutError("checks timed out")),
        (None, ClientConnectionError("checks unavailable")),
    ],
)
async def test_hosted_flow_rejects_failed_checks_request(
    hass: HomeAssistant,
    aioclient_mock: Any,
    status: int | None,
    exception: BaseException | None,
) -> None:
    """Reject credentials for each checks-endpoint failure mode."""
    aioclient_mock.get(
        f"{DEFAULT_SITE_ROOT}/api/v1/checks/",
        status=status or 200,
        exc=exception,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=_hosted_input(ping_uuid=None)
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth"}


async def test_user_form_defaults_and_allows_another_api_key(
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """Expose stable defaults and allow a second API key to be configured."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    defaults = result["data_schema"]({})
    assert defaults[CONF_NAME] == INTEGRATION_NAME
    assert defaults[CONF_PING_UUID] == ""
    assert defaults[CONF_CREATE_BINARY_SENSOR] is True
    assert defaults[CONF_CREATE_SENSOR] is False
    assert defaults[CONF_SELF_HOSTED] is False

    MockConfigEntry(domain=DOMAIN, data={"api_key": API_KEY}, unique_id=API_KEY).add_to_hass(hass)
    aioclient_mock.get(f"{DEFAULT_SITE_ROOT}/api/v1/checks/", json=CHECKS_RESPONSE)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            **_hosted_input(ping_uuid=None),
            "api_key": "another-api-key",
            CONF_NAME: "Secondary",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Secondary"
    assert result["data"]["api_key"] == "another-api-key"


async def test_user_flow_rejects_an_already_configured_api_key(hass: HomeAssistant) -> None:
    """Prevent duplicate configuration of the same API key."""
    MockConfigEntry(domain=DOMAIN, data={"api_key": API_KEY}, unique_id=API_KEY).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=_hosted_input(ping_uuid=None),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_updates_enabled_entity_types(
    hass: HomeAssistant,
    entry_data: dict[str, str | bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persist selected entity types as options and reload the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=entry_data,
        options={
            CONF_CREATE_BINARY_SENSOR: False,
            CONF_CREATE_SENSOR: True,
        },
        unique_id=API_KEY,
        version=3,
    )
    entry.add_to_hass(hass)
    mock_schedule_reload = Mock()
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", mock_schedule_reload)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    defaults = result["data_schema"]({})
    assert defaults[CONF_CREATE_BINARY_SENSOR] is False
    assert defaults[CONF_CREATE_SENSOR] is True

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CREATE_BINARY_SENSOR: False,
            CONF_CREATE_SENSOR: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "need_a_sensor"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CREATE_BINARY_SENSOR: True,
            CONF_CREATE_SENSOR: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_CREATE_BINARY_SENSOR: True,
        CONF_CREATE_SENSOR: False,
    }
    assert entry.options == result["data"]
    mock_schedule_reload.assert_called_once_with(entry.entry_id)


async def test_reconfigure_flow_updates_existing_hosted_entry(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Update hosted configuration without changing the existing config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**entry_data, CONF_NAME: "Existing entry"},
        unique_id=API_KEY,
        title="Existing entry",
        version=3,
    )
    entry.add_to_hass(hass)
    mock_schedule_reload = Mock()
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", mock_schedule_reload)
    aioclient_mock.get(f"{DEFAULT_PING_ENDPOINT}/{UPDATED_PING_UUID}", status=200)
    aioclient_mock.get(f"{DEFAULT_SITE_ROOT}/api/v1/checks/", json=CHECKS_RESPONSE)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    defaults = result["data_schema"]({})
    assert CONF_NAME not in defaults
    assert defaults[CONF_API_KEY] == API_KEY
    assert defaults[CONF_CREATE_BINARY_SENSOR] is True
    assert defaults[CONF_CREATE_SENSOR] is True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: UPDATED_API_KEY,
            CONF_PING_UUID: UPDATED_PING_UUID,
            CONF_CREATE_BINARY_SENSOR: False,
            CONF_CREATE_SENSOR: True,
            CONF_SELF_HOSTED: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Existing entry"
    assert entry.unique_id == UPDATED_API_KEY
    assert entry.data == {
        CONF_NAME: "Existing entry",
        CONF_API_KEY: UPDATED_API_KEY,
        CONF_PING_UUID: UPDATED_PING_UUID,
        CONF_SELF_HOSTED: False,
        CONF_SITE_ROOT: DEFAULT_SITE_ROOT,
        CONF_PING_ENDPOINT: DEFAULT_PING_ENDPOINT,
    }
    assert entry.options == {
        CONF_CREATE_BINARY_SENSOR: False,
        CONF_CREATE_SENSOR: True,
    }
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    mock_schedule_reload.assert_called_once_with(entry.entry_id)


async def test_reconfigure_flow_clears_existing_ping_uuid(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skip ping validation when a reconfigure submission clears the Ping UUID."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=API_KEY, version=3)
    entry.add_to_hass(hass)
    mock_schedule_reload = Mock()
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", mock_schedule_reload)
    aioclient_mock.get(f"{DEFAULT_SITE_ROOT}/api/v1/checks/", json=CHECKS_RESPONSE)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: API_KEY,
            CONF_PING_UUID: "",
            CONF_CREATE_BINARY_SENSOR: True,
            CONF_CREATE_SENSOR: True,
            CONF_SELF_HOSTED: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PING_UUID] == ""
    assert entry.options == {
        CONF_CREATE_BINARY_SENSOR: True,
        CONF_CREATE_SENSOR: True,
    }
    mock_schedule_reload.assert_called_once_with(entry.entry_id)


async def test_reconfigure_flow_preserves_entry_after_invalid_submission(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the existing data intact until a valid reconfiguration succeeds."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=API_KEY, version=3)
    entry.add_to_hass(hass)
    mock_schedule_reload = Mock()
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", mock_schedule_reload)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: API_KEY,
            CONF_CREATE_BINARY_SENSOR: False,
            CONF_CREATE_SENSOR: False,
            CONF_SELF_HOSTED: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "need_a_sensor"}

    aioclient_mock.get(f"{DEFAULT_PING_ENDPOINT}/{PING_UUID}", status=200)
    aioclient_mock.get(f"{DEFAULT_SITE_ROOT}/api/v1/checks/", status=401)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: API_KEY,
            CONF_CREATE_BINARY_SENSOR: True,
            CONF_CREATE_SENSOR: False,
            CONF_SELF_HOSTED: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth"}
    assert entry.data == entry_data
    mock_schedule_reload.assert_not_called()


async def test_reconfigure_flow_rejects_an_api_key_used_by_another_entry(
    hass: HomeAssistant,
    entry_data: dict[str, str | bool],
) -> None:
    """Prevent a reconfigured entry from taking another entry's API key."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=API_KEY, version=3)
    entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={**entry_data, CONF_API_KEY: UPDATED_API_KEY},
        unique_id=UPDATED_API_KEY,
        version=3,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: UPDATED_API_KEY,
            CONF_CREATE_BINARY_SENSOR: True,
            CONF_CREATE_SENSOR: False,
            CONF_SELF_HOSTED: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == API_KEY
    assert entry.data == entry_data


async def test_reconfigure_flow_updates_self_hosted_urls(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validate and normalize self-hosted URLs before updating an existing entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=API_KEY, version=3)
    entry.add_to_hass(hass)
    mock_schedule_reload = Mock()
    monkeypatch.setattr(hass.config_entries, "async_schedule_reload", mock_schedule_reload)
    aioclient_mock.get("http://healthchecks.example.test/ping/" + UPDATED_PING_UUID, status=200)
    aioclient_mock.get(
        "http://healthchecks.example.test/healthchecks/api/v1/checks/",
        json=CHECKS_RESPONSE,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: UPDATED_API_KEY,
            CONF_PING_UUID: UPDATED_PING_UUID,
            CONF_CREATE_BINARY_SENSOR: True,
            CONF_CREATE_SENSOR: False,
            CONF_SELF_HOSTED: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "self_hosted"
    defaults = result["data_schema"]({})
    assert defaults[CONF_SITE_ROOT] == entry_data[CONF_SITE_ROOT]
    assert defaults[CONF_PING_ENDPOINT] == entry_data[CONF_PING_ENDPOINT]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SITE_ROOT: "http://healthchecks.example.test/healthchecks//",
            CONF_PING_ENDPOINT: "http://healthchecks.example.test/ping///",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_API_KEY: UPDATED_API_KEY,
        CONF_PING_UUID: UPDATED_PING_UUID,
        CONF_SELF_HOSTED: True,
        CONF_SITE_ROOT: "http://healthchecks.example.test/healthchecks",
        CONF_PING_ENDPOINT: "http://healthchecks.example.test/ping",
    }
    assert entry.options == {
        CONF_CREATE_BINARY_SENSOR: True,
        CONF_CREATE_SENSOR: False,
    }
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    mock_schedule_reload.assert_called_once_with(entry.entry_id)


async def test_self_hosted_defaults_and_invalid_credentials(
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """Preserve self-hosted defaults and report invalid credentials on its form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={**_hosted_input(ping_uuid=None), CONF_SELF_HOSTED: True},
    )
    defaults = result["data_schema"]({})
    assert defaults[CONF_SITE_ROOT] == DEFAULT_SITE_ROOT
    assert defaults[CONF_PING_ENDPOINT] == ""
    aioclient_mock.get("https://healthchecks.example.test/api/v1/checks/", status=401)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SITE_ROOT: "healthchecks.example.test", CONF_PING_ENDPOINT: ""},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_self"}


def test_schema_helpers_apply_fallback_values() -> None:
    """Use existing entry data as defaults when no submitted values exist."""
    fallback = {
        "api_key": API_KEY,
        CONF_NAME: "Existing entry",
        CONF_PING_UUID: PING_UUID,
        CONF_CREATE_BINARY_SENSOR: False,
        CONF_CREATE_SENSOR: True,
        CONF_SELF_HOSTED: True,
        CONF_SITE_ROOT: "https://self.example.test",
        CONF_PING_ENDPOINT: "https://self.example.test/ping",
    }
    assert _build_user_input_schema(None, fallback)({}) == {
        key: fallback[key]
        for key in (
            "api_key",
            CONF_NAME,
            CONF_PING_UUID,
            CONF_CREATE_BINARY_SENSOR,
            CONF_CREATE_SENSOR,
            CONF_SELF_HOSTED,
        )
    }
    assert _build_self_hosted_schema(None, fallback)({}) == {
        CONF_SITE_ROOT: fallback[CONF_SITE_ROOT],
        CONF_PING_ENDPOINT: fallback[CONF_PING_ENDPOINT],
    }
    assert _build_user_input_schema(None, fallback, reconf=True)({}) == {
        key: fallback[key]
        for key in (
            CONF_API_KEY,
            CONF_PING_UUID,
            CONF_CREATE_BINARY_SENSOR,
            CONF_CREATE_SENSOR,
            CONF_SELF_HOSTED,
        )
    }


def test_clean_url_preserves_root_path() -> None:
    """Preserve an explicit root slash while normalizing a URL."""
    assert clean_url("https://healthchecks.example.test/") == ("https://healthchecks.example.test/")


async def test_self_hosted_step_supplies_omitted_ping_endpoint(
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """Derive the conventional ping endpoint when the submitted value is omitted."""
    aioclient_mock.get("https://self.example.test/api/v1/checks/", status=401)
    flow = HealthchecksioConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}
    await flow.async_step_user({**_hosted_input(ping_uuid=None), CONF_SELF_HOSTED: True})

    result = await flow.async_step_self_hosted(
        {CONF_SITE_ROOT: "self.example.test", CONF_PING_ENDPOINT: None}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth_self"}
