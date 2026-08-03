"""Base entity for the Healthchecks.io integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import generate_entity_id
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HealthchecksioDataUpdateCoordinator


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
        self._attr_unique_id: str = f"{platform}_{ping_uuid}"

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
