"""Unit tests for coordinator failure handling and payload normalization."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

from custom_components.healthchecksio.coordinator import HealthchecksioDataUpdateCoordinator


def _coordinator(
    hass: HomeAssistant, *, ping_uuid: str | None = None
) -> tuple[
    HealthchecksioDataUpdateCoordinator,
    AsyncMock,
    AsyncMock,
]:
    ping = AsyncMock()
    checks = AsyncMock()
    coordinator = HealthchecksioDataUpdateCoordinator(
        hass, "key", ping, checks, "https://example.test", "https://ping.test", ping_uuid
    )
    return coordinator, ping, checks


async def test_update_skips_ping_and_filters_checks_without_uuid(hass: HomeAssistant) -> None:
    """Return only checks having a usable UUID when pinging is disabled."""
    coordinator, ping, checks = _coordinator(hass)
    response = AsyncMock()
    response.json.return_value = {"checks": [{"name": "missing"}, {"uuid": "ok"}]}
    checks.get.return_value = response

    assert await coordinator._async_update_data() == {  # noqa: SLF001
        "ok": {"uuid": "ok"}
    }
    ping.get.assert_not_awaited()


@pytest.mark.parametrize("error", [TimeoutError(), ClientError()])
async def test_ping_failure_does_not_prevent_checks_update(
    hass: HomeAssistant, error: Exception
) -> None:
    """Continue refreshing checks when the optional ping fails."""
    coordinator, ping, checks = _coordinator(hass, ping_uuid="ping")
    ping.get.side_effect = error
    response = AsyncMock()
    response.json.return_value = {"checks": []}
    checks.get.return_value = response

    assert await coordinator._async_update_data() == {}  # noqa: SLF001


@pytest.mark.parametrize("error", [TimeoutError(), ClientError()])
async def test_checks_transport_failure_raises_update_failed(
    hass: HomeAssistant, error: Exception
) -> None:
    """Translate checks transport failures into coordinator failures."""
    coordinator, _, checks = _coordinator(hass)
    checks.get.side_effect = error

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()  # noqa: SLF001


@pytest.mark.parametrize("result", [ValueError("bad json"), [], None])
async def test_invalid_checks_response_raises_update_failed(
    hass: HomeAssistant, result: object
) -> None:
    """Reject invalid JSON and non-mapping JSON payloads."""
    coordinator, _, checks = _coordinator(hass)
    response = AsyncMock()
    if isinstance(result, Exception):
        response.json.side_effect = result
    else:
        response.json.return_value = result
    checks.get.return_value = response

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()  # noqa: SLF001
