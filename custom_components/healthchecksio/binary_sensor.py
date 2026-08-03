"""Binary sensor platform for HealthChecks.io integration."""

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_STATUS
from .coordinator import HealthchecksioDataUpdateCoordinator
from .entity import HealthchecksioEntity

PLATFORM = Platform.BINARY_SENSOR


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup Binary Sensor platform."""
    coordinator: HealthchecksioDataUpdateCoordinator = config_entry.runtime_data
    entities: list[HealthchecksioBinarySensor] = [
        HealthchecksioBinarySensor(
            hass=hass,
            ping_uuid=uuid,
            name=check.get(ATTR_NAME),
            coordinator=coordinator,
        )
        for uuid, check in coordinator.data.items()
    ]
    async_add_entities(entities)


class HealthchecksioBinarySensor(HealthchecksioEntity, BinarySensorEntity):
    """HealthChecks.io binary sensor class."""

    def __init__(
        self,
        hass: HomeAssistant,
        ping_uuid: str,
        name: str,
        coordinator: HealthchecksioDataUpdateCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(hass, ping_uuid, name, coordinator, PLATFORM)
        self._attr_device_class: BinarySensorDeviceClass = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_is_on: bool | None = None

    def _update_status(self, status: Any) -> None:
        """Set binary sensor state and attributes for a Healthchecks.io status."""
        if status == "paused":
            self._attr_is_on = None
        else:
            self._attr_is_on = status != "down"
        self._attr_extra_state_attributes[ATTR_STATUS] = status
