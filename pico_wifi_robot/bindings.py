"""Keyboard binding manager decoupled from HTTP transport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

from .controls import ButtonControl


@dataclass
class ControlAction:
    event: str
    key: str
    control: ButtonControl
    path: str


class KeyboardBindingManager:
    """Map key press/release events to control actions."""

    def __init__(
        self,
        controls: Iterable[ButtonControl],
        on_action: Optional[Callable[[ControlAction], object]] = None,
    ) -> None:
        self._controls_by_key: Dict[str, ButtonControl] = {}
        self._active_keys: set[str] = set()
        self._on_action = on_action

        for control in controls:
            if control.key_binding:
                self._controls_by_key[control.key_binding.lower()] = control

    def handle_key_press(self, key: str) -> Optional[ControlAction]:
        normalized = key.lower()
        control = self._controls_by_key.get(normalized)
        if control is None or normalized in self._active_keys:
            return None

        self._active_keys.add(normalized)
        action = ControlAction(
            event="press",
            key=normalized,
            control=control,
            path=control.build_path(),
        )
        self._dispatch(action)
        return action

    def handle_key_release(self, key: str) -> Optional[ControlAction]:
        normalized = key.lower()
        control = self._controls_by_key.get(normalized)
        if control is None:
            return None

        self._active_keys.discard(normalized)
        action = ControlAction(
            event="release",
            key=normalized,
            control=control,
            path=control.build_path(),
        )
        self._dispatch(action)
        return action

    def _dispatch(self, action: ControlAction) -> None:
        if self._on_action is not None:
            self._on_action(action)
