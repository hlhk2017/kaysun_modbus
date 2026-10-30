"""Shared entity classes for Kaysun GW-Modbus(A)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL_GATEWAY
from .coordinator import KaysunCoordinator


def gateway_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return the gateway device registry information."""
    config = {**entry.data, **entry.options}
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        model=MODEL_GATEWAY,
        name=entry.title,
        configuration_url=f"http://{config.get('host', '')}:8586",
    )


class KaysunGatewayEntity(CoordinatorEntity[KaysunCoordinator]):
    """Entity attached directly to the gateway."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KaysunCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = gateway_device_info(entry)


class KaysunDeviceEntity(CoordinatorEntity[KaysunCoordinator]):
    """Entity attached to an IDU or ODU behind the gateway."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KaysunCoordinator,
        entry: ConfigEntry,
        device_type: str,
        address: int,
        model: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self.address = address
        self.device_type = device_type
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{device_type}_{address}")},
            manufacturer=MANUFACTURER,
            model=model,
            name=f"{entry.title} {device_type.upper()} {address}",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def available(self) -> bool:
        """Require a successful gateway poll and an online device bit."""
        if not super().available:
            return False
        if self.device_type == "idu":
            state = self.coordinator.data.idus.get(self.address)
        else:
            state = self.coordinator.data.odus.get(self.address)
        return state is not None and state.online
