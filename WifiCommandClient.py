# Jack Tommaney, Nov 2025 / Jan 2026
"""
WifiCommandClient.py compatibility wrapper around the pico_wifi_robot package.
"""

import threading

from pynput import keyboard

from pico_wifi_robot import RobotClient, compute_wasd_command

# ===========================
# CONFIG
# ===========================

ROBOT_BASE_URL = "http://192.168.4.1"

# ===========================
# State & helpers
# ===========================

active_keys = set()
current_cmd = None
lock = threading.Lock()
client = RobotClient(ROBOT_BASE_URL)


def send_command(cmd: str):
    """Send a movement command to the robot if it changed."""
    global current_cmd
    with lock:
        if cmd == current_cmd:
            return
        current_cmd = cmd

    try:
        response = client.send_path(cmd)
        print(f"Sent {cmd} -> {response.status_code} {response.text}")
    except Exception as exc:
        print(f"Error sending {cmd}: {exc}")


def compute_command() -> str:
    """Backwards-compatible command computation for active WASD keys."""
    return compute_wasd_command(active_keys)


def on_press(key):
    global active_keys

    if key == keyboard.Key.space:
        active_keys.clear()
        send_command("stop")
        print("[SPACE] Panic stop")
        return

    try:
        k = key.char.lower()
    except AttributeError:
        return

    if k in ["w", "a", "s", "d"] and k not in active_keys:
        active_keys.add(k)
        send_command(compute_command())


def on_release(key):
    global active_keys

    if key == keyboard.Key.esc:
        print("ESC pressed, stopping and exiting...")
        send_command("stop")
        return False

    try:
        k = key.char.lower()
    except AttributeError:
        return

    if k in ["w", "a", "s", "d"]:
        active_keys.discard(k)
        send_command(compute_command())


if __name__ == "__main__":
    print("WASD to drive the robot.")
    print("SPACE = panic stop, ESC = quit.")
    send_command("stop")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()
