"""Reusable AP + HTTP command server for Pico W CircuitPython projects."""

import json
import time
import wifi
import socketpool

from wifi_dashboard_assets import HTML, CSS, JS


class WifiCommandServer:
    """Robot-agnostic command server with schema-driven dashboard endpoints."""

    def __init__(
        self,
        ssid="RobotCar",
        password="12345678",
        title="Pico Robot Dashboard",
        command_timeout_ms=1200,
        poll_timeout_s=0.1,
    ):
        self.ssid = ssid
        self.password = password
        self.title = title
        self.command_timeout_ms = command_timeout_ms
        self.poll_timeout_s = poll_timeout_s

        self._commands = {}
        self._sliders = {}
        self._telemetry = {}
        self._controls = []
        self._telemetry_meta = []
        self._state = {}

        self._running = True
        self._ap_ip = None
        self._last_motion_ms = self._now_ms()
        self._movement_active = False
        self._emergency_handler = None
        self._idle_callback = None

    def _now_ms(self):
        return int(time.monotonic() * 1000)

    # -------- Registration helpers --------
    def command(self, command_id, label=None, motion=False, on_release=None):
        def decorator(func):
            self.register_command(
                command_id,
                func,
                label=label,
                motion=motion,
                on_release=on_release,
            )
            return func

        return decorator

    def register_command(self, command_id, handler, label=None, motion=False, on_release=None):
        self._commands[command_id] = {
            "handler": handler,
            "motion": bool(motion),
            "on_release": on_release,
        }
        self._controls.append(
            {
                "type": "button",
                "id": command_id,
                "label": label or command_id,
                "on_release": bool(on_release),
                "motion": bool(motion),
            }
        )

    def slider(self, slider_id, min=0, max=100, default=0, label=None, step=1, motion=False):
        def decorator(func):
            self.register_slider(
                slider_id,
                func,
                min=min,
                max=max,
                default=default,
                label=label,
                step=step,
                motion=motion,
            )
            return func

        return decorator

    def register_slider(self, slider_id, handler, min=0, max=100, default=0, label=None, step=1, motion=False):
        self._sliders[slider_id] = {
            "handler": handler,
            "min": min,
            "max": max,
            "default": default,
            "step": step,
            "motion": bool(motion),
        }
        self._state[slider_id] = default
        self._controls.append(
            {
                "type": "slider",
                "id": slider_id,
                "label": label or slider_id,
                "min": min,
                "max": max,
                "default": default,
                "step": step,
                "motion": bool(motion),
            }
        )

    def telemetry(self, telemetry_id, label=None):
        def decorator(func):
            self.register_telemetry(telemetry_id, func, label=label)
            return func

        return decorator

    def register_telemetry(self, telemetry_id, getter, label=None):
        self._telemetry[telemetry_id] = getter
        self._telemetry_meta.append({"id": telemetry_id, "label": label or telemetry_id})

    def set_emergency_stop(self, handler):
        self._emergency_handler = handler

    def set_idle_callback(self, callback):
        self._idle_callback = callback

    # -------- AP + HTTP transport --------
    def start_ap(self):
        print("Starting AP:", self.ssid)
        wifi.radio.start_ap(self.ssid, self.password)
        while wifi.radio.ipv4_address_ap is None:
            time.sleep(0.2)
        self._ap_ip = str(wifi.radio.ipv4_address_ap)
        print("AP ready at", self._ap_ip)
        return self._ap_ip

    def _start_socket(self):
        pool = socketpool.SocketPool(wifi.radio)
        server = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
        server.setsockopt(pool.SOL_SOCKET, pool.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", 80))
        server.listen(2)
        server.settimeout(self.poll_timeout_s)
        print("HTTP server: http://%s/" % self._ap_ip)
        return server

    def _json_response(self, conn, payload, status_code=200):
        body = json.dumps(payload)
        self._send_response(conn, body, status_code=status_code, content_type="application/json")

    def _send_response(self, conn, body, status_code=200, content_type="text/plain"):
        reasons = {200: "OK", 400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed", 500: "Server Error"}
        reason = reasons.get(status_code, "OK")
        if not isinstance(body, str):
            body = str(body)
        response = (
            "HTTP/1.1 %d %s\r\n" % (status_code, reason)
            + "Content-Type: %s\r\n" % content_type
            + "Connection: close\r\n"
            + "Content-Length: %d\r\n\r\n" % len(body)
            + body
        )
        conn.send(response.encode("utf-8"))

    def _parse_request(self, raw):
        request = raw.decode("utf-8")
        lines = request.split("\r\n")
        request_line = lines[0]
        parts = request_line.split(" ")
        if len(parts) < 2:
            return None

        method = parts[0].upper()
        path = parts[1].split("?", 1)[0]
        body = ""
        sep = request.find("\r\n\r\n")
        if sep != -1:
            body = request[sep + 4 :]

        return {"method": method, "path": path, "body": body}

    def _build_schema(self):
        return {
            "title": self.title,
            "controls": self._controls,
            "telemetry": self._telemetry_meta,
        }

    def _build_state(self):
        state = {}
        for key in self._state:
            state[key] = self._state[key]

        for telemetry_id, getter in self._telemetry.items():
            try:
                state[telemetry_id] = getter()
            except Exception:
                state[telemetry_id] = None
        return state

    def _touch_motion(self):
        self._movement_active = True
        self._last_motion_ms = self._now_ms()

    def _mark_safe(self):
        self._movement_active = False
        self._last_motion_ms = self._now_ms()

    def _apply_command(self, command_id, event="press"):
        meta = self._commands.get(command_id)
        if meta is None:
            return 404, {"ok": False, "error": "unknown command"}

        try:
            if event == "release" and meta["on_release"] is not None:
                meta["on_release"]()
            else:
                meta["handler"]()

            if meta["motion"]:
                self._touch_motion()
            if command_id in ("stop", "emergency_stop"):
                self._mark_safe()
            return 200, {"ok": True}
        except Exception as exc:
            return 500, {"ok": False, "error": str(exc)}

    def _apply_slider(self, slider_id, value):
        meta = self._sliders.get(slider_id)
        if meta is None:
            return 404, {"ok": False, "error": "unknown slider"}

        try:
            if value < meta["min"]:
                value = meta["min"]
            if value > meta["max"]:
                value = meta["max"]
            meta["handler"](value)
            self._state[slider_id] = value
            if meta["motion"]:
                self._touch_motion()
            return 200, {"ok": True, "value": value}
        except Exception as exc:
            return 500, {"ok": False, "error": str(exc)}

    def _handle_emergency_stop(self):
        try:
            if self._emergency_handler is not None:
                self._emergency_handler()
            elif "stop" in self._commands:
                self._commands["stop"]["handler"]()
            self._mark_safe()
            return 200, {"ok": True}
        except Exception as exc:
            return 500, {"ok": False, "error": str(exc)}

    def _check_timeout(self):
        if not self._movement_active:
            return
        if self.command_timeout_ms <= 0:
            return
        if self._now_ms() - self._last_motion_ms < self.command_timeout_ms:
            return

        print("Movement timeout reached -> emergency stop")
        self._handle_emergency_stop()

    def _route(self, req):
        method = req["method"]
        path = req["path"]

        if method == "GET" and path == "/":
            return 200, HTML, "text/html"
        if method == "GET" and path == "/app.js":
            return 200, JS, "application/javascript"
        if method == "GET" and path == "/app.css":
            return 200, CSS, "text/css"
        if method == "GET" and path == "/api/ping":
            return 200, {"ok": True, "ip": self._ap_ip}, "json"
        if method == "GET" and path == "/api/schema":
            return 200, self._build_schema(), "json"
        if method == "GET" and path == "/api/state":
            return 200, self._build_state(), "json"

        if method == "POST" and path == "/api/command":
            try:
                payload = json.loads(req["body"] or "{}")
            except Exception:
                return 400, {"ok": False, "error": "bad json"}, "json"
            command_id = payload.get("id")
            event = payload.get("event", "press")
            status, out = self._apply_command(command_id, event=event)
            return status, out, "json"

        if method == "POST" and path == "/api/set":
            try:
                payload = json.loads(req["body"] or "{}")
                slider_id = payload.get("id")
                value = payload.get("value")
                if value is None:
                    raise ValueError("missing value")
                value = float(value)
            except Exception:
                return 400, {"ok": False, "error": "bad payload"}, "json"
            status, out = self._apply_slider(slider_id, value)
            return status, out, "json"

        if method == "POST" and path == "/api/emergency_stop":
            status, out = self._handle_emergency_stop()
            return status, out, "json"

        if path.startswith("/api/"):
            if method not in ("GET", "POST"):
                return 405, {"ok": False, "error": "method not allowed"}, "json"
            return 404, {"ok": False, "error": "not found"}, "json"

        return 404, "Not Found", "text/plain"

    def run(self):
        self.start_ap()
        server = self._start_socket()

        while self._running:
            try:
                conn, _addr = server.accept()
            except OSError:
                self._check_timeout()
                if self._idle_callback is not None:
                    try:
                        self._idle_callback()
                    except Exception:
                        pass
                continue

            try:
                raw = conn.recv(2048)
                if not raw:
                    conn.close()
                    continue

                req = self._parse_request(raw)
                if req is None:
                    self._send_response(conn, "Malformed request", status_code=400)
                    conn.close()
                    continue

                status, payload, content_type = self._route(req)
                if content_type == "json":
                    self._json_response(conn, payload, status_code=status)
                else:
                    self._send_response(conn, payload, status_code=status, content_type=content_type)

            except Exception as exc:
                self._send_response(conn, "Server error: %s" % exc, status_code=500)
            finally:
                self._check_timeout()
                try:
                    conn.close()
                except Exception:
                    pass

    def stop(self):
        self._running = False
