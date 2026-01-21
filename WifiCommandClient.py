# Jack Tommaney, Nov 2025 / Jan 2026
"""
WifiCommandClient.py contains functions for 
interactions between the computer and a 
CircuitPython Pico with a wifi module.
"""

# Tested on a Windows 11 Home PC with Python v 3.11.4
# Runs its own WiFi access point and HTTP command server (insecure)

import requests
from pynput import keyboard
import threading

# ===========================
# CONFIG
# ===========================

# Change this to the Pico's IP address printed in the REPL if this doesn't work
ROBOT_BASE_URL = "http://192.168.4.1"

# ===========================
# State & helpers
# ===========================

active_keys = set()   # currently pressed movement keys
current_cmd = None
lock = threading.Lock()


def send_command(cmd: str):
    """Send a movement command to the robot if it changed."""
    global current_cmd
    with lock:
        if cmd == current_cmd:
            return  # no need to spam the same command
        current_cmd = cmd

    try:
        url = f"{ROBOT_BASE_URL}/{cmd}"
        r = requests.get(url, timeout=0.5)
        print(f"Sent {cmd} -> {r.status_code} {r.text}")
    except Exception as e:
        print(f"Error sending {cmd}: {e}")


def compute_command() -> str:
    """Figure out which command to send, based on active WASD keys."""
    w = 'w' in active_keys
    a = 'a' in active_keys
    s = 's' in active_keys
    d = 'd' in active_keys

    # Simple priority scheme:
    # - If exactly one key is pressed, do that move.
    # - Any combo or no keys -> stop (you can get fancier later).
    if w and not s and not a and not d:
        return "forward"
    if s and not w and not a and not d:
        return "back"
    if a and not d and not w and not s:
        return "left"
    if d and not a and not w and not s:
        return "right"

    # Multiple keys or none = stop
    return "stop"


def on_press(key):
    global active_keys

    # Space bar = panic stop
    if key == keyboard.Key.space:
        active_keys.clear()
        send_command("stop")
        print("[SPACE] Panic stop")
        return

    try:
        k = key.char.lower()
    except AttributeError:
        # Non-character keys (shift, ctrl, arrows, etc.)
        return

    if k in ['w', 'a', 's', 'd']:
        if k not in active_keys:
            active_keys.add(k)
            cmd = compute_command()
            send_command(cmd)


def on_release(key):
    global active_keys

    # ESC = quit program (and stop robot)
    if key == keyboard.Key.esc:
        print("ESC pressed, stopping and exiting...")
        send_command("stop")
        return False  # stops the listener

    try:
        k = key.char.lower()
    except AttributeError:
        return

    if k in ['w', 'a', 's', 'd']:
        if k in active_keys:
            active_keys.remove(k)
        cmd = compute_command()
        send_command(cmd)


if __name__ == "__main__":
    print("WASD to drive the robot.")
    print("SPACE = panic stop, ESC = quit.")
    # Make sure we start in a safe state
    send_command("stop")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()