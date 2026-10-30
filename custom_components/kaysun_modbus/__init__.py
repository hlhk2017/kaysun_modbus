"""Kaysun GW-Modbus(A) integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .api import KaysunModbusClient
from .const import (
    CONF_IDU_ADDRESSES,
    CONF_IDU_TYPES,
    CONF_ODU_ADDRESSES,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UNIT_ID,
    DEFAULT_IDU_ADDRESSES,
    DEFAULT_IDU_TYPES,
    DEFAULT_ODU_ADDRESSES,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import KaysunCoordinator
from .protocol import parse_address_expression, parse_idu_type_overrides


@dataclass(slots=True)
class KaysunRuntimeData:
    """Objects shared by the entity platforms."""

    client: KaysunModbusClient
    coordinator: KaysunCoordinator
    config: dict[str, Any]


def merged_config(entry: ConfigEntry) -> dict[str, Any]:
    """Return setup data overlaid with editable options."""
    return {**entry.data, **entry.options}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a configured Kaysun gateway."""
    config = merged_config(entry)
    client = KaysunModbusClient(
        config[CONF_HOST],
        int(config.get(CONF_PORT, DEFAULT_PORT)),
        int(config.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)),
        float(config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
    )
    coordinator = KaysunCoordinator(
        hass,
        entry,
        client,
        parse_address_expression(
            config.get(CONF_IDU_ADDRESSES, DEFAULT_IDU_ADDRESSES), 63
        ),
        parse_address_expression(
            config.get(CONF_ODU_ADDRESSES, DEFAULT_ODU_ADDRESSES), 31
        ),
        parse_idu_type_overrides(config.get(CONF_IDU_TYPES, DEFAULT_IDU_TYPES)),
        int(config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = KaysunRuntimeData(
        client=client,
        coordinator=coordinator,
        config=config,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        client.close()
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
        raise
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry and close its Modbus connection."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        runtime: KaysunRuntimeData = hass.data[DOMAIN].pop(entry.entry_id)
        runtime.client.close()
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unloaded
