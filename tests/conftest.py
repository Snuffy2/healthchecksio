"""Shared fixtures and realistic Healthchecks.io API payloads for integration tests."""

from http import HTTPStatus
from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (  # type: ignore[import-untyped]
    AiohttpClientMockResponse,
)

import custom_components
from custom_components.healthchecksio.const import (
    CONF_CREATE_BINARY_SENSOR,
    CONF_CREATE_SENSOR,
    CONF_PING_ENDPOINT,
    CONF_PING_UUID,
    CONF_SELF_HOSTED,
    CONF_SITE_ROOT,
)

API_KEY = "test-api-key"
CHECK_UUID = "9d4dd48f-5632-4e53-b5a2-a630f1109a37"
PING_UUID = "a37b5c8c-4c2c-4c43-9d50-e21cf6e77383"
SITE_ROOT = "https://healthchecks.example.test"
PING_ENDPOINT = "https://ping.example.test"
CHECKS_URL = f"{SITE_ROOT}/api/v1/checks/"
PING_URL = f"{PING_ENDPOINT}/{PING_UUID}"

CHECKS_RESPONSE = {
    "checks": [
        {
            "uuid": CHECK_UUID,
            "name": "Database backup",
            "status": "up",
            "last_ping": "2026-08-02T12:34:56+00:00",
        }
    ]
}

CUSTOM_COMPONENTS_PATH = Path(__file__).parents[1] / "custom_components"


def _mock_response_is_ok(response: AiohttpClientMockResponse) -> bool:
    """Mirror ``aiohttp.ClientResponse.ok`` on the custom-component test double."""
    return response.status < HTTPStatus.BAD_REQUEST


@pytest.fixture(autouse=True)
def add_missing_aiohttp_response_ok_property(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give the response mock the standard aiohttp property used by the integration."""
    monkeypatch.setattr(
        AiohttpClientMockResponse,
        "ok",
        property(_mock_response_is_ok),
        raising=False,
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load the checked-out component without an editable-install namespace hook."""
    monkeypatch.setattr(custom_components, "__path__", [str(CUSTOM_COMPONENTS_PATH)])


@pytest.fixture
def entry_data() -> dict[str, str | bool]:
    """Return complete hosted-service configuration entry data."""
    return {
        "api_key": API_KEY,
        CONF_CREATE_BINARY_SENSOR: True,
        CONF_CREATE_SENSOR: True,
        CONF_PING_UUID: PING_UUID,
        CONF_SELF_HOSTED: False,
        CONF_SITE_ROOT: SITE_ROOT,
        CONF_PING_ENDPOINT: PING_ENDPOINT,
    }
