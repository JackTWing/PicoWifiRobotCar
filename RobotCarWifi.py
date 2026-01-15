# Jack T - Robot Car over HTTP AP
# Raspberry Pi Pico 2 W + CircuitPython
# Runs its own WiFi access point and HTTP command server

import board, time, pwmio
import wifi, socketpool
from adafruit_motor import servo

# =======================
# Servo setup
# =======================

# Setup servos on GP15 (left) and GP16 (right)
pwm_left = pwmio.PWMOut(board.GP15, frequency=50)
pwm_right = pwmio.PWMOut(board.GP16, frequency=50)
servo_left = servo.ContinuousServo(pwm_left)
servo_right = servo.ContinuousServo(pwm_right)

# Trim adjustments so the car actually drives straight-ish
left_adjust = 0.075
right_adjust = 0.075  # tweak as needed

def move_servo(left_throttle, right_throttle):
    """Set left/right continuous servo throttles with clamping + direction flips."""
    right_reverse = -1.0   # invert as needed for your wiring
    left_reverse = 1.0

    # Left
    throttle = (left_throttle + left_adjust) * left_reverse
    throttle = max(min(throttle, 1.0), -1.0)
    print("left_throttle:", throttle)
    servo_left.throttle = throttle

    # Right
    throttle = (right_throttle + right_adjust) * right_reverse
    throttle = max(min(throttle, 1.0), -1.0)
    print("right_throttle:", throttle)
    servo_right.throttle = throttle


def stop():
    move_servo(0.0, 0.0)


# =======================
# WiFi AP setup
# =======================

AP_SSID = "JTRobotCar"
AP_PASSWORD = "JTPhysCompAswesomeness"  # must be at least 8 chars

print("Starting WiFi access point...")
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

# =======================
# HTTP server setup
# =======================

pool = socketpool.SocketPool(wifi.radio)
server = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
server.setsockopt(pool.SOL_SOCKET, pool.SO_REUSEADDR, 1)

HOST = "0.0.0.0"  # listen on all interfaces
PORT = 80

server.bind((HOST, PORT))
server.listen(1)
server.settimeout(None)  # blocking accept is fine here

print(f"HTTP robot server listening on http://{ap_ip}:{PORT}/")


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


def handle_path(path):
    """
    Interpret the HTTP path and perform the corresponding action.
    Returns a short string describing the result.
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
        # TODO: hook this into your audio code if you want
        print("Sound requested:", sound_name)
        # play_mp3(sound_name)  # if you re-add your MP3 code
        return f"sound:{sound_name}"

    # Unknown path
    return f"Unknown path: {path}"


# =======================
# Main loop
# =======================

while True:
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