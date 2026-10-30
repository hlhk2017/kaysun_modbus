"""Status binary sensors for Kaysun GW-Modbus(A)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KaysunRuntimeData
from .const import DOMAIN
from .entity import KaysunDeviceEntity, KaysunGatewayEntity
from .models import IduState, OduState


@dataclass(frozen=True, kw_only=True)
class KaysunBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a device binary sensor."""

    value_fn: Callable[[IduState | OduState], bool]


DEVICE_DESCRIPTIONS = (
    KaysunBinarySensorDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.online,
    ),
    KaysunBinarySensorDescription(
        key="error",
        translation_key="error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.error,
    ),
    KaysunBinarySensorDescription(
        key="power",
        translation_key="power",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda state: state.power_on,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up gateway and device binary sensors."""
    runtime: KaysunRuntimeData = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [
        KaysunGatewayConnectedBinarySensor(runtime, entry)
    ]
    for address in runtime.coordinator.idu_addresses:
        entities.extend(
            KaysunDeviceBinarySensor(runtime, entry, "idu", address, description)
            for description in DEVICE_DESCRIPTIONS
        )
    for address in runtime.coordinator.odu_addresses:
        entities.extend(
            KaysunDeviceBinarySensor(runtime, entry, "odu", address, description)
            for description in DEVICE_DESCRIPTIONS
        )
    async_add_entities(entities)


class KaysunGatewayConnectedBinarySensor(KaysunGatewayEntity, BinarySensorEntity):
    """Expose successful communication with the gateway."""

    _attr_translation_key = "gateway_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: KaysunRuntimeData, entry: ConfigEntry) -> None:
        super().__init__(runtime.coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_gateway_connected"

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success


class KaysunDeviceBinarySensor(KaysunDeviceEntity, BinarySensorEntity):
    """Expose online, error, or power state for an IDU/ODU."""

    entity_description: KaysunBinarySensorDescription

    def __init__(
        self,
        runtime: KaysunRuntimeData,
        entry: ConfigEntry,
        device_type: str,
        address: int,
        description: KaysunBinarySensorDescription,
    ) -> None:
        model = "Indoor unit" if device_type == "idu" else "Outdoor unit"
        super().__init__(runtime.coordinator, entry, device_type, address, model)
        self.entity_description = description
        self._attr_unique_id = (
            f"{entry.entry_id}_{device_type}_{address}_{description.key}"
        )

    @property
    def available(self) -> bool:
        if self.entity_description.key == "online":
            return self.coordinator.last_update_success
        return super().available

    @property
    def is_on(self) -> bool:
        state = (
            self.coordinator.data.idus[self.address]
            if self.device_type == "idu"
            else self.coordinator.data.odus[self.address]
        )
        return self.entity_description.value_fn(state)
