"""Fan-speed entities for Kaysun VRF indoor units."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KaysunRuntimeData
from .const import ATTR_MODBUS_ADDRESS, DOMAIN, IDU_TYPE_HTHM
from .entity import KaysunDeviceEntity
from .models import IduState
from .protocol import (
    FAN_MODE_LABELS,
    FAN_PRESET_AUTO,
    fan_level_from_percentage,
    fan_level_from_raw,
    fan_percentage_from_level,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one fan-speed entity per VRF indoor unit."""
    runtime: KaysunRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KaysunFan(runtime, entry, address)
        for address in runtime.coordinator.idu_addresses
        if runtime.coordinator.data.idus[address].kind != IDU_TYPE_HTHM
    )


class KaysunFan(KaysunDeviceEntity, FanEntity):
    """Control fan speed independently from the climate entity."""

    _attr_translation_key = "fan_speed"
    _attr_should_poll = False
    _attr_speed_count = 7
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(
        self, runtime: KaysunRuntimeData, entry: ConfigEntry, address: int
    ) -> None:
        super().__init__(runtime.coordinator, entry, "idu", address, "VRF indoor unit")
        self._attr_unique_id = f"{entry.entry_id}_idu_{address}_fan"

    @property
    def state_data(self) -> IduState:
        """Return the latest state for this indoor unit."""
        return self.coordinator.data.idus[self.address]

    @property
    def is_on(self) -> bool:
        """Return whether the indoor unit is running."""
        return self.state_data.power_on

    @property
    def percentage(self) -> int | None:
        """Return the manual fan level as a seven-step percentage."""
        if not self.is_on:
            return 0
        level = fan_level_from_raw(self.state_data.fan_speed)
        return None if level is None else fan_percentage_from_level(level)

    @property
    def preset_modes(self) -> list[str]:
        """Expose Auto as the fan entity's preset."""
        return [FAN_PRESET_AUTO]

    @property
    def preset_mode(self) -> str | None:
        """Return Auto when no fixed manual level is active."""
        return (
            FAN_PRESET_AUTO
            if self.is_on and fan_level_from_raw(self.state_data.fan_speed) is None
            else None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the exact human-readable level alongside percentage."""
        level = fan_level_from_raw(self.state_data.fan_speed)
        speed_level = None
        if self.is_on:
            speed_level = (
                FAN_PRESET_AUTO if level is None else FAN_MODE_LABELS[level - 1]
            )
        return {
            ATTR_MODBUS_ADDRESS: self.address,
            "speed_level": speed_level,
        }

    async def _async_ensure_fan_mode(self) -> None:
        """Start an idle indoor unit in fan-only mode before changing speed."""
        if self.state_data.power_on:
            return
        await self.coordinator.async_write_idu(
            self.address,
            0,
            1,
            {"mode": 1, "power_on": True},
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on fan-only mode and optionally select a speed."""
        await self._async_ensure_fan_mode()
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the indoor unit."""
        await self.coordinator.async_write_idu(
            self.address,
            0,
            0,
            {"mode": 0, "power_on": False},
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set one of seven manual fan levels."""
        if percentage <= 0:
            await self.async_turn_off()
            return
        await self._async_ensure_fan_mode()
        level = fan_level_from_percentage(percentage)
        await self.coordinator.async_write_idu(
            self.address,
            1,
            level,
            {"fan_speed": level},
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the automatic fan-speed preset."""
        if preset_mode != FAN_PRESET_AUTO:
            raise ValueError(f"Unsupported preset mode: {preset_mode}")
        await self._async_ensure_fan_mode()
        await self.coordinator.async_write_idu(
            self.address,
            1,
            0,
            {"fan_speed": 0},
        )
