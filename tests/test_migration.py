"""Tests for legacy config-entry and entity migration."""

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    MockConfigEntry,
)

from custom_components.healthchecksio import async_migrate_entry
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
)


async def test_future_version_rejected_and_v2_accepted(hass: HomeAssistant) -> None:
    """Reject unknown future schemas while accepting the current schema."""
    future_entry = MockConfigEntry(domain=DOMAIN, data={}, version=4)
    current_entry = MockConfigEntry(domain=DOMAIN, data={}, version=3)
    assert not await async_migrate_entry(hass, future_entry)
    assert await async_migrate_entry(hass, current_entry)


async def test_v2_entity_type_settings_migrate_to_options(hass: HomeAssistant) -> None:
    """Move entity-type settings to options without retaining duplicate data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "key",
            CONF_CREATE_BINARY_SENSOR: False,
            CONF_CREATE_SENSOR: True,
        },
        version=2,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 3
    assert entry.data == {CONF_API_KEY: "key"}
    assert entry.options == {
        CONF_CREATE_BINARY_SENSOR: False,
        CONF_CREATE_SENSOR: True,
    }


async def test_v2_entity_type_settings_migration_failure_is_reported(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep a v2 entry unchanged when its options cannot be persisted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CREATE_BINARY_SENSOR: True,
            CONF_CREATE_SENSOR: False,
        },
        version=2,
    )
    entry.add_to_hass(hass)
    monkeypatch.setattr(
        hass.config_entries,
        "async_update_entry",
        lambda *args, **kwargs: False,
    )

    assert not await async_migrate_entry(hass, entry)
    assert entry.version == 2
    assert entry.data == {
        CONF_CREATE_BINARY_SENSOR: True,
        CONF_CREATE_SENSOR: False,
    }
    assert entry.options == {}


@pytest.mark.parametrize(
    ("self_hosted", "site_root", "ping_endpoint", "expected_site", "expected_ping"),
    [
        (False, "old", "old-ping", DEFAULT_SITE_ROOT, DEFAULT_PING_ENDPOINT),
        (True, "https://hc.test/", "/ping/", "https://hc.test/", "https://hc.test/ping"),
    ],
)
async def test_v1_data_and_relevant_entities_migrate(
    hass: HomeAssistant,
    self_hosted: bool,
    site_root: str,
    ping_endpoint: str,
    expected_site: str,
    expected_ping: str,
) -> None:
    """Convert v1 data and update only unprefixed binary-sensor identities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "key",
            "check": "ping",
            CONF_SELF_HOSTED: self_hosted,
            CONF_SITE_ROOT: site_root,
            CONF_PING_ENDPOINT: ping_endpoint,
        },
        version=1,
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    target = registry.async_get_or_create("binary_sensor", DOMAIN, "legacy", config_entry=entry)
    prefixed = registry.async_get_or_create(
        "binary_sensor", DOMAIN, "binary_sensor_existing", config_entry=entry
    )
    sensor = registry.async_get_or_create("sensor", DOMAIN, "sensor-old", config_entry=entry)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 3
    assert entry.unique_id == "key"
    assert entry.data[CONF_PING_UUID] == "ping"
    assert CONF_CREATE_BINARY_SENSOR not in entry.data
    assert CONF_CREATE_SENSOR not in entry.data
    assert entry.options[CONF_CREATE_BINARY_SENSOR] is True
    assert entry.options[CONF_CREATE_SENSOR] is False
    assert entry.data[CONF_SITE_ROOT] == expected_site
    assert entry.data[CONF_PING_ENDPOINT] == expected_ping
    migrated_target = registry.async_get(target.entity_id)
    migrated_prefixed = registry.async_get(prefixed.entity_id)
    migrated_sensor = registry.async_get(sensor.entity_id)
    assert migrated_target is not None
    assert migrated_prefixed is not None
    assert migrated_sensor is not None
    assert migrated_target.unique_id == f"{entry.entry_id}_binary_sensor_legacy"
    assert migrated_prefixed.unique_id == f"{entry.entry_id}_binary_sensor_existing"
    assert migrated_sensor.unique_id == "sensor-old"


async def test_v2_entities_migrate_to_entry_scoped_unique_ids(hass: HomeAssistant) -> None:
    """Preserve entity IDs while scoping v2 unique IDs to their entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, version=2)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old_entity = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "sensor_check-uuid",
        config_entry=entry,
    )

    assert await async_migrate_entry(hass, entry)
    migrated_entity = registry.async_get(old_entity.entity_id)
    assert entry.version == 3
    assert migrated_entity is not None
    assert migrated_entity.unique_id == f"{entry.entry_id}_sensor_check-uuid"


async def test_v2_migration_skips_unrelated_platform(hass: HomeAssistant) -> None:
    """Leave entities from unsupported platforms unchanged during migration."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, version=2)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    unrelated_entity = registry.async_get_or_create(
        "switch",
        DOMAIN,
        "switch_check-uuid",
        config_entry=entry,
    )

    assert await async_migrate_entry(hass, entry)
    migrated_entity = registry.async_get(unrelated_entity.entity_id)
    assert entry.version == 3
    assert migrated_entity is not None
    assert migrated_entity.unique_id == "switch_check-uuid"


async def test_v2_entity_update_failure_stops_migration(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep a v2 entry unchanged if its entity identity cannot be migrated."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, version=2)
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "sensor_check-uuid",
        config_entry=entry,
    )
    monkeypatch.setattr(
        registry,
        "async_update_entity",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("conflict")),
    )

    assert not await async_migrate_entry(hass, entry)
    assert entry.version == 2


async def test_entity_update_error_is_tolerated(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finish config migration if an entity identity conflicts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", "check": None, CONF_SELF_HOSTED: False},
        version=1,
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create("binary_sensor", DOMAIN, "legacy", config_entry=entry)
    monkeypatch.setattr(
        registry,
        "async_update_entity",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("conflict")),
    )
    assert await async_migrate_entry(hass, entry)


async def test_config_entry_update_failure_stops_migration(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Report failure when Home Assistant cannot persist the migrated entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_SELF_HOSTED: False},
        version=1,
    )
    monkeypatch.setattr(
        hass.config_entries,
        "async_update_entry",
        lambda *args, **kwargs: False,
    )
    assert not await async_migrate_entry(hass, entry)
