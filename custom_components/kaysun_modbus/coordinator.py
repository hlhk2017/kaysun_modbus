"""Data coordinator for Kaysun GW-Modbus(A)."""

from __future__ import annotations

from datetime import timedelta
import logging
from time import monotonic
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KaysunModbusClient, KaysunModbusError
from .const import DOMAIN
from .models import GatewayData

_LOGGER = logging.getLogger(__name__)
_OPTIMISTIC_STATE_SECONDS = 15.0


class KaysunCoordinator(DataUpdateCoordinator[GatewayData]):
    """Poll all devices behind one gateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: KaysunModbusClient,
        idu_addresses: tuple[int, ...],
        odu_addresses: tuple[int, ...],
        type_overrides: dict[int, str],
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.idu_addresses = idu_addresses
        self.odu_addresses = odu_addresses
        self.type_overrides = type_overrides
        self._optimistic_state: dict[tuple[int, str], tuple[Any, float]] = {}

    async def _async_update_data(self) -> GatewayData:
        try:
            data = await self.client.async_read_all(
                self.idu_addresses, self.odu_addresses, self.type_overrides
            )
        except KaysunModbusError as err:
            raise UpdateFailed(str(err)) from err
        self._apply_optimistic_state(data)
        return data

    def _apply_optimistic_state(self, data: GatewayData) -> None:
        """Protect recent control values from stale scheduled-poll results."""
        now = monotonic()
        for key, (value, expires_at) in tuple(self._optimistic_state.items()):
            if now >= expires_at:
                del self._optimistic_state[key]
                continue
            address, attribute = key
            if (state := data.idus.get(address)) is not None:
                setattr(state, attribute, value)

    async def async_write_idu(
        self,
        address: int,
        register_offset: int,
        value: int,
        optimistic_changes: dict[str, Any] | None = None,
    ) -> None:
        """Write and publish the assumed state without triggering a read."""
        try:
            await self.client.async_write_idu(address, register_offset, value)
        except KaysunModbusError as err:
            raise UpdateFailed(str(err)) from err

        if optimistic_changes and (state := self.data.idus.get(address)) is not None:
            expires_at = monotonic() + _OPTIMISTIC_STATE_SECONDS
            for attribute, optimistic_value in optimistic_changes.items():
                setattr(state, attribute, optimistic_value)
                self._optimistic_state[(address, attribute)] = (
                    optimistic_value,
                    expires_at,
                )
            self.async_set_updated_data(self.data)
