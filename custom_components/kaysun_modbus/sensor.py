"""Diagnostic and outdoor-unit sensors for Kaysun GW-Modbus(A)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KaysunRuntimeData
from .const import DOMAIN
from .entity import KaysunDeviceEntity
from .models import IduState, OduState

ODU_MODE_NAMES = {
    0: "off",
    1: "cool",
    2: "heat",
    3: "forced_cool",
    4: "master_cool",
    5: "master_heat",
}


@dataclass(frozen=True, kw_only=True)
class KaysunSensorDescription(SensorEntityDescription):
    """Describe a Kaysun diagnostic sensor."""

    value_fn: Callable[[IduState | OduState], Any]


IDU_SENSOR_DESCRIPTIONS = (
    KaysunSensorDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.error_code,
    ),
)

ODU_SENSOR_DESCRIPTIONS = (
    KaysunSensorDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.outdoor_temperature,
    ),
    KaysunSensorDescription(
        key="active_idus",
        translation_key="active_idus",
        icon="mdi:air-conditioner",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.active_idus,
    ),
    KaysunSensorDescription(
        key="operating_mode",
        translation_key="operating_mode",
        icon="mdi:hvac",
        value_fn=lambda state: ODU_MODE_NAMES.get(state.mode, f"unknown_{state.mode}"),
    ),
    KaysunSensorDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.error_code,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IDU and ODU sensors."""
    runtime: KaysunRuntimeData = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for address in runtime.coordinator.idu_addresses:
        entities.extend(
            KaysunDeviceSensor(runtime, entry, "idu", address, description)
            for description in IDU_SENSOR_DESCRIPTIONS
        )
    for address in runtime.coordinator.odu_addresses:
        entities.extend(
            KaysunDeviceSensor(runtime, entry, "odu", address, description)
            for description in ODU_SENSOR_DESCRIPTIONS
        )
    async_add_entities(entities)


class KaysunDeviceSensor(KaysunDeviceEntity, SensorEntity):
    """Sensor backed by the coordinator's latest IDU/ODU state."""

    entity_description: KaysunSensorDescription

    def __init__(
        self,
        runtime: KaysunRuntimeData,
        entry: ConfigEntry,
        device_type: str,
        address: int,
        description: KaysunSensorDescription,
    ) -> None:
        model = "Indoor unit" if device_type == "idu" else "Outdoor unit"
        super().__init__(runtime.coordinator, entry, device_type, address, model)
        self.entity_description = description
        self._attr_unique_id = (
            f"{entry.entry_id}_{device_type}_{address}_{description.key}"
        )

    @property
    def native_value(self) -> Any:
        state = (
            self.coordinator.data.idus[self.address]
            if self.device_type == "idu"
            else self.coordinator.data.odus[self.address]
        )
        return self.entity_description.value_fn(state)
