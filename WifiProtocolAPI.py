# Jack Tommaney, Nov 2025 / Jan 2026
"""
WifiProtocolAPI.py contains functions for 
interactions between a CircuitPython Pico 
with a wifi module and a connected computer.
"""
# ======================
# board functions:
# ======================

# Tested on a Raspberry Pi Pico 2 W with CircuitPython v 10.0.0
# Runs its own WiFi access point and HTTP command server (insecure)

import board, time, wifi, socketpool

# =======================
# WiFi AP setup
# =======================

def start_wifi_ap(network_name="Pi-Pico-Wifi", password="password"):
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

def start_http_server(ap_ip):
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


def send_http_response(conn, status_code=200, body="OK"):
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

route_registry = {}

def register_route(path, func):
    """Utility for developers to add their own commands.
    Args:
        path (str): The HTTP path to register (e.g., "/mycommand").
        func (callable): The function to call when this path is requested.
    """
    route_registry[path] = func

def handle_path(path, registry=route_registry):
    """
    Interpret the HTTP path using a registry of predefined commands mapped to paths.
    Args:
        path (str): The HTTP path requested.
        registry (dict): A mapping of paths to functions.
    Returns:
        str: A short string describing the result.
    """

    # 1. Normalize path (strip query strings)
    if "?" in path:
        path, _ = path.split("?", 1)
    
    # 2. Check for exact matches in the registry
    if path in registry:
        return registry[path]()

    # 3. Handle 'Prefix' matches (like your /sound/ example)
    for prefix, func in registry.items():
        if prefix.endswith("/") and path.startswith(prefix):
            # Pass the 'remainder' of the path as an argument to the function
            arg = path[len(prefix):]
            return func(arg)

    return f"Unknown path: {path}"

def handle_path_old(path):
    """
    Interpret the HTTP path and perform the corresponding action.
    Returns a short string describing the result.
    This is the old hardcoded version before route_registry was added.
    """

    # Normalize by stripping query strings if present
    if "?" in path:
        path, _query = path.split("?", 1)

    print("Requested path:", path)

    # Root: show basic help
    if path == "/" or path == "":
        return (
            "Robot Car HTTP Control (AP mode)\n"
            "Commands:\n"
            "  /forward\n"
            "  /back\n"
            "  /left\n"
            "  /right\n"
            "  /stop\n"
            "  /sound/<name>\n"
        )

    # Movement commands
    if path == "/stop":
        stop()
        return "stop"

    elif path == "/forward":
        move_servo(-1.0, -1.0)
        return "forward"

    elif path == "/back":
        move_servo(1.0, 1.0)
        return "back"

    elif path == "/left":
        move_servo(-0.5, 0.5)
        return "left"

    elif path == "/right":
        move_servo(0.5, -0.5)
        return "right"

    # Sounds: /sound/<something>
    elif path.startswith("/sound/"):
        sound_name = path[len("/sound/"):]
        # TODO: hook this into audio code if wanted
        print("Sound requested:", sound_name)
        # play_mp3(sound_name)  # if re-adding MP3 code
        return f"sound:{sound_name}"

    # Unknown path
    return f"Unknown path: {path}"



def listen_http_wireless():
    """
    Main loop: listens for HTTP requests over WiFi AP
    and handles them.
    """

    ap_ip = start_wifi_ap()
    server = start_http_server(ap_ip)

    keepAlive = True

    while keepAlive:
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
                send_http_response(conn, 400, "Bad request encoding")
                conn.close()
                continue

            # First line: "GET /path HTTP/1.1"
            request_line = request_str.split("\r\n")[0]
            print("Request line:", request_line)

            parts = request_line.split(" ")
            if len(parts) < 2:
                send_http_response(conn, 400, "Malformed request")
                conn.close()
                continue

            method = parts[0]
            path = parts[1]

            if method != "GET":
                send_http_response(conn, 405, "Only GET supported")
                conn.close()
                continue

            # Handle the path
            result_text = handle_path(path)
            send_http_response(conn, 200, result_text)

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