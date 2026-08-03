"""End-to-end platform and entity behavior tests."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock

from homeassistant.const import ATTR_ATTRIBUTION, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    MockConfigEntry,
)

from custom_components.healthchecksio import async_unload_entry
from custom_components.healthchecksio.binary_sensor import HealthchecksioBinarySensor
from custom_components.healthchecksio.const import (
    ATTR_LAST_PING,
    ATTR_STATUS,
    ATTRIBUTION,
    CONF_CREATE_BINARY_SENSOR,
    CONF_CREATE_SENSOR,
    DOMAIN,
    ICON_DEFAULT,
    ICON_DOWN,
    ICON_PAUSED,
)
from custom_components.healthchecksio.entity import HealthchecksioEntity
from custom_components.healthchecksio.sensor import HealthchecksioSensor

from .conftest import API_KEY, CHECK_UUID, CHECKS_RESPONSE, CHECKS_URL, PING_URL


def test_platform_entities_inherit_the_shared_entity_base() -> None:
    """Use the common Healthchecks.io entity implementation on every platform."""
    assert issubclass(HealthchecksioBinarySensor, HealthchecksioEntity)
    assert issubclass(HealthchecksioSensor, HealthchecksioEntity)


async def test_unload_returns_false_when_platform_unload_fails(
    hass: HomeAssistant,
    entry_data: dict[str, str | bool],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Propagate a platform unload failure to Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=API_KEY, version=2)
    unload_platforms = AsyncMock(return_value=False)
    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", unload_platforms)

    assert await async_unload_entry(hass, entry) is False
    unload_platforms.assert_awaited_once_with(
        entry,
        [Platform.BINARY_SENSOR, Platform.SENSOR],
    )


async def _setup_entry(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
    response: dict[str, Any] = CHECKS_RESPONSE,
) -> MockConfigEntry:
    """Set up a real config entry using mocked Healthchecks.io transport."""
    aioclient_mock.get(PING_URL, status=200)
    aioclient_mock.get(CHECKS_URL, json=response)
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=API_KEY, version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.parametrize(
    ("enabled_key", "entity_id", "disabled_entity_id"),
    [
        (
            CONF_CREATE_SENSOR,
            "sensor.healthchecksio_database_backup",
            "binary_sensor.healthchecksio_database_backup",
        ),
        (
            CONF_CREATE_BINARY_SENSOR,
            "binary_sensor.healthchecksio_database_backup",
            "sensor.healthchecksio_database_backup",
        ),
    ],
)
async def test_setup_and_unload_each_platform_alone(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
    enabled_key: str,
    entity_id: str,
    disabled_entity_id: str,
) -> None:
    """Forward and unload exactly the platform selected by the entry."""
    entry_data[CONF_CREATE_SENSOR] = enabled_key == CONF_CREATE_SENSOR
    entry_data[CONF_CREATE_BINARY_SENSOR] = enabled_key == CONF_CREATE_BINARY_SENSOR
    entry = await _setup_entry(hass, aioclient_mock, entry_data)

    assert hass.states.get(entity_id) is not None
    assert hass.states.get(disabled_entity_id) is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("platform", "enabled_key"),
    [
        (Platform.SENSOR, CONF_CREATE_SENSOR),
        (Platform.BINARY_SENSOR, CONF_CREATE_BINARY_SENSOR),
    ],
)
async def test_platform_reuses_registered_entity_id(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
    platform: Platform,
    enabled_key: str,
) -> None:
    """Preserve an existing entity registry ID across entry setup."""
    entry_data[CONF_CREATE_SENSOR] = enabled_key == CONF_CREATE_SENSOR
    entry_data[CONF_CREATE_BINARY_SENSOR] = enabled_key == CONF_CREATE_BINARY_SENSOR
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=API_KEY, version=2)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    unique_id = f"{entry.entry_id}_{platform}_{CHECK_UUID}"
    registry.async_get_or_create(
        platform,
        DOMAIN,
        unique_id,
        config_entry=entry,
        suggested_object_id="preserved_check_name",
    )
    aioclient_mock.get(PING_URL, status=200)
    aioclient_mock.get(CHECKS_URL, json=CHECKS_RESPONSE)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(f"{platform}.preserved_check_name") is not None


async def test_missing_check_makes_entities_unavailable(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
) -> None:
    """Mark both entities unavailable when their coordinator check disappears."""
    entry = await _setup_entry(hass, aioclient_mock, entry_data)

    entry.runtime_data.data = {}
    entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.healthchecksio_database_backup").state == STATE_UNAVAILABLE
    assert (
        hass.states.get("binary_sensor.healthchecksio_database_backup").state == STATE_UNAVAILABLE
    )


@pytest.mark.parametrize(
    ("status", "sensor_state", "binary_state", "icon"),
    [
        ("paused", "Paused", "unknown", ICON_PAUSED),
        ("down", "Down", "off", ICON_DOWN),
        (17, "17", "on", ICON_DEFAULT),
    ],
)
async def test_entity_status_contract(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
    status: str | int,
    sensor_state: str,
    binary_state: str,
    icon: str,
) -> None:
    """Expose status semantics, attributes, and icons through Home Assistant state."""
    response: dict[str, Any] = deepcopy(CHECKS_RESPONSE)
    response["checks"][0]["status"] = status
    await _setup_entry(hass, aioclient_mock, entry_data, response)

    sensor = hass.states.get("sensor.healthchecksio_database_backup")
    binary_sensor = hass.states.get("binary_sensor.healthchecksio_database_backup")
    assert sensor.state == sensor_state
    assert sensor.attributes["icon"] == icon
    assert sensor.attributes[ATTR_ATTRIBUTION] == ATTRIBUTION
    assert sensor.attributes[ATTR_LAST_PING] == "2026-08-02T12:34:56+00:00"
    assert binary_sensor.state == binary_state
    assert binary_sensor.attributes["icon"] == icon
    assert binary_sensor.attributes[ATTR_STATUS] == status
    assert binary_sensor.attributes[ATTR_LAST_PING] == "2026-08-02T12:34:56+00:00"
