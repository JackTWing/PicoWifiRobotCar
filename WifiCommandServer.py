# Jack Tommaney, Nov 2025 / Jan 2026
"""
WifiProtocolAPI.py contains functions for 
interactions between a CircuitPython Pico 
with a wifi module and a connected computer.
"""

# Tested on a Raspberry Pi Pico 2 W with CircuitPython v 10.0.0
# Runs its own WiFi access point and HTTP command server (insecure)

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

    def __init__(self, registry):
        self.registry = registry
        self.keepAlive = True

    def start(self):
        self.listen_http_wireless(self.registry)

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
        server.settimeout(None)  # blocking accept is fine here for most robotics applications

        print(f"HTTP server listening on http://{ap_ip}:{PORT}/")
        return server
    
    def stop_http_server(self):
        """Stops the HTTP server by setting keepAlive to False in the main server loop."""
        self.keepAlive = False


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

    # Jury-rigged DIY POST response handler for plaintext
    def do_POST_RESPONSE(self, response_text):
            # Send the response back to the client
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(response_text.encode())

    def register_route(self, path, func):
        """Utility for developers to add their own commands.
        Args:
            registry (dict): The route registry to add to.
            path (str): The HTTP path to register (e.g., "/mycommand").
            func (callable): The function to call when this path is requested.
        """
        self.registry[path] = func

    def get_registry(self):
        """Returns the current command registry of paths and functions.
        Returns:
            dict: The current route registry.
        """
        return self.registry

    def handle_path(self, path):
        """
        Interpret the HTTP path using a registry of predefined commands mapped to paths.
        Args:
            path (str): The HTTP path requested.
        Returns:
            str: A short string describing the result.
        """

        # 1. Normalize path (strip query strings)
        if "?" in path:
            path, _ = path.split("?", 1)
        
        # 2. Check for exact matches in the registry
        if path in self.registry:
            return self.registry[path]()

        # 3. Handle 'Prefix' matches (like your /sound/ example)
        for prefix, func in self.registry.items():
            if prefix.endswith("/") and path.startswith(prefix):
                # Pass the 'remainder' of the path as an argument to the function
                arg = path[len(prefix):]
                return func(arg)

        return f"Unknown path: {path}"

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

                # First line: "GET /path HTTP/1.1"
                request_line = request_str.split("\r\n")[0]
                print("Request line:", request_line)

                parts = request_line.split(" ")
                if len(parts) < 2:
                    self.send_http_response(conn, 400, "Malformed request")
                    conn.close()
                    continue

                method = parts[0]
                path = parts[1]

                if method != "GET":
                    self.send_http_response(conn, 405, "Only GET supported at this time")
                    conn.close()
                    continue

                # Handle the path
                result_text = self.handle_path(path, self.registry)
                self.send_http_response(conn, 200, result_text)

                conn.close()

            except OSError as e:
                # Occasional WiFi/socket weirdness
                print("Socket error:", e)
                try:
                    conn.close()
                except Exception:
                    pass
                time.sleep(0.1)
            except Exception as e:
                print("General error:", e)
                try:
                    conn.close()
                except Exception:
                    pass
                time.sleep(0.1)
                # note: shutdown sometimes takes up to 15 seconds.