"""Register addressing and value conversion for GW-Modbus(A)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
import re

_ERROR_PREFIXES = ("A", "b", "C", "E", "F", "H", "L", "J", "n", "P", "r", "t", "U")
_ERROR_SUFFIXES = tuple("0123456789ABCDEF") + ("H", "L", "P", "U")

FAN_MODE_LABELS = tuple(f"{speed}\u6863" for speed in range(1, 8))
FAN_PRESET_AUTO = "\u81ea\u52a8"
_FAN_LEVEL_FROM_RAW = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    6: 6,
    7: 7,
    8: 1,
    9: 1,
    10: 4,
    11: 7,
}


class AddressExpressionError(ValueError):
    """Raised when an address or type expression cannot be parsed."""


@dataclass(frozen=True, slots=True)
class AddressChunk:
    """A contiguous sequence of device addresses."""

    first: int
    addresses: tuple[int, ...]


def idu_input_address(address: int) -> int:
    """Return the protocol address for IDU input register 30001 + n*16."""
    return address * 16


def idu_discrete_address(address: int) -> int:
    """Return the protocol address for IDU discrete input 10001 + n*8."""
    return address * 8


def idu_holding_address(address: int, offset: int = 0) -> int:
    """Return the protocol address for IDU holding register 45002 + n*8."""
    return 5001 + address * 8 + offset


def odu_input_address(address: int) -> int:
    """Return the protocol address for ODU input register 32001 + n*10."""
    return 2000 + address * 10


def odu_discrete_address(address: int) -> int:
    """Return the protocol address for ODU discrete input 11001 + n*8."""
    return 1000 + address * 8


def fan_level_from_raw(value: int) -> int | None:
    """Convert a documented fan value to level 1-7; Auto has no fixed level."""
    return _FAN_LEVEL_FROM_RAW.get(value)


def fan_level_from_percentage(percentage: int) -> int:
    """Convert Home Assistant percentage to the nearest level from 1 to 7."""
    return max(1, min(7, round(percentage * 7 / 100)))


def fan_percentage_from_level(level: int) -> int:
    """Convert a level from 1 to 7 to Home Assistant percentage."""
    return round(level * 100 / 7)


def parse_address_expression(value: str, maximum: int) -> tuple[int, ...]:
    """Parse comma-separated addresses and inclusive ranges."""
    normalized = (
        value.strip()
        .replace("\uff0c", ",")
        .replace("\uff1b", ",")
        .replace(";", ",")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("~", "-")
        .replace("\uff5e", "-")
    )
    if not normalized:
        return ()

    result: set[int] = set()
    for token in normalized.split(","):
        token = token.strip()
        if not token:
            continue
        match = re.fullmatch(r"(\d+)\s*(?:-\s*(\d+))?", token)
        if match is None:
            raise AddressExpressionError(token)
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start > end or start < 0 or end > maximum:
            raise AddressExpressionError(token)
        result.update(range(start, end + 1))
    return tuple(sorted(result))


def parse_idu_type_overrides(value: str) -> dict[int, str]:
    """Parse address:type pairs used to override automatic model detection."""
    normalized = (
        value.strip().replace("\uff0c", ",").replace("\uff1b", ",").replace(";", ",")
    )
    if not normalized:
        return {}

    overrides: dict[int, str] = {}
    for token in normalized.split(","):
        if not token.strip():
            continue
        parts = token.strip().lower().split(":", 1)
        if len(parts) != 2 or not parts[0].strip().isdigit():
            raise AddressExpressionError(token)
        address = int(parts[0].strip())
        kind = parts[1].strip()
        if address < 0 or address > 63 or kind not in {"auto", "vrf", "hthm"}:
            raise AddressExpressionError(token)
        overrides[address] = kind
    return overrides


def contiguous_chunks(
    addresses: Iterable[int], stride: int, maximum_items: int
) -> Iterator[AddressChunk]:
    """Split addresses into bounded, contiguous chunks for bulk reads."""
    ordered = tuple(sorted(set(addresses)))
    if not ordered:
        return
    maximum_devices = max(1, maximum_items // stride)
    current: list[int] = [ordered[0]]
    for address in ordered[1:]:
        if address == current[-1] + 1 and len(current) < maximum_devices:
            current.append(address)
            continue
        yield AddressChunk(current[0], tuple(current))
        current = [address]
    yield AddressChunk(current[0], tuple(current))


def signed_16(value: int) -> int:
    """Interpret an unsigned Modbus word as a signed 16-bit integer."""
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def decode_temperature(value: int) -> float:
    """Decode a signed, tenths-of-a-degree input register."""
    return signed_16(value) / 10.0


def encode_set_temperature(value: float) -> int:
    """Encode a setpoint using bits 0-6 plus bit 7 for half a degree."""
    rounded = round(float(value) * 2) / 2
    whole = int(rounded)
    if whole < 1 or whole > 100:
        raise ValueError("temperature must be between 1 and 100 C")
    return whole | (0x80 if rounded - whole >= 0.5 else 0)


def decode_error_code(value: int) -> str:
    """Decode the manual's 9-bit HTHM/ODU error-code scheme."""
    code = value & 0x1FF
    if code == 0:
        return "0"
    if 1 <= code <= 260:
        index = code - 1
        return f"{_ERROR_PREFIXES[index // 20]}{_ERROR_SUFFIXES[index % 20]}"
    return f"0x{code:03X}"
