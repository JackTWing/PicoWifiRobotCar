"""Legacy WASD controller helpers."""

from __future__ import annotations

from typing import Set


def compute_wasd_command(active_keys: Set[str]) -> str:
    """Preserve legacy movement logic for single-key WASD control."""
    w = "w" in active_keys
    a = "a" in active_keys
    s = "s" in active_keys
    d = "d" in active_keys

    if w and not s and not a and not d:
        return "forward"
    if s and not w and not a and not d:
        return "back"
    if a and not d and not w and not s:
        return "left"
    if d and not a and not w and not s:
        return "right"
    return "stop"
