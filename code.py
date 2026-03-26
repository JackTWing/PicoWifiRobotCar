"""Example runtime entrypoint for Pico W robot car.

This keeps robot logic separate from HTTP/dashboard framework logic by using
WifiCommandServer from lib/.
"""

import board
import pwmio
from adafruit_motor import servo

from wifi_command_server import WifiCommandServer


# ----- Robot hardware setup -----
pwm_left = pwmio.PWMOut(board.GP15, frequency=50)
pwm_right = pwmio.PWMOut(board.GP16, frequency=50)
left_servo = servo.ContinuousServo(pwm_left)
right_servo = servo.ContinuousServo(pwm_right)

left_adjust = 0.075
right_adjust = 0.075
right_reverse = -1.0
left_reverse = 1.0

speed_percent = 50


def _scale(value):
    return max(-1.0, min(1.0, value * (speed_percent / 100.0)))


def set_wheels(left, right):
    left_servo.throttle = max(-1.0, min(1.0, (left + left_adjust) * left_reverse))
    right_servo.throttle = max(-1.0, min(1.0, (right + right_adjust) * right_reverse))


def stop_motion():
    set_wheels(0.0, 0.0)


def forward():
    set_wheels(_scale(-1.0), _scale(-1.0))


def reverse():
    set_wheels(_scale(1.0), _scale(1.0))


def left():
    set_wheels(_scale(-0.5), _scale(0.5))


def right():
    set_wheels(_scale(0.5), _scale(-0.5))


def set_speed(percent):
    global speed_percent
    speed_percent = int(max(0, min(100, percent)))


def fake_battery():
    # Replace with ADC read if battery sensing is wired.
    return 3.9


# ----- Generic WiFi command server setup -----
server = WifiCommandServer(
    ssid="RobotCar",
    password="12345678",
    title="Pico Robot Car",
    command_timeout_ms=1200,
)


@server.command("forward", label="Forward", motion=True, on_release=stop_motion)
def _cmd_forward():
    forward()


@server.command("reverse", label="Reverse", motion=True, on_release=stop_motion)
def _cmd_reverse():
    reverse()


@server.command("left", label="Left", motion=True, on_release=stop_motion)
def _cmd_left():
    left()


@server.command("right", label="Right", motion=True, on_release=stop_motion)
def _cmd_right():
    right()


@server.command("stop", label="Stop")
def _cmd_stop():
    stop_motion()


@server.slider("speed", min=0, max=100, default=50, label="Speed", step=1)
def _slider_speed(value):
    set_speed(value)


@server.telemetry("battery", label="Battery (V)")
def _tm_battery():
    return fake_battery()


@server.telemetry("speed", label="Speed (%)")
def _tm_speed():
    return speed_percent


server.set_emergency_stop(stop_motion)
server.run()
