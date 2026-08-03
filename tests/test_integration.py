"""Config-entry lifecycle tests against a real Home Assistant test instance."""

from typing import Any

from homeassistant.const import ATTR_ATTRIBUTION, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    MockConfigEntry,
)

from custom_components.healthchecksio.const import ATTR_LAST_PING, ATTR_STATUS, ATTRIBUTION, DOMAIN

from .conftest import API_KEY, CHECKS_RESPONSE, CHECKS_URL, PING_URL


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
