"""Asynchronous Modbus TCP client for Kaysun GW-Modbus(A)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
import logging
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    IDU_DISCRETE_STRIDE,
    IDU_INPUT_STRIDE,
    IDU_TYPE_AUTO,
    IDU_TYPE_HTHM,
    IDU_TYPE_VRF,
    MAX_MODBUS_BITS,
    MAX_MODBUS_REGISTERS,
    ODU_DISCRETE_STRIDE,
    ODU_INPUT_STRIDE,
)
from .models import GatewayData, IduState, OduState
from .protocol import (
    contiguous_chunks,
    decode_error_code,
    decode_temperature,
    idu_discrete_address,
    idu_holding_address,
    idu_input_address,
    odu_discrete_address,
    odu_input_address,
)

_LOGGER = logging.getLogger(__name__)


class KaysunModbusError(Exception):
    """Base exception raised for communication or response failures."""


class KaysunModbusClient:
    """Serialize access to one GW-Modbus(A) TCP endpoint."""

    def __init__(self, host: str, port: int, unit_id: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self._client = AsyncModbusTcpClient(
            host,
            port=port,
            timeout=timeout,
            retries=1,
            reconnect_delay=0.5,
        )
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        """Return whether the underlying TCP client is connected."""
        return self._client.connected

    async def async_connect(self) -> None:
        """Connect to the gateway."""
        try:
            connected = await self._client.connect()
        except (ModbusException, OSError, TimeoutError) as err:
            raise KaysunModbusError(str(err)) from err
        if not connected:
            raise KaysunModbusError(f"Unable to connect to {self.host}:{self.port}")

    def close(self) -> None:
        """Close the TCP connection."""
        self._client.close()

    async def async_probe(
        self, idu_addresses: Sequence[int], odu_addresses: Sequence[int]
    ) -> None:
        """Connect and verify that a documented register can be read."""
        await self.async_connect()
        if idu_addresses:
            await self._read_input_registers(idu_input_address(idu_addresses[0]), 16)
        elif odu_addresses:
            await self._read_input_registers(odu_input_address(odu_addresses[0]), 4)
        else:
            raise KaysunModbusError("At least one IDU or ODU address is required")

    async def async_read_all(
        self,
        idu_addresses: Sequence[int],
        odu_addresses: Sequence[int],
        type_overrides: dict[int, str],
    ) -> GatewayData:
        """Read all configured devices with bounded contiguous requests."""
        data = GatewayData()
        idu_registers = await self._read_device_blocks(
            idu_addresses,
            idu_input_address,
            IDU_INPUT_STRIDE,
            registers=True,
        )
        idu_bits = await self._read_device_blocks(
            idu_addresses,
            idu_discrete_address,
            IDU_DISCRETE_STRIDE,
            registers=False,
        )
        for address in idu_addresses:
            registers = idu_registers[address]
            bits = idu_bits[address]
            data.idus[address] = self._parse_idu(
                address, registers, bits, type_overrides.get(address, IDU_TYPE_AUTO)
            )

        odu_registers = await self._read_device_blocks(
            odu_addresses,
            odu_input_address,
            ODU_INPUT_STRIDE,
            registers=True,
        )
        odu_bits = await self._read_device_blocks(
            odu_addresses,
            odu_discrete_address,
            ODU_DISCRETE_STRIDE,
            registers=False,
        )
        for address in odu_addresses:
            registers = odu_registers[address]
            bits = odu_bits[address]
            error_raw = registers[3]
            data.odus[address] = OduState(
                address=address,
                online=bool(bits[2]),
                power_on=bool(bits[0]),
                error=bool(bits[1]),
                mode=registers[0],
                outdoor_temperature=decode_temperature(registers[1]),
                active_idus=registers[2],
                error_raw=error_raw,
                error_code=decode_error_code(error_raw),
            )
        return data

    async def _read_device_blocks(
        self,
        addresses: Sequence[int],
        address_fn: Callable[[int], int],
        stride: int,
        *,
        registers: bool,
    ) -> dict[int, tuple[Any, ...]]:
        result: dict[int, tuple[Any, ...]] = {}
        maximum = MAX_MODBUS_REGISTERS if registers else MAX_MODBUS_BITS
        for chunk in contiguous_chunks(addresses, stride, maximum):
            count = len(chunk.addresses) * stride
            start = address_fn(chunk.first)
            values = (
                await self._read_input_registers(start, count)
                if registers
                else await self._read_discrete_inputs(start, count)
            )
            for offset, address in enumerate(chunk.addresses):
                device_values = values[offset * stride : (offset + 1) * stride]
                result[address] = tuple(device_values)
        return result

    async def async_write_idu(
        self, address: int, register_offset: int, value: int
    ) -> None:
        """Write one IDU control value with function code 0x10."""
        register = idu_holding_address(address, register_offset)
        await self._execute("write_registers", register, values=[value])

    async def _read_input_registers(self, address: int, count: int) -> list[int]:
        response = await self._execute("read_input_registers", address, count=count)
        registers = getattr(response, "registers", None)
        if registers is None or len(registers) < count:
            raise KaysunModbusError(f"Short input-register response at {address}")
        return list(registers[:count])

    async def _read_discrete_inputs(self, address: int, count: int) -> list[bool]:
        response = await self._execute("read_discrete_inputs", address, count=count)
        bits = getattr(response, "bits", None)
        if bits is None or len(bits) < count:
            raise KaysunModbusError(f"Short discrete-input response at {address}")
        return [bool(value) for value in bits[:count]]

    async def _execute(self, method_name: str, address: int, **kwargs: Any) -> Any:
        async with self._lock:
            try:
                if not self._client.connected and not await self._client.connect():
                    raise KaysunModbusError(
                        f"Unable to connect to {self.host}:{self.port}"
                    )
                method = getattr(self._client, method_name)
                response = await method(address, device_id=self.unit_id, **kwargs)
            except KaysunModbusError:
                raise
            except (ModbusException, OSError, TimeoutError) as err:
                raise KaysunModbusError(str(err)) from err
            if response is None or response.isError():
                raise KaysunModbusError(
                    f"Modbus error at address {address}: {response}"
                )
            return response

    @staticmethod
    def _parse_idu(
        address: int,
        registers: tuple[int, ...],
        bits: tuple[bool, ...],
        override: str,
    ) -> IduState:
        detected = IDU_TYPE_HTHM if registers[13] == 1 else IDU_TYPE_VRF
        kind = detected if override == IDU_TYPE_AUTO else override
        common = {
            "address": address,
            "kind": kind,
            "online": bool(bits[2]),
            "power_on": bool(bits[0]),
            "error": bool(bits[1]),
            "mode": registers[0],
            "error_raw": registers[6] if kind == IDU_TYPE_HTHM else registers[5],
            "raw_registers": registers,
        }
        if kind == IDU_TYPE_HTHM:
            error_raw = registers[6]
            return IduState(
                **common,
                heating_setpoint=decode_temperature(registers[1]),
                set_temperature=decode_temperature(registers[2]),
                water_inlet_temperature=decode_temperature(registers[3]),
                water_outlet_temperature=decode_temperature(registers[4]),
                water_tank_temperature=decode_temperature(registers[5]),
                error_code=decode_error_code(error_raw),
                mode_lock=registers[7],
            )
        return IduState(
            **common,
            fan_speed=registers[1],
            set_temperature=decode_temperature(registers[2]),
            heating_setpoint=decode_temperature(registers[3]),
            indoor_temperature=decode_temperature(registers[4]),
            error_code=str(registers[5]),
            mode_lock=registers[6],
            fan_lock=registers[7],
            remote_lock=registers[8],
            wired_lock=registers[9],
            swing_lock=registers[12],
        )
