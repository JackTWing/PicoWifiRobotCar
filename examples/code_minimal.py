"""Minimal usage example for WifiCommandServer."""

from wifi_command_server import WifiCommandServer


server = WifiCommandServer(ssid="MyRobot", password="12345678", title="My Robot")


@server.command("forward", motion=True)
def forward():
    print("forward")


@server.command("stop")
def stop():
    print("stop")


@server.slider("speed", min=0, max=100, default=50)
def set_speed(value):
    print("speed", value)


@server.telemetry("battery")
def battery_voltage():
    return 4.0


server.set_emergency_stop(stop)
server.run()
