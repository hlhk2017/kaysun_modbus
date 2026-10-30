"""Runtime models for the Kaysun GW-Modbus(A) integration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class IduState:
    """State read for one indoor unit."""

    address: int
    kind: str
    online: bool
    power_on: bool
    error: bool
    mode: int
    fan_speed: int = 0
    set_temperature: float | None = None
    heating_setpoint: float | None = None
    indoor_temperature: float | None = None
    water_inlet_temperature: float | None = None
    water_outlet_temperature: float | None = None
    water_tank_temperature: float | None = None
    error_raw: int = 0
    error_code: str = "0"
    mode_lock: int = 0
    fan_lock: int = 0
    remote_lock: int = 0
    wired_lock: int = 0
    swing_lock: int = 0
    raw_registers: tuple[int, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class OduState:
    """State read for one outdoor unit."""

    address: int
    online: bool
    power_on: bool
    error: bool
    mode: int
    outdoor_temperature: float
    active_idus: int
    error_raw: int
    error_code: str


@dataclass(slots=True)
class GatewayData:
    """All state collected during one poll."""

    idus: dict[int, IduState] = field(default_factory=dict)
    odus: dict[int, OduState] = field(default_factory=dict)
