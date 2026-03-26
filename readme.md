# Pico WiFi Robot Car (Standalone Pico + Phone)

This branch now targets a **standalone runtime architecture**:

**phone browser ↔ Pico W AP ↔ lightweight HTTP server ↔ your robot code**

A computer is only needed to copy files onto the Pico initially.

---

## Architecture

The project is separated into three layers:

1. **Transport/server layer** (`lib/wifi_command_server.py`)
   - Starts Pico W Wi-Fi AP.
   - Serves dashboard assets.
   - Parses lightweight HTTP requests.
   - Provides reusable route handling and safety timeout.

2. **Schema/UI contract layer** (`GET /api/schema`)
   - Pico returns JSON schema with controls + telemetry definitions.
   - Frontend builds controls dynamically from schema.

3. **User robot application layer** (`code.py`)
   - Hardware setup, motor logic, sensor reads.
   - Registers commands/sliders/telemetry with the server API.

---

## File Layout

- `code.py` - default robot car runtime using the reusable server API.
- `lib/wifi_command_server.py` - reusable Pico AP + HTTP + schema server.
- `lib/wifi_dashboard_assets.py` - embedded HTML/CSS/JS served by the Pico.
- `examples/code_minimal.py` - smallest custom robot example.
- `WifiCommandServer.py` - backward-compatible shim import.

Legacy desktop/client files are still present for reference, but the primary runtime path is now Pico + phone.

---

## API Endpoints

Implemented endpoints:

- `GET /` -> dashboard HTML
- `GET /app.js` -> frontend JS
- `GET /app.css` -> frontend CSS
- `GET /api/schema` -> dashboard schema
- `GET /api/state` -> current telemetry/state
- `GET /api/ping` -> health check
- `POST /api/command` -> invoke command (`{ "id": "forward", "event": "press" }`)
- `POST /api/set` -> set slider/value (`{ "id": "speed", "value": 45 }`)
- `POST /api/emergency_stop` -> immediate stop path

---

## Developer API

`WifiCommandServer` supports decorator-based registration:

```python
from wifi_command_server import WifiCommandServer

server = WifiCommandServer(ssid="RobotCar", password="12345678")

@server.command("forward", motion=True, on_release=stop)
def forward():
    car.forward()

@server.command("stop")
def stop():
    car.stop()

@server.slider("speed", min=0, max=100, default=50)
def set_speed(value):
    car.set_speed(value)

@server.telemetry("battery")
def get_battery():
    return read_battery_voltage()

server.set_emergency_stop(stop)
server.run()
```

### Notes
- `motion=True` marks controls that refresh the movement timeout watchdog.
- `on_release=` enables press/release behavior in the dynamic UI.

---

## Deploy to Pico

1. Copy files to Pico CIRCUITPY drive:
   - `code.py`
   - `lib/wifi_command_server.py`
   - `lib/wifi_dashboard_assets.py`
2. Ensure CircuitPython and `adafruit_motor` library are installed.
3. Reboot Pico.

---

## Connect Phone and Drive

1. Power the Pico robot.
2. Join Wi-Fi AP from your phone (default in `code.py`: `RobotCar` / `12345678`).
3. Open browser to `http://192.168.4.1/`.
4. UI loads schema from `/api/schema` and builds controls automatically.
5. Use controls; telemetry updates from `/api/state` polling.

---

## Safety / Failsafe

- Server has a **command timeout failsafe** (`command_timeout_ms`, default 1200 ms in `code.py` usage).
- If motion command updates stop while moving, server invokes emergency stop handler.
- Dedicated `POST /api/emergency_stop` endpoint and large UI emergency button are included.

---

## CircuitPython Constraints and Tradeoffs

- Assets are embedded as Python strings to keep deployment simple and avoid extra filesystem I/O logic.
- HTTP parser is intentionally minimal (small JSON payloads, no heavy framework).
- Keep handlers lightweight and non-blocking; long sensor reads should be avoided in request path.
- Telemetry getter errors are isolated and reported as `null` so UI remains usable.
