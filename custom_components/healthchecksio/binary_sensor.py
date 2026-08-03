"""Binary sensor platform for HealthChecks.io integration."""

from collections.abc import MutableMapping
import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_LAST_PING,
    ATTR_STATUS,
    ATTRIBUTION,
    ICON_DEFAULT,
    ICON_DOWN,
    ICON_GRACE,
    ICON_PAUSED,
    ICON_UP,
)
from .coordinator import HealthchecksioDataUpdateCoordinator
from .entity import HealthchecksioEntity

_LOGGER = logging.getLogger(__name__)

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
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._attr_is_on: bool | None = None
        self._attr_icon: str = ICON_DEFAULT

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the binary sensor."""
        _LOGGER.debug("Updating: %s", self._attr_name)
        checks: MutableMapping[str, Any] = self.coordinator.data
        # _LOGGER.debug("checks: %s", checks)
        check: MutableMapping[str, Any] | None = checks.get(self._ping_uuid)
        # _LOGGER.debug("check: %s", check)
        if not check:
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_available = True
        self._attr_name = check.get(ATTR_NAME) or self._attr_name
        if check.get(ATTR_STATUS) == "paused":
            self._attr_is_on = None
        else:
            self._attr_is_on = check.get(ATTR_STATUS) != "down"
        self._attr_extra_state_attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
        self._attr_extra_state_attributes[ATTR_STATUS] = check.get(ATTR_STATUS)
        self._attr_extra_state_attributes[ATTR_LAST_PING] = check.get(ATTR_LAST_PING)
        value: str | None = check.get(ATTR_STATUS)
        if isinstance(value, str):
            value_lower: str = value.lower()
            icon_map: MutableMapping[str, str] = {
                "new": ICON_DEFAULT,
                "up": ICON_UP,
                "grace": ICON_GRACE,
                "down": ICON_DOWN,
                "paused": ICON_PAUSED,
            }
            self._attr_icon = icon_map.get(value_lower, ICON_DEFAULT)
        else:
            self._attr_icon = ICON_DEFAULT

        self.async_write_ha_state()
