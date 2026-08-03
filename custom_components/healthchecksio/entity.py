"""Base entity for the Healthchecks.io integration."""

from abc import abstractmethod
import logging
from typing import Any

from homeassistant.const import ATTR_ATTRIBUTION, ATTR_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import generate_entity_id
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_LAST_PING,
    ATTR_STATUS,
    ATTRIBUTION,
    DOMAIN,
    ICON_DEFAULT,
    ICON_DOWN,
    ICON_GRACE,
    ICON_PAUSED,
    ICON_UP,
)
from .coordinator import HealthchecksioDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__name__)

_STATUS_ICONS: dict[str, str] = {
    "new": ICON_DEFAULT,
    "up": ICON_UP,
    "grace": ICON_GRACE,
    "down": ICON_DOWN,
    "paused": ICON_PAUSED,
}


class HealthchecksioEntity(CoordinatorEntity):
    """Define common behavior for Healthchecks.io entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        ping_uuid: str,
        name: str,
        coordinator: HealthchecksioDataUpdateCoordinator,
        platform: Platform,
    ) -> None:
        """Initialize the Healthchecks.io entity."""
        super().__init__(coordinator)
        self.hass: HomeAssistant = hass
        self._attr_available = False
        self._ping_uuid: str = ping_uuid
        self._attr_name: str = name
        self._attr_unique_id: str = f"{coordinator.config_entry.entry_id}_{platform}_{ping_uuid}"
        self._attr_extra_state_attributes: dict[str, Any] = {}
        self._attr_icon: str = ICON_DEFAULT

        registry = er.async_get(self.hass)
        current_entity_id = registry.async_get_entity_id(
            platform,
            DOMAIN,
            self._attr_unique_id,
        )
        if current_entity_id is not None:
            self.entity_id = current_entity_id
        else:
            self.entity_id = generate_entity_id(
                f"{platform}.{{}}",
                f"healthchecksio_{name}",
                hass=self.hass,
            )

        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "HealthChecks.io",
        }

    @property
    def available(self) -> bool:
        """Return whether the coordinator and this check are available."""
        return self.coordinator.last_update_success and self._attr_available

    async def async_added_to_hass(self) -> None:
        """Update the entity after it is added to Home Assistant."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Apply coordinator data to the entity."""
        _LOGGER.debug("Updating: %s", self._attr_name)
        check: dict[str, Any] | None = self.coordinator.data.get(self._ping_uuid)
        if not check:
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_available = True
        self._attr_name = check.get(ATTR_NAME) or self._attr_name
        status: Any = check.get(ATTR_STATUS)
        self._attr_extra_state_attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
        self._attr_extra_state_attributes[ATTR_LAST_PING] = check.get(ATTR_LAST_PING)
        self._set_status_icon(status)
        self._update_status(status)
        self.async_write_ha_state()

    def _set_status_icon(self, status: Any) -> None:
        """Set the common entity icon for a Healthchecks.io status."""
        self._attr_icon = (
            _STATUS_ICONS.get(status.lower(), ICON_DEFAULT)
            if isinstance(status, str)
            else ICON_DEFAULT
        )

    @abstractmethod
    def _update_status(self, status: Any) -> None:
        """Update platform-specific state from a Healthchecks.io status."""
