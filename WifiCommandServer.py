# Jack Tommaney, Nov 2025 / Jan - March 2026
"""
WifiProtocolAPI.py contains functions for 
interactions between a CircuitPython Pico 
with a wifi module and a connected computer.
"""

# Tested on a Raspberry Pi Pico 2 W with CircuitPython v 10.0.0
# Runs its own WiFi access point and HTTP command server (insecure)

import inspect
import time, wifi, socketpool

class WifiCommandServer():
    """
    Class encapsulating a WiFi command server for robotics and control applications.

    Data:
    - registry (dict): A mapping of HTTP paths to command handler functions.

    Functions:
    - start_wifi_ap(): Starts a WiFi access point with given SSID and password.
    - start_http_server(): Starts a simple HTTP server on the WiFi AP.
    - stop_http_server(): Stops the HTTP server by setting keepAlive to False.
    - send_http_response(): Sends a minimal HTTP response to a client.
    - register_route(): Registers custom command handlers for specific HTTP paths.
    - get_registry(): Returns the current command registry of paths and functions.
    - handle_path(): Interprets HTTP paths and calls registered command handlers.
    - listen_http_wireless(): Main loop that listens for HTTP requests and handles them.
    """

    registry = {}
    keepAlive = True

    def __init__(self, registry, deadman_timeout_ms=1500, deadman_stop_path="/stop"):
        self.registry = registry
        self._route_templates = []
        self.keepAlive = True
        self.deadman_timeout_ms = deadman_timeout_ms
        self.deadman_stop_path = deadman_stop_path
        self._last_heartbeat_ms = time.monotonic() * 1000
        self._deadman_engaged = False
        self._last_cmd_seq = -1
        self._last_client_timestamp = 0

        # Index templates pre-loaded in the incoming registry.
        for path, func in list(self.registry.items()):
            if self._is_route_template(path):
                self._route_templates.append((path, self._tokenize_template(path), func))

    def start(self):
        self.listen_http_wireless()

    # =======================
    # WiFi AP setup
    # =======================

    def start_wifi_ap(self, network_name="Pi-Pico-Wifi", password="password"):
        """
        Starts the WiFi access point.
        Args:
            network_name (str): SSID for the access point.
            password (str): Password for the access point (min 8 chars).
        Returns:
            ap_ip (str): The IP address of the access point.
        """

        AP_SSID = network_name
        AP_PASSWORD = password

        print("Starting Pico WiFi access point...")
        wifi.radio.start_ap(AP_SSID, AP_PASSWORD)

        # Wait for AP IP address to show up
        while wifi.radio.ipv4_address_ap is None:
            print("Waiting for AP IP address...")
            time.sleep(0.5)

        ap_ip = str(wifi.radio.ipv4_address_ap)
        print("AP started!")
        print("SSID:", AP_SSID)
        print("Password:", AP_PASSWORD)
        print("AP IP address:", ap_ip)

        return ap_ip

    # =======================
    # HTTP server setup
    # =======================

    def start_http_server(self, ap_ip):
        """
        Starts a simple HTTP server on the WiFi access point.
        Args:
            ap_ip (str): The IP address of the access point.
        Returns:
            server (socket): The listening server socket.
        """

        pool = socketpool.SocketPool(wifi.radio)
        server = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
        server.setsockopt(pool.SOL_SOCKET, pool.SO_REUSEADDR, 1)

        HOST = "0.0.0.0"  # listen on all interfaces
        PORT = 80

        server.bind((HOST, PORT))
        server.listen(1)
        server.settimeout(0.1)

        print(f"HTTP server listening on http://{ap_ip}:{PORT}/")
        return server
    
    def stop_http_server(self):
        """Stops the HTTP server by setting keepAlive to False in the main server loop."""
        self.keepAlive = False

    def _touch_heartbeat(self):
        self._last_heartbeat_ms = time.monotonic() * 1000
        self._deadman_engaged = False

    def _check_deadman(self):
        if self.deadman_timeout_ms is None or self.deadman_timeout_ms <= 0:
            return
        if self._deadman_engaged:
            return

        now_ms = time.monotonic() * 1000
        elapsed_ms = now_ms - self._last_heartbeat_ms
        if elapsed_ms < self.deadman_timeout_ms:
            return

        stop_handler = self.registry.get(self.deadman_stop_path)
        if stop_handler is None:
            return

        try:
            stop_handler()
            self._deadman_engaged = True
            print("Dead-man timeout reached; stop handler invoked.")
        except Exception as e:
            print("Dead-man stop handler error:", e)


    def send_http_response(self, conn, status_code=200, body="OK"):
        """Minimal HTTP response helper."""
        reason = "OK" if status_code == 200 else "ERROR"
        response = (
            f"HTTP/1.1 {status_code} {reason}\r\n"
            "Content-Type: text/plain\r\n"
            "Connection: close\r\n"
            f"Content-Length: {len(body)}\r\n"
            "\r\n"
            f"{body}"
        )
        conn.send(response.encode("utf-8"))

    def _parse_request_line(self, request_str):
        """
        Parse the HTTP request line and normalize method/path values.
        Returns:
            tuple: (method, path, status_code, error_message)
        """
        request_line = request_str.split("\r\n")[0]
        print("Request line:", request_line)

        parts = request_line.split(" ")
        if len(parts) < 2:
            return None, None, 400, "Malformed request"

        method = parts[0].strip().upper()
        path = parts[1].strip()

        if not path.startswith("/"):
            return None, None, 400, "Malformed request path"

        if method != "GET":
            return None, None, 405, "Only GET supported at this time"

        return method, path, None, None

    def register_route(self, path, func):
        """Utility for developers to add their own commands.
        Args:
            registry (dict): The route registry to add to.
            path (str): The HTTP path to register (e.g., "/mycommand").
            func (callable): The function to call when this path is requested.
        """
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("Route path must be a string starting with '/'.")

        if self._is_route_template(path):
            self._route_templates.append((path, self._tokenize_template(path), func))

        self.registry[path] = func

    def _is_route_template(self, path):
        return "{" in path and "}" in path

    def _split_path_segments(self, path):
        stripped = path.strip("/")
        if stripped == "":
            return []
        return [segment for segment in stripped.split("/") if segment != ""]

    def _tokenize_template(self, template):
        tokens = []
        for segment in self._split_path_segments(template):
            if segment.startswith("{") and segment.endswith("}") and len(segment) > 2:
                tokens.append(("param", segment[1:-1]))
            else:
                tokens.append(("literal", segment))
        return tokens

    def _coerce_path_value(self, value):
        lower = value.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False

        try:
            if value.startswith("0") and len(value) > 1 and value[1].isdigit():
                raise ValueError
            return int(value)
        except ValueError:
            pass

        try:
            return float(value)
        except ValueError:
            return value

    def _coerce_value_to_type(self, value, expected_type):
        if expected_type is inspect._empty or expected_type is str:
            return value
        if expected_type is bool:
            lower = value.lower()
            if lower == "true":
                return True
            if lower == "false":
                return False
            raise ValueError(f"expected bool, got '{value}'")
        if expected_type is int:
            return int(value)
        if expected_type is float:
            return float(value)
        return self._coerce_path_value(value)

    def _validate_handler_kwargs(self, handler, kwargs):
        try:
            signature = inspect.signature(handler)
            signature.bind(**kwargs)
            return True, None, signature
        except TypeError as e:
            message = str(e)
            if "unexpected keyword argument" in message or "missing" in message:
                return False, message, None
            raise

    def _match_template_route(self, path):
        path_segments = self._split_path_segments(path)

        for template, tokens, func in self._route_templates:
            if len(tokens) != len(path_segments):
                continue

            kwargs = {}
            matched = True
            for idx, (token_type, token_value) in enumerate(tokens):
                segment = path_segments[idx]

                if token_type == "literal":
                    if token_value != segment:
                        matched = False
                        break
                    continue

                if segment == "":
                    return 400, f"Invalid parameter format for '{token_value}' in route {template}"

                kwargs[token_value] = segment

            if not matched:
                continue

            is_valid_kwargs, error_message, signature = self._validate_handler_kwargs(func, kwargs)
            if not is_valid_kwargs:
                return 400, f"Invalid parameter format for route {template}: {error_message}"

            coerced_kwargs = {}
            for name, raw_value in kwargs.items():
                parameter = signature.parameters.get(name)
                expected_type = parameter.annotation if parameter else inspect._empty
                try:
                    coerced_kwargs[name] = self._coerce_value_to_type(raw_value, expected_type)
                except ValueError as e:
                    return 400, f"Invalid parameter format for '{name}' in route {template}: {e}"

            # Fallback coercion when no explicit type annotations are provided.
            if all(
                signature.parameters[name].annotation is inspect._empty
                for name in coerced_kwargs
                if name in signature.parameters
            ):
                for name in coerced_kwargs:
                    coerced_kwargs[name] = self._coerce_path_value(kwargs[name])

            try:
                return 200, func(**coerced_kwargs)
            except (ValueError, TypeError) as e:
                return 400, f"Invalid parameter format for route {template}: {e}"

        return None, None

    def get_registry(self):
        """Returns the current command registry of paths and functions.
        Returns:
            dict: The current route registry.
        """
        return self.registry

    def _apply_compact_command(self, cmd, speed, seq, timestamp):
        """
        Applies compact command packets sent from dashboard clients:
        /cmd/{cmd}/{speed}/{seq}/{timestamp}
        """
        if seq <= self._last_cmd_seq:
            return 200, "stale"

        self._last_cmd_seq = seq
        self._last_client_timestamp = timestamp
        self._touch_heartbeat()

        speed_handler = self.registry.get("/speed/{value}") or self.registry.get("/speed/")
        if speed_handler is not None:
            try:
                speed_handler(speed)
            except Exception as e:
                return 400, f"speed error: {e}"

        if cmd == "heartbeat":
            return 200, "heartbeat"

        command_path_map = {
            "forward": "/forward",
            "backward": "/backward",
            "left": "/left",
            "right": "/right",
            "stop": "/stop",
            "lights_toggle": "/lights/toggle",
            "camera_toggle": "/camera/toggle",
            "speed": None,
        }
        mapped_path = command_path_map.get(cmd)
        if mapped_path is None and cmd != "speed":
            return 400, f"unknown cmd: {cmd}"
        if mapped_path is None:
            return 200, "speed"

        handler = self.registry.get(mapped_path)
        if handler is None:
            return 404, f"missing route: {mapped_path}"

        try:
            return 200, handler()
        except Exception as e:
            return 500, f"cmd error: {e}"

    def handle_path(self, path):
        """
        Interpret the HTTP path using a registry of predefined commands mapped to paths.
        Args:
            path (str): The HTTP path requested.
        Returns:
            tuple: (status_code, response_body)
        """

        # 1. Normalize path (strip query strings)
        if "?" in path:
            path, _ = path.split("?", 1)

        compact_prefix = "/cmd/"
        if path.startswith(compact_prefix):
            segments = self._split_path_segments(path)
            if len(segments) != 5:
                return 400, "compact command format: /cmd/{cmd}/{speed}/{seq}/{timestamp}"
            _, cmd, speed_value, seq_value, timestamp_value = segments
            try:
                speed = int(speed_value)
                seq = int(seq_value)
                timestamp = int(timestamp_value)
            except ValueError:
                return 400, "compact command payload must be integers for speed/seq/timestamp"
            return self._apply_compact_command(cmd, speed, seq, timestamp)

        if path == "/heartbeat":
            self._touch_heartbeat()
            return 200, "heartbeat"

        if path == "/status":
            uptime_ms = int(time.monotonic() * 1000)
            return 200, (
                '{"ok":true,'
                f'"deadman_timeout_ms":{int(self.deadman_timeout_ms)},'
                f'"last_cmd_seq":{int(self._last_cmd_seq)},'
                f'"last_client_timestamp":{int(self._last_client_timestamp)},'
                f'"uptime_ms":{uptime_ms}'
                '}'
            )
        
        # 2. Check for exact matches in the registry
        if path in self.registry:
            return 200, self.registry[path]()

        # 3. Check template routes with path parameters
        template_status, template_result = self._match_template_route(path)
        if template_status is not None:
            return template_status, template_result

        # 4. Handle 'Prefix' matches (like your /sound/ example)
        for prefix, func in self.registry.items():
            if prefix.endswith("/") and path.startswith(prefix):
                # Pass the 'remainder' of the path as an argument to the function
                arg = path[len(prefix):]
                return 200, func(arg)

        return 200, f"Unknown path: {path}"

    # =======================
    # Full functionality loop:
    # =======================

    def listen_http_wireless(self):
        """
        Main loop: listens for HTTP requests over WiFi AP
        and handles them.

        Warning: This is a blocking function that runs indefinitely. The way to stop it is to reset or power off the board.
        The outputs are function calls from the registered functions, which are defined by register_route().
        """

        ap_ip = self.start_wifi_ap()
        time.sleep(1)  # give AP a moment to settle
        server = self.start_http_server(ap_ip)

        while self.keepAlive:
            try:
                print("Waiting for connection...")
                conn, addr = server.accept()
                print("Client connected from", addr)

                request = conn.recv(1024)
                if not request:
                    print("Empty request.")
                    conn.close()
                    continue

                try:
                    request_str = request.decode("utf-8")
                except UnicodeError:
                    print("Failed to decode request.")
                    self.send_http_response(conn, 400, "Bad request encoding")
                    conn.close()
                    continue

                method, path, status_code, error_message = self._parse_request_line(request_str)
                if status_code is not None:
                    self.send_http_response(conn, status_code, error_message)
                    conn.close()
                    continue

                # Handle the path
                status_code, result_text = self.handle_path(path)
                self.send_http_response(conn, status_code, result_text)

                conn.close()

            except OSError as e:
                self._check_deadman()
                # Occasional WiFi/socket weirdness
                if "timed out" in str(e).lower():
                    continue
                print("Socket error:", e)
                try:
                    conn.close()
                except Exception:
                    pass
                time.sleep(0.1)
            except Exception as e:
                self._check_deadman()
                print("General error:", e)
                try:
                    conn.close()
                except Exception:
                    pass
                time.sleep(0.1)
                # note: shutdown sometimes takes up to 15 seconds.
