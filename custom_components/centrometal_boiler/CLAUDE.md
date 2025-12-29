# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom integration for Centrometal boilers (pellet heating systems). Uses the `py-centrometal-web-boiler` library to communicate with Centrometal's cloud API via websocket for real-time updates.

**Domain**: `centrometal_boiler`
**Supported devices**: PelTec II Lambda (`peltec2`), CM Pelet Set (`cmpelet`), BioTec Plus (`biopl`)

## Architecture

### Core Components

- **`__init__.py`**: Entry point. Sets up `WebBoilerSystem` wrapper that handles login, websocket connection, periodic refresh (tick loop), and reconnection logic. Contains monkey patches for the upstream library (SSL context fix, quieter logging).

- **`WebBoilerSystem` class**: Manages single account session. Key methods:
  - `start()`: Login → get configuration → open websocket → initial refresh
  - `tick()`: Runs every second, triggers refresh (4 min interval) or relogin (60s interval when disconnected)
  - `relogin()`: Reconnection after disconnect

### Platforms

| Platform | File | Purpose |
|----------|------|---------|
| sensor | `sensor.py` | Temperature sensors, counters, status values. Has watchdog that auto-reloads config entry on stale data. |
| switch | `switch.py` | Power switch (on/off), heating circuit switches |
| binary_sensor | `binary_sensor.py` | Websocket connection status |

### Sensor System (`sensors/` folder)

Sensors are created via factory methods that iterate device parameters:

- **`WebBoilerGenericSensor`**: Base class. Subscribes to parameter websocket updates, marks params as "used" to prevent duplicates.
- **`generic_sensors_peltec.py`**: Defines `PELTEC_GENERIC_SENSORS` dict mapping param names to sensor metadata.
- **`WebBoilerBinaryOnOffSensor`**: Shows boolean params (`B_CMD`, pump states) as On/Off.

### Switches (`switches/` folder)

- **`WebBoilerPowerSwitch`**: Main boiler on/off. Reads `B_CMD` and `B_STATE`. Calls `web_boiler_client.turn(serial, True/False)`.
- **`WebBoilerCircuitSwitch`**: Controls heating circuits.

### Data Flow

1. `WebBoilerClient` receives websocket push → calls `on_parameter_updated`
2. Entities subscribe via `parameter.set_update_callback(callback, callback_id)`
3. Callback calls `self.async_write_ha_state()` to update HA

### Key Constants (`const.py`)

- `WEB_BOILER_LOGIN_RETRY_INTERVAL = 60` (seconds)
- `WEB_BOILER_REFRESH_INTERVAL = 240` (seconds)

## Common Parameter Names

| Param | Description |
|-------|-------------|
| B_CMD | Command Active (On/Off request) |
| B_STATE | Boiler State (physical state) |
| B_Tk1 | Boiler Temperature |
| B_Tkm1 | DHW Temperature |
| B_razP | Pellet Level (%) |
| CNT_* | Runtime counters |

## Testing

Copy to `custom_components/centrometal_boiler/` in HA config, restart, add via UI.

## Dependencies

- `py-centrometal-web-boiler==0.0.58` (see `manifest.json`)
