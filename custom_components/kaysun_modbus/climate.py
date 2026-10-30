"""Climate entities for Kaysun indoor units."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KaysunRuntimeData
from .const import (
    ATTR_ERROR_CODE,
    ATTR_FAN_LOCK,
    ATTR_MODBUS_ADDRESS,
    ATTR_MODE_LOCK,
    ATTR_RAW_MODE,
    ATTR_REMOTE_LOCK,
    ATTR_SWING_LOCK,
    ATTR_WIRED_LOCK,
    CONF_HTHM_MAX_TEMP,
    CONF_HTHM_MIN_TEMP,
    CONF_VRF_MAX_TEMP,
    CONF_VRF_MIN_TEMP,
    DEFAULT_HTHM_MAX_TEMP,
    DEFAULT_HTHM_MIN_TEMP,
    DEFAULT_VRF_MAX_TEMP,
    DEFAULT_VRF_MIN_TEMP,
    DOMAIN,
    IDU_TYPE_HTHM,
)
from .entity import KaysunDeviceEntity
from .models import IduState
from .protocol import (
    FAN_MODE_LABELS,
    FAN_PRESET_AUTO,
    encode_set_temperature,
    fan_level_from_raw,
)

_VRF_HVAC_FROM_RAW = {
    0: HVACMode.OFF,
    1: HVACMode.FAN_ONLY,
    2: HVACMode.COOL,
    3: HVACMode.HEAT,
    4: HVACMode.AUTO,
    5: HVACMode.DRY,
}
_VRF_HVAC_TO_RAW = {value: key for key, value in _VRF_HVAC_FROM_RAW.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one climate entity per configured IDU."""
    runtime: KaysunRuntimeData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        KaysunClimate(runtime, entry, address)
        for address in runtime.coordinator.idu_addresses
    )


class KaysunClimate(KaysunDeviceEntity, ClimateEntity):
    """Control one VRF or HTHM indoor unit."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_should_poll = False

    def __init__(
        self, runtime: KaysunRuntimeData, entry: ConfigEntry, address: int
    ) -> None:
        state = runtime.coordinator.data.idus[address]
        model = "HTHM indoor unit" if state.kind == IDU_TYPE_HTHM else "VRF indoor unit"
        super().__init__(runtime.coordinator, entry, "idu", address, model)
        self._config = runtime.config
        self._attr_unique_id = f"{entry.entry_id}_idu_{address}_climate"

    @property
    def state_data(self) -> IduState:
        """Return the latest state for this IDU."""
        return self.coordinator.data.idus[self.address]

    @property
    def is_hthm(self) -> bool:
        return self.state_data.kind == IDU_TYPE_HTHM

    @property
    def min_temp(self) -> float:
        key = CONF_HTHM_MIN_TEMP if self.is_hthm else CONF_VRF_MIN_TEMP
        default = DEFAULT_HTHM_MIN_TEMP if self.is_hthm else DEFAULT_VRF_MIN_TEMP
        return float(self._config.get(key, default))

    @property
    def max_temp(self) -> float:
        key = CONF_HTHM_MAX_TEMP if self.is_hthm else CONF_VRF_MAX_TEMP
        default = DEFAULT_HTHM_MAX_TEMP if self.is_hthm else DEFAULT_VRF_MAX_TEMP
        return float(self._config.get(key, default))

    @property
    def supported_features(self) -> ClimateEntityFeature:
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if not self.is_hthm:
            features |= ClimateEntityFeature.FAN_MODE
        return features

    @property
    def hvac_modes(self) -> list[HVACMode]:
        if self.is_hthm:
            return [HVACMode.OFF, HVACMode.HEAT]
        return [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.AUTO,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
        ]

    @property
    def hvac_mode(self) -> HVACMode:
        if self.is_hthm:
            return HVACMode.HEAT if self.state_data.mode in (3, 10) else HVACMode.OFF
        return _VRF_HVAC_FROM_RAW.get(self.state_data.mode, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction:
        if self.hvac_mode == HVACMode.OFF or not self.state_data.power_on:
            return HVACAction.OFF
        if self.hvac_mode == HVACMode.HEAT:
            return HVACAction.HEATING
        if self.hvac_mode == HVACMode.COOL:
            return HVACAction.COOLING
        if self.hvac_mode == HVACMode.DRY:
            return HVACAction.DRYING
        if self.hvac_mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        if self.is_hthm:
            return self.state_data.water_outlet_temperature
        return self.state_data.indoor_temperature

    @property
    def target_temperature(self) -> float | None:
        if self.is_hthm:
            return self.state_data.heating_setpoint
        return self.state_data.set_temperature

    @property
    def fan_modes(self) -> list[str] | None:
        """Return Auto and the seven documented manual fan levels."""
        if self.is_hthm:
            return None
        return [FAN_PRESET_AUTO, *FAN_MODE_LABELS]

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan level using user-facing labels."""
        if self.is_hthm:
            return None
        level = fan_level_from_raw(self.state_data.fan_speed)
        return FAN_PRESET_AUTO if level is None else FAN_MODE_LABELS[level - 1]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.state_data
        attributes: dict[str, Any] = {
            ATTR_MODBUS_ADDRESS: self.address,
            ATTR_RAW_MODE: state.mode,
            ATTR_ERROR_CODE: state.error_code,
            ATTR_MODE_LOCK: state.mode_lock,
        }
        if self.is_hthm:
            attributes.update(
                {
                    "water_inlet_temperature": state.water_inlet_temperature,
                    "water_tank_temperature": state.water_tank_temperature,
                }
            )
        else:
            attributes.update(
                {
                    ATTR_FAN_LOCK: state.fan_lock,
                    ATTR_REMOTE_LOCK: state.remote_lock,
                    ATTR_WIRED_LOCK: state.wired_lock,
                    ATTR_SWING_LOCK: state.swing_lock,
                    "dual_setpoint_heating_temperature": state.heating_setpoint,
                }
            )
        return attributes

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if self.is_hthm:
            water_active = self.state_data.mode in (7, 8, 10)
            if hvac_mode == HVACMode.HEAT:
                raw_mode = 10 if water_active else 3
            elif hvac_mode == HVACMode.OFF:
                raw_mode = 8 if water_active else 0
            else:
                return
        else:
            raw_mode = _VRF_HVAC_TO_RAW[hvac_mode]
        register_offset = 4 if self.is_hthm else 0
        optimistic_mode = 7 if self.is_hthm and raw_mode == 8 else raw_mode
        await self.coordinator.async_write_idu(
            self.address,
            register_offset,
            raw_mode,
            {"mode": optimistic_mode, "power_on": raw_mode != 0},
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        register_offset = 6 if self.is_hthm else 2
        state_attribute = "heating_setpoint" if self.is_hthm else "set_temperature"
        await self.coordinator.async_write_idu(
            self.address,
            register_offset,
            encode_set_temperature(float(temperature)),
            {state_attribute: float(temperature)},
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set Auto or one of the seven manual fan levels."""
        if self.is_hthm:
            return
        if fan_mode == FAN_PRESET_AUTO:
            raw_speed = 0
        else:
            try:
                raw_speed = FAN_MODE_LABELS.index(fan_mode) + 1
            except ValueError:
                return
        await self.coordinator.async_write_idu(
            self.address,
            1,
            raw_speed,
            {"fan_speed": raw_speed},
        )

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT if self.is_hthm else HVACMode.COOL)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)
