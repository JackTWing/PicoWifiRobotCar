"""Load/save JSON control configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Union

from .controls import ButtonControl, SliderControl

Control = Union[ButtonControl, SliderControl]


def _identity(value: object) -> object:
    return value


def _as_int(value: object) -> int:
    return int(value)


def _as_float(value: object) -> float:
    return float(value)


TRANSFORMS: Dict[str, Callable[[object], object]] = {
    "identity": _identity,
    "int": _as_int,
    "float": _as_float,
}

REVERSE_TRANSFORMS = {func: name for name, func in TRANSFORMS.items()}


def load_controls(path: Union[str, Path]) -> List[Control]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    controls: List[Control] = []

    for item in data.get("controls", []):
        control_type = item["type"]
        transform_name = item.get("value_transform")
        transform = TRANSFORMS.get(transform_name) if transform_name else None

        common = {
            "label": item["label"],
            "target_path_template": item["target_path_template"],
            "key_binding": item.get("key_binding"),
            "value_transform": transform,
        }

        if control_type == "button":
            controls.append(ButtonControl(**common))
        elif control_type == "slider":
            controls.append(SliderControl(**common))
        else:
            raise ValueError(f"Unknown control type: {control_type}")

    return controls


def save_controls(path: Union[str, Path], controls: Sequence[Control]) -> None:
    payload = {"controls": []}
    for control in controls:
        if isinstance(control, ButtonControl):
            control_type = "button"
        elif isinstance(control, SliderControl):
            control_type = "slider"
        else:
            raise TypeError(f"Unsupported control object: {type(control)!r}")

        transform_name = None
        if control.value_transform is not None:
            transform_name = REVERSE_TRANSFORMS.get(control.value_transform)
            if transform_name is None:
                raise ValueError(
                    f"Control '{control.label}' uses a non-serializable transform. "
                    "Use one of: identity, int, float."
                )

        payload["controls"].append(
            {
                "type": control_type,
                "label": control.label,
                "target_path_template": control.target_path_template,
                "key_binding": control.key_binding,
                "value_transform": transform_name,
            }
        )

    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
