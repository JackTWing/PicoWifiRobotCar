"""Backwards-compatible import shim.

Prefer: from wifi_command_server import WifiCommandServer
"""

from wifi_command_server import WifiCommandServer

__all__ = ["WifiCommandServer"]
