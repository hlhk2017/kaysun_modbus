"""Constants for the Kaysun GW-Modbus(A) integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "kaysun_modbus"

PLATFORMS: tuple[Platform, ...] = (
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.SENSOR,
)

CONF_GATEWAY_NAME = "gateway_name"
CONF_UNIT_ID = "unit_id"
CONF_IDU_ADDRESSES = "idu_addresses"
CONF_ODU_ADDRESSES = "odu_addresses"
CONF_IDU_TYPES = "idu_types"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_VRF_MIN_TEMP = "vrf_min_temperature"
CONF_VRF_MAX_TEMP = "vrf_max_temperature"
CONF_HTHM_MIN_TEMP = "hthm_min_temperature"
CONF_HTHM_MAX_TEMP = "hthm_max_temperature"

DEFAULT_GATEWAY_NAME = "Kaysun GW-Modbus(A)"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
DEFAULT_IDU_ADDRESSES = "0-31"
DEFAULT_ODU_ADDRESSES = ""
DEFAULT_IDU_TYPES = ""
DEFAULT_SCAN_INTERVAL = 15
DEFAULT_TIMEOUT = 3
DEFAULT_VRF_MIN_TEMP = 16.0
DEFAULT_VRF_MAX_TEMP = 30.0
DEFAULT_HTHM_MIN_TEMP = 5.0
DEFAULT_HTHM_MAX_TEMP = 60.0

IDU_INPUT_STRIDE = 16
IDU_DISCRETE_STRIDE = 8
ODU_INPUT_STRIDE = 10
ODU_DISCRETE_STRIDE = 8

MAX_IDU_ADDRESS = 63
MAX_ODU_ADDRESS = 31
MAX_MODBUS_REGISTERS = 120
MAX_MODBUS_BITS = 1920

IDU_TYPE_AUTO = "auto"
IDU_TYPE_VRF = "vrf"
IDU_TYPE_HTHM = "hthm"
IDU_TYPES = {IDU_TYPE_AUTO, IDU_TYPE_VRF, IDU_TYPE_HTHM}

MANUFACTURER = "Kaysun"
MODEL_GATEWAY = "GW-Modbus(A) / K05-MODBUS A"

ATTR_MODBUS_ADDRESS = "modbus_address"
ATTR_RAW_MODE = "raw_mode"
ATTR_ERROR_CODE = "error_code"
ATTR_MODE_LOCK = "mode_lock"
ATTR_FAN_LOCK = "fan_speed_lock"
ATTR_REMOTE_LOCK = "remote_controller_lock"
ATTR_WIRED_LOCK = "wired_controller_lock"
ATTR_SWING_LOCK = "swing_lock"

DATA_RUNTIME = "runtime"
