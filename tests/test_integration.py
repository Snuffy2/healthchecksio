"""Config-entry lifecycle tests against a real Home Assistant test instance."""

from typing import Any

from homeassistant.const import ATTR_ATTRIBUTION, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    MockConfigEntry,
)

from custom_components.healthchecksio.const import (
    ATTR_LAST_PING,
    ATTR_STATUS,
    ATTRIBUTION,
    CONF_CREATE_BINARY_SENSOR,
    CONF_CREATE_SENSOR,
    DOMAIN,
)

from .conftest import API_KEY, CHECK_UUID, CHECKS_RESPONSE, CHECKS_URL, PING_URL


async def test_entry_setup_creates_entities_and_unload_marks_them_unavailable(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
) -> None:
    """Exercise the complete setup and unload lifecycle through Home Assistant."""
    aioclient_mock.get(PING_URL, status=200)
    aioclient_mock.get(CHECKS_URL, json=CHECKS_RESPONSE)
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=API_KEY, version=2)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.healthchecksio_database_backup")
    binary_sensor = hass.states.get("binary_sensor.healthchecksio_database_backup")
    assert sensor is not None
    assert sensor.state == "Up"
    assert sensor.attributes[ATTR_ATTRIBUTION] == ATTRIBUTION
    assert sensor.attributes[ATTR_LAST_PING] == "2026-08-02T12:34:56+00:00"
    assert binary_sensor is not None
    assert binary_sensor.state == "on"
    assert binary_sensor.attributes[ATTR_STATUS] == "up"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    unloaded_sensor = hass.states.get("sensor.healthchecksio_database_backup")
    unloaded_binary_sensor = hass.states.get("binary_sensor.healthchecksio_database_backup")
    assert unloaded_sensor is not None
    assert unloaded_sensor.state == STATE_UNAVAILABLE
    assert unloaded_binary_sensor is not None
    assert unloaded_binary_sensor.state == STATE_UNAVAILABLE


async def test_multiple_entries_create_separate_entities(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
) -> None:
    """Keep entities separate when different entries expose the same check UUID."""
    first_entry_data = dict(entry_data)
    first_entry_data.pop("ping_uuid")
    second_entry_data = {
        **first_entry_data,
        "api_key": "second-api-key",
        "site_root": "https://second.healthchecks.example.test",
    }
    aioclient_mock.get(CHECKS_URL, json=CHECKS_RESPONSE)
    aioclient_mock.get(
        "https://second.healthchecks.example.test/api/v1/checks/",
        json=CHECKS_RESPONSE,
    )

    first_entry = MockConfigEntry(
        domain=DOMAIN,
        data=first_entry_data,
        unique_id=API_KEY,
        version=3,
    )
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        data=second_entry_data,
        unique_id="second-api-key",
        version=3,
    )
    first_entry.add_to_hass(hass)
    second_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(first_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    first_entity_id = registry.async_get_entity_id(
        Platform.SENSOR,
        DOMAIN,
        f"{first_entry.entry_id}_sensor_{CHECK_UUID}",
    )
    second_entity_id = registry.async_get_entity_id(
        Platform.SENSOR,
        DOMAIN,
        f"{second_entry.entry_id}_sensor_{CHECK_UUID}",
    )
    assert first_entity_id is not None
    assert second_entity_id is not None
    assert first_entity_id != second_entity_id
    assert hass.states.get(first_entity_id) is not None
    assert hass.states.get(second_entity_id) is not None


async def test_entry_setup_uses_entity_type_options(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
) -> None:
    """Use entity-type options in preference to the initial configuration values."""
    aioclient_mock.get(PING_URL, status=200)
    aioclient_mock.get(CHECKS_URL, json=CHECKS_RESPONSE)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            key: value
            for key, value in entry_data.items()
            if key not in (CONF_CREATE_BINARY_SENSOR, CONF_CREATE_SENSOR)
        },
        options={
            CONF_CREATE_BINARY_SENSOR: False,
            CONF_CREATE_SENSOR: True,
        },
        unique_id=API_KEY,
        version=3,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.healthchecksio_database_backup") is not None
    assert hass.states.get("binary_sensor.healthchecksio_database_backup") is None


async def test_reloading_removes_deselected_platform_entities(
    hass: HomeAssistant,
    aioclient_mock: Any,
    entry_data: dict[str, str | bool],
) -> None:
    """Delete the registry entry and state for a platform removed from options."""
    aioclient_mock.get(PING_URL, status=200)
    aioclient_mock.get(CHECKS_URL, json=CHECKS_RESPONSE)
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, unique_id=API_KEY, version=3)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    binary_sensor_unique_id = f"{entry.entry_id}_{Platform.BINARY_SENSOR}_{CHECK_UUID}"
    binary_sensor_entity_id = registry.async_get_entity_id(
        Platform.BINARY_SENSOR,
        DOMAIN,
        binary_sensor_unique_id,
    )
    assert binary_sensor_entity_id is not None
    unrelated_entity = registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        "unrelated",
        config_entry=entry,
    )

    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_CREATE_BINARY_SENSOR: False,
            CONF_CREATE_SENSOR: True,
        },
    )

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(binary_sensor_entity_id) is None
    assert hass.states.get(binary_sensor_entity_id) is None
    assert registry.async_get(unrelated_entity.entity_id) is not None
