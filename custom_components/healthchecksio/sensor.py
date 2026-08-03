"""Sensor platform for HealthChecks.io integration."""

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HealthchecksioDataUpdateCoordinator
from .entity import HealthchecksioEntity

PLATFORM = Platform.SENSOR


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup Binary Sensor platform."""
    coordinator: HealthchecksioDataUpdateCoordinator = config_entry.runtime_data
    entities: list[HealthchecksioSensor] = [
        HealthchecksioSensor(
            hass=hass,
            ping_uuid=uuid,
            name=check.get(ATTR_NAME),
            coordinator=coordinator,
        )
        for uuid, check in coordinator.data.items()
    ]
    async_add_entities(entities)


class HealthchecksioSensor(HealthchecksioEntity, SensorEntity):
    """HealthChecks.io Sensor class."""

    def __init__(
        self,
        hass: HomeAssistant,
        ping_uuid: str,
        name: str,
        coordinator: HealthchecksioDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, ping_uuid, name, coordinator, PLATFORM)
        self._attr_native_value: Any | None = None

    def _update_status(self, status: Any) -> None:
        """Set the sensor state for a Healthchecks.io status."""
        self._attr_native_value = status.title() if isinstance(status, str) else status
