Jack T's Pico WiFi Robot Car Miniproject!

To use the system:

1. Change the hardcoded name and password to your choices.
2. Connect to the car's WiFi name.
3. Run the script - you now have a robot running over an HTTP server.

Built for Physical Computing with Prof. Gallaugher at BC.

## Python client package layout

The host-side controls are now organized in `pico_wifi_robot/`:

- `client.py`: `RobotClient(base_url)` transport with `send_path()` and `send_segments()`.
- `controls.py`: declarative control models (`ButtonControl`, `SliderControl`).
- `bindings.py`: keyboard binding manager independent from HTTP transport.
- `config.py`: JSON load/save helpers for user-defined controls.
- `legacy.py`: compatibility helpers for existing WASD behavior.

Legacy/deprecated snapshots:

- `WifiCommandClient.py`
- `WifiCarController.py.old` (deprecated snapshot)

Both wrappers call into the new package APIs so old workflows continue to work.

## JSON config format

`pico_wifi_robot.config.load_controls()` expects:

```json
{
  "controls": [
    {
      "type": "button",
      "label": "Forward",
      "target_path_template": "/forward",
      "key_binding": "w",
      "value_transform": null
    },
    {
      "type": "slider",
      "label": "Speed",
      "target_path_template": "/speed/{value}",
      "value_transform": "float"
    }
  ]
}
```

Supported `value_transform` names: `identity`, `int`, `float`.
