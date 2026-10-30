"""Config flow for Kaysun GW-Modbus(A)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .api import KaysunModbusClient, KaysunModbusError
from .const import (
    CONF_GATEWAY_NAME,
    CONF_HTHM_MAX_TEMP,
    CONF_HTHM_MIN_TEMP,
    CONF_IDU_ADDRESSES,
    CONF_IDU_TYPES,
    CONF_ODU_ADDRESSES,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_UNIT_ID,
    CONF_VRF_MAX_TEMP,
    CONF_VRF_MIN_TEMP,
    DEFAULT_GATEWAY_NAME,
    DEFAULT_HTHM_MAX_TEMP,
    DEFAULT_HTHM_MIN_TEMP,
    DEFAULT_IDU_ADDRESSES,
    DEFAULT_IDU_TYPES,
    DEFAULT_ODU_ADDRESSES,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_UNIT_ID,
    DEFAULT_VRF_MAX_TEMP,
    DEFAULT_VRF_MIN_TEMP,
    DOMAIN,
    MAX_IDU_ADDRESS,
    MAX_ODU_ADDRESS,
)
from .protocol import (
    AddressExpressionError,
    parse_address_expression,
    parse_idu_type_overrides,
)


def _defaults(values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return complete form defaults."""
    return {
        CONF_GATEWAY_NAME: DEFAULT_GATEWAY_NAME,
        CONF_HOST: "192.168.1.185",
        CONF_PORT: DEFAULT_PORT,
        CONF_UNIT_ID: DEFAULT_UNIT_ID,
        CONF_IDU_ADDRESSES: DEFAULT_IDU_ADDRESSES,
        CONF_ODU_ADDRESSES: DEFAULT_ODU_ADDRESSES,
        CONF_IDU_TYPES: DEFAULT_IDU_TYPES,
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_TIMEOUT: DEFAULT_TIMEOUT,
        CONF_VRF_MIN_TEMP: DEFAULT_VRF_MIN_TEMP,
        CONF_VRF_MAX_TEMP: DEFAULT_VRF_MAX_TEMP,
        CONF_HTHM_MIN_TEMP: DEFAULT_HTHM_MIN_TEMP,
        CONF_HTHM_MAX_TEMP: DEFAULT_HTHM_MAX_TEMP,
        **(values or {}),
    }


def _schema(values: dict[str, Any]) -> vol.Schema:
    """Build the shared setup/options schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_GATEWAY_NAME, default=values[CONF_GATEWAY_NAME]
            ): selector({"text": {"type": "text"}}),
            vol.Required(CONF_HOST, default=values[CONF_HOST]): selector(
                {"text": {"type": "text"}}
            ),
            vol.Required(CONF_PORT, default=values[CONF_PORT]): selector(
                {"number": {"min": 1, "max": 65535, "mode": "box"}}
            ),
            vol.Required(CONF_UNIT_ID, default=values[CONF_UNIT_ID]): selector(
                {"number": {"min": 0, "max": 247, "mode": "box"}}
            ),
            vol.Required(
                CONF_IDU_ADDRESSES, default=values[CONF_IDU_ADDRESSES]
            ): selector({"text": {"type": "text"}}),
            vol.Optional(
                CONF_ODU_ADDRESSES, default=values[CONF_ODU_ADDRESSES]
            ): selector({"text": {"type": "text"}}),
            vol.Optional(CONF_IDU_TYPES, default=values[CONF_IDU_TYPES]): selector(
                {"text": {"type": "text"}}
            ),
            vol.Required(
                CONF_SCAN_INTERVAL, default=values[CONF_SCAN_INTERVAL]
            ): selector(
                {
                    "number": {
                        "min": 5,
                        "max": 300,
                        "step": 1,
                        "unit_of_measurement": "s",
                        "mode": "box",
                    }
                }
            ),
            vol.Required(CONF_TIMEOUT, default=values[CONF_TIMEOUT]): selector(
                {
                    "number": {
                        "min": 1,
                        "max": 15,
                        "step": 0.5,
                        "unit_of_measurement": "s",
                        "mode": "box",
                    }
                }
            ),
            vol.Required(
                CONF_VRF_MIN_TEMP, default=values[CONF_VRF_MIN_TEMP]
            ): selector(
                {"number": {"min": 1, "max": 99.5, "step": 0.5, "mode": "box"}}
            ),
            vol.Required(
                CONF_VRF_MAX_TEMP, default=values[CONF_VRF_MAX_TEMP]
            ): selector(
                {"number": {"min": 1.5, "max": 100, "step": 0.5, "mode": "box"}}
            ),
            vol.Required(
                CONF_HTHM_MIN_TEMP, default=values[CONF_HTHM_MIN_TEMP]
            ): selector(
                {"number": {"min": 1, "max": 99.5, "step": 0.5, "mode": "box"}}
            ),
            vol.Required(
                CONF_HTHM_MAX_TEMP, default=values[CONF_HTHM_MAX_TEMP]
            ): selector(
                {"number": {"min": 1.5, "max": 100, "step": 0.5, "mode": "box"}}
            ),
        }
    )


def _validate_input(
    user_input: dict[str, Any],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Validate expressions and cross-field constraints."""
    idus = parse_address_expression(user_input[CONF_IDU_ADDRESSES], MAX_IDU_ADDRESS)
    odus = parse_address_expression(
        user_input.get(CONF_ODU_ADDRESSES, ""), MAX_ODU_ADDRESS
    )
    overrides = parse_idu_type_overrides(user_input.get(CONF_IDU_TYPES, ""))
    if not idus and not odus:
        raise AddressExpressionError("no_devices")
    if set(overrides) - set(idus):
        raise AddressExpressionError("override_not_selected")
    if float(user_input[CONF_VRF_MIN_TEMP]) >= float(user_input[CONF_VRF_MAX_TEMP]):
        raise AddressExpressionError("vrf_temperature_range")
    if float(user_input[CONF_HTHM_MIN_TEMP]) >= float(user_input[CONF_HTHM_MAX_TEMP]):
        raise AddressExpressionError("hthm_temperature_range")
    return idus, odus


async def _async_validate_connection(
    user_input: dict[str, Any], idus: tuple[int, ...], odus: tuple[int, ...]
) -> None:
    client = KaysunModbusClient(
        user_input[CONF_HOST].strip(),
        int(user_input[CONF_PORT]),
        int(user_input[CONF_UNIT_ID]),
        float(user_input[CONF_TIMEOUT]),
    )
    try:
        await client.async_probe(idus, odus)
    finally:
        client.close()


class KaysunConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a Kaysun gateway."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial setup."""
        errors: dict[str, str] = {}
        values = _defaults(user_input)
        if user_input is not None:
            try:
                idus, odus = _validate_input(user_input)
            except AddressExpressionError:
                errors["base"] = "invalid_input"
            else:
                try:
                    await _async_validate_connection(user_input, idus, odus)
                except KaysunModbusError:
                    errors["base"] = "cannot_connect"
                else:
                    host = user_input[CONF_HOST].strip().lower()
                    port = int(user_input[CONF_PORT])
                    unit_id = int(user_input[CONF_UNIT_ID])
                    await self.async_set_unique_id(f"{host}:{port}:{unit_id}")
                    self._abort_if_unique_id_configured()
                    data = dict(user_input)
                    data[CONF_HOST] = user_input[CONF_HOST].strip()
                    return self.async_create_entry(
                        title=user_input[CONF_GATEWAY_NAME].strip(), data=data
                    )
        return self.async_show_form(
            step_id="user", data_schema=_schema(values), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the editable options flow."""
        return KaysunOptionsFlow()


class KaysunOptionsFlow(OptionsFlowWithReload):
    """Edit all gateway and device selection options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit integration options and verify the new endpoint."""
        errors: dict[str, str] = {}
        current = _defaults({**self.config_entry.data, **self.config_entry.options})
        values = _defaults(user_input) if user_input is not None else current
        if user_input is not None:
            try:
                idus, odus = _validate_input(user_input)
            except AddressExpressionError:
                errors["base"] = "invalid_input"
            else:
                try:
                    await _async_validate_connection(user_input, idus, odus)
                except KaysunModbusError:
                    errors["base"] = "cannot_connect"
                else:
                    host = user_input[CONF_HOST].strip()
                    unique_id = (
                        f"{host.lower()}:{int(user_input[CONF_PORT])}:"
                        f"{int(user_input[CONF_UNIT_ID])}"
                    )
                    duplicate = any(
                        entry.entry_id != self.config_entry.entry_id
                        and entry.unique_id == unique_id
                        for entry in self.hass.config_entries.async_entries(DOMAIN)
                    )
                    if duplicate:
                        errors["base"] = "already_configured"
                    else:
                        self.hass.config_entries.async_update_entry(
                            self.config_entry,
                            title=user_input[CONF_GATEWAY_NAME].strip(),
                            unique_id=unique_id,
                        )
                        data = dict(user_input)
                        data[CONF_HOST] = host
                        return self.async_create_entry(data=data)
        return self.async_show_form(
            step_id="init", data_schema=_schema(values), errors=errors
        )
