# Pico WiFi Robot Car Guide

This repository provides a full **robot-over-WiFi control stack** with three main parts:

1. **Robot-side HTTP command server** (`WifiCommandServer`) that runs on a Pico W / Pico 2 W in CircuitPython.
2. **Computer-side Python client** (`RobotClient`) for sending command paths to the robot.
3. **Desktop dashboard** (`dashboard_app.py`) for configurable buttons/sliders + optional keyboard bindings.
4. **Mobile-first web dashboard** (`web/dashboard.html`) with a two-zone touch layout for drive + secondary actions.

### Install as a mobile app (PWA)

The web dashboard includes a web app manifest, service worker shell caching, and an offline fallback page.

- **iOS Safari**: open `dashboard.html`, tap **Share** → **Add to Home Screen**.
- **Android Chrome**: use the **Install app** banner when shown, or open the three-dot menu and choose **Install app** / **Add to Home screen**.

Offline behavior notes:
- Static shell assets (HTML/CSS/JS/icons/manifest) are cached for quicker startup.
- Live robot command endpoints (`/cmd/...`) are always fetched from network and are never cached.
- If navigation happens while offline, `offline.html` is shown with a clear control-unavailable message.

---

## 1) Project Overview

### Robot-side server
The robot hosts its own WiFi Access Point (AP), listens for HTTP `GET` requests, and maps request paths to handler functions.

- AP setup and server loop are provided by `WifiCommandServer`.
- Routes support:
  - **exact paths** (`/forward`),
  - **prefix paths** (`/sound/anything`),
  - **template paths** (`/speed/{value}`, `/arm/{joint}/{angle}`).

### Computer-side client + dashboard
- `RobotClient` sends HTTP paths (`send_path`, `send_segments`) from your computer to the Pico AP.
- `dashboard_app.py` provides a Tkinter UI for adding controls at runtime and saving/loading JSON control layouts.
- `web/dashboard.html` + `web/dashboard.css` + `web/dashboard.js` provide a responsive browser dashboard (mobile first, progressively enhanced for larger screens).

---

## 2) Quickstart

## A. Robot setup (Pico W / Pico 2 W)

### Prerequisites
- CircuitPython firmware on your board.
- This repo's `WifiCommandServer.py` copied to the board filesystem.
- A boot script (`code.py`) on the board to start WiFi AP + route handlers.

### Configure AP credentials
Use `start_wifi_ap(network_name=..., password=...)`.

> Password must be at least 8 characters.

### Example `code.py` boot script
```python
import board
import pwmio
from adafruit_motor import servo
from WifiCommandServer import WifiCommandServer

# --- Motor setup (example pins; adjust for your wiring) ---
pwm_left = pwmio.PWMOut(board.GP15, frequency=50)
pwm_right = pwmio.PWMOut(board.GP16, frequency=50)
left_servo = servo.ContinuousServo(pwm_left)
right_servo = servo.ContinuousServo(pwm_right)

def move(left, right):
    left_servo.throttle = max(min(left, 1.0), -1.0)
    right_servo.throttle = max(min(right, 1.0), -1.0)
    return f"left={left}, right={right}"


def stop():
    return move(0, 0)


def set_speed(value: float):
    # template example: /speed/{value}
    speed = max(min(value, 1.0), -1.0)
    return move(speed, speed)


def play_sound(name: str):
    # prefix example: /sound/<name>
    return f"sound:{name}"


server = WifiCommandServer({
    "/stop": stop,
    "/forward": lambda: move(-1.0, -1.0),
    "/back": lambda: move(1.0, 1.0),
    "/left": lambda: move(-0.5, 0.5),
    "/right": lambda: move(0.5, -0.5),
})

server.register_route("/speed/{value}", set_speed)   # template route
server.register_route("/sound/", play_sound)         # prefix route (trailing slash)

server.start_wifi_ap(network_name="MyRobotCar", password="MyPass123")
server.start()  # enters blocking loop
```

After boot, connect your computer to the robot AP (e.g., `MyRobotCar`). Default AP IP is typically `192.168.4.1`.

## B. Computer setup

### Python version
Use **Python 3.10+** (3.11/3.12 recommended).

### Install dependencies
From this repo directory:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install requests pynput
```

- `requests` is required for `RobotClient`.
- `pynput` is used by the legacy keyboard client (`WifiCommandClient.py`).
- `tkinter` is needed for the dashboard and is usually included with standard Python installers.

### First command example
```python
from pico_wifi_robot.client import RobotClient

client = RobotClient("http://192.168.4.1")
resp = client.send_path("/forward")
print(resp.status_code, resp.text)
```

---

## 3) Library API: `WifiCommandServer`

### Minimal usage
```python
from WifiCommandServer import WifiCommandServer

server = WifiCommandServer(registry={
    "/ping": lambda: "pong"
})
server.start_wifi_ap("MyRobotCar", "MyPass123")
server.start()
```

### Registering routes

#### Exact routes
- Match only one exact path.

```python
server.register_route("/stop", stop_handler)
# GET /stop -> stop_handler()
```

#### Prefix routes
- Prefix route keys end with `/`.
- The unmatched suffix is passed as **one positional argument**.

```python
def play_sound(name: str):
    return f"sound:{name}"

server.register_route("/sound/", play_sound)
# GET /sound/horn -> play_sound("horn")
```

#### Template routes
- Template segments use `{param}` syntax.
- Segment names are bound as keyword args to your handler.

```python
def set_servo(index: int, angle: float):
    return f"servo {index} -> {angle}"

server.register_route("/servo/{index}/{angle}", set_servo)
# GET /servo/2/45.5 -> set_servo(index=2, angle=45.5)
```

### Handler signatures and parameter types

For template routes, handler parameter coercion works like this:

- If you annotate parameters with `int`, `float`, `bool`, `str`, values are converted to that type.
- With no type annotations, values are auto-coerced in this order:
  1. `true`/`false` -> `bool`
  2. integer -> `int`
  3. float -> `float`
  4. fallback -> `str`

Examples:

```python
def lights(enabled: bool):
    return f"lights={enabled}"

server.register_route("/lights/{enabled}", lights)
# /lights/true -> lights(enabled=True)


def speed(value):
    # untyped, will receive int/float/str based on coercion
    return f"speed={value} ({type(value).__name__})"
```

When parameters are missing, extra, or malformed, server returns HTTP `400`.

---

## 4) Client API

Use `pico_wifi_robot.client.RobotClient` for command transport.

## `send_path` examples

```python
from pico_wifi_robot.client import RobotClient

client = RobotClient("http://192.168.4.1", timeout=0.5)

# Example 1: function-style path
client.send_path("/somePath/someFunction/someValue")

# Example 2: numeric segment
client.send_path("/somePath/123")

# Also accepted without leading slash:
client.send_path("forward")
```

## `send_segments` helper

```python
client.send_segments("somePath", "someFunction", "someValue")
client.send_segments("somePath", 123)
```

`send_segments` URL-encodes each segment for you.

## Error handling and retries

`send_path` returns a `requests.Response` on success and raises exceptions on network failures/timeouts.

```python
import time
import requests
from pico_wifi_robot.client import RobotClient

client = RobotClient("http://192.168.4.1", timeout=0.5)


def send_with_retry(path: str, retries: int = 3, delay: float = 0.2):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            response = client.send_path(path)
            if 200 <= response.status_code < 300:
                return response
            print(f"HTTP {response.status_code}: {response.text}")
        except requests.RequestException as exc:
            last_exc = exc
            print(f"Attempt {attempt}/{retries} failed: {exc}")

        if attempt < retries:
            time.sleep(delay)

    if last_exc:
        raise last_exc
    raise RuntimeError(f"Command failed after {retries} attempts: {path}")
```

---

## 5) Dashboard Guide (`dashboard_app.py`)

Run:

```bash
python dashboard_app.py
```

## Adding button and slider controls

1. Click **Add Control**.
2. Choose `button` or `slider`.
3. Enter:
   - **Display Label** (e.g., `Forward`, `Speed`)
   - **Path Template** (must start with `/`)
   - Optional **Key Binding** (single character)
4. For sliders, also configure default/min/max/step.

Path template notes:
- Use `{value}` placeholder for slider-based values.
- Example button template: `/forward`
- Example slider template: `/speed/{value}`

## Mapping keyboard keys

- Set `Key Binding` (like `w`, `s`, `1`, etc.) while creating each control.
- The app prevents duplicate key bindings.
- Pressing the mapped key triggers that control:
  - button -> sends its path,
  - slider -> sends with default slider value.

## JSON config format example

Dashboard save/load uses this format:

```json
{
  "controls": [
    {
      "control_type": "button",
      "label": "Forward",
      "path_template": "/forward",
      "key_binding": "w"
    },
    {
      "control_type": "slider",
      "label": "Speed",
      "path_template": "/speed/{value}",
      "key_binding": "q",
      "default": 0.5,
      "min_value": 0.0,
      "max_value": 1.0,
      "step": 0.1
    }
  ]
}
```

---

## 6) Troubleshooting

## Network connectivity issues
- Ensure your computer is connected to the robot AP SSID (not your home WiFi).
- Confirm robot AP started successfully from serial logs.
- Verify target IP (usually `http://192.168.4.1`).
- Check signal strength/distance and power stability.

## Malformed routes
- Route paths must start with `/`.
- Template placeholders must match handler argument names.
- Prefix handlers should use routes ending with `/` and accept one argument.
- For dashboard templates, only `{value}` is supported by built-in validation.

## Timeouts / intermittent request failures
- Increase client timeout (e.g., `RobotClient(..., timeout=1.0)`).
- Add retry logic (see section 4).
- Send commands at a lower rate to avoid overloading the board.
- If server loop appears stuck, reboot the board and reconnect to the AP.

---

## Repository map

- `WifiCommandServer.py` -> robot-side AP + HTTP command server.
- `pico_wifi_robot/client.py` -> host-side `RobotClient` transport.
- `dashboard_app.py` -> desktop dashboard GUI.
- `WifiCommandClient.py` -> legacy WASD keyboard client wrapper.
- `pico_wifi_robot/config.py` -> load/save JSON control configs for package control models.
