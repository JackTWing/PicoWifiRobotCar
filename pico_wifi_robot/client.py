"""HTTP client utilities for the Pico WiFi robot."""

from __future__ import annotations

from urllib.parse import quote

import requests


class RobotClient:
    """Simple HTTP client for sending commands to a robot control server."""

    def __init__(self, base_url: str, timeout: float = 0.5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def send_path(self, path: str) -> requests.Response:
        """Send a GET request to a path like ``/forward`` or ``forward``."""
        normalized = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{normalized}"
        return requests.get(url, timeout=self.timeout)

    def send_segments(self, *segments: object) -> requests.Response:
        """Build a path from segments and send it as a GET request."""
        encoded = [quote(str(segment).strip("/"), safe="") for segment in segments]
        joined = "/".join(part for part in encoded if part)
        return self.send_path(f"/{joined}")
