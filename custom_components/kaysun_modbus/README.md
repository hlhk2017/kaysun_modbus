# Kaysun GW-Modbus(A) for Home Assistant

[简体中文](README.zh-CN.md) | English

Local Modbus TCP integration for the Kaysun `GW-MOD(A)` / `K05-MODBUS A`
gateway. It follows the register maps in manual `MD20U-014A-ZH`, version A.0.

The integration uses the PyModbus version supplied by Home Assistant's built-in
Modbus integration. This avoids dependency conflicts across Home Assistant
releases, including 2026.4 (`pymodbus 3.11`) and 2026.7 (`pymodbus 3.13`).

## Features

- UI setup and editable options; no YAML is required.
- Indoor unit addresses `0-63`. This installation defaults to `0-31` for its
  32 indoor units, while non-contiguous ranges such as `0-7,10,12-31` remain supported.
- Automatic VRF/HTHM detection from input register `30014 + n*16`.
- VRF climate control: off, fan, cool, heat, auto, dry, target temperature,
  and fan speed with Auto plus levels 1-7 (no High/Medium/Low aliases).
- A separate fan entity for every VRF indoor unit, with seven speed steps and
  Auto as a preset. Climate and fan controls remain synchronized.
- HTHM space-heating climate control without interrupting an active water-heating mode.
- Indoor/outdoor online, error, and running status.
- Outdoor temperature, operating mode, active IDU count, and decoded error code.
- Contiguous bulk reads to reduce Modbus traffic.
- Successful control writes update Home Assistant immediately without triggering
  a status read. Each controlled field keeps its assumed value for at least 15
  seconds; scheduled polls may replace it with the gateway state after that window.

For 32 consecutive IDUs, each poll uses five bounded input-register requests
(no request exceeds 120 registers) and one discrete-input request. It does not
issue a separate status request for every indoor unit.

## Gateway preparation

1. Connect the gateway LAN port and open `http://192.168.1.185:8586` (factory default).
2. Assign a fixed IP address and set a unique Modbus address.
3. In Home Assistant, open **Settings > Devices & services > Add integration** and
   select **Kaysun GW-Modbus(A)**.
4. Enter the Modbus TCP host/port, gateway Modbus address, and IDU/ODU addresses.

The web configuration interface uses port `8586`; Modbus TCP normally uses port `502`.
If Home Assistant runs in Docker, its container must be able to route to the gateway LAN.

## Address conventions

The manual lists reference addresses such as `30001` and `45002`. Modbus protocol
addresses are zero-based:

- IDU input registers: `30001 + n*16` -> protocol address `n*16`.
- IDU controls: `45002 + n*8` -> protocol address `5001 + n*8`.
- ODU input registers: `32001 + n*10` -> protocol address `2000 + n*10`.
- IDU discrete inputs: `10001 + n*8` -> protocol address `n*8`.
- ODU discrete inputs: `11001 + n*8` -> protocol address `1000 + n*8`.

Control writes use function code `0x10`, as required by the manual. Some indoor-unit
models do not support every mode or fan speed; configure temperature limits to match
the connected equipment.
