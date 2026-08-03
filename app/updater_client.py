from __future__ import annotations

import http.client
import json
import socket
from typing import Any


class UpdaterUnavailable(RuntimeError):
    pass


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float):
        super().__init__("updater.local", timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self.timeout)
        try:
            connection.connect(self.socket_path)
        except OSError as exc:
            connection.close()
            raise UpdaterUnavailable(
                "Updater is not installed or is unavailable on this VPS"
            ) from exc
        self.sock = connection


def request(
    socket_path: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
    control_token: str = "",
) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else None
    headers = {"Host": "updater.local", "Accept": "application/json"}
    if control_token:
        headers["X-Updater-Token"] = control_token
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    connection = UnixHTTPConnection(socket_path, timeout)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        content = response.read(4 * 1024 * 1024 + 1)
    finally:
        connection.close()
    if len(content) > 4 * 1024 * 1024:
        raise RuntimeError("Updater response exceeds 4 MB")
    try:
        result = json.loads(content.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Updater returned invalid JSON") from exc
    if not 200 <= response.status < 300:
        raise RuntimeError(str(result.get("error") or f"Updater returned HTTP {response.status}"))
    return result


def status(socket_path: str) -> dict[str, Any]:
    try:
        return {
            "installed": True,
            "available": True,
            **request(socket_path, "GET", "/v1/health"),
        }
    except UpdaterUnavailable as exc:
        return {
            "installed": False,
            "available": False,
            "status": "unavailable",
            "service": "updater",
            "message": str(exc),
        }
