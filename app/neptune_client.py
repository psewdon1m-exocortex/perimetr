from __future__ import annotations

import http.client
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .updater_client import UnixHTTPConnection, UpdaterUnavailable


def request(
    socket_path: str,
    project_id: str,
    control_token_file: str,
    method: str,
    route: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    token_path = Path(control_token_file)
    if not token_path.is_file():
        raise UpdaterUnavailable("Neptune control token is not configured")
    token = token_path.read_text(encoding="utf-8").strip()
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else None
    headers = {"Host": "neptune.local", "Accept": "application/json", "X-Neptune-Token": token}
    if body is not None:
        headers.update({"Content-Type": "application/json", "Content-Length": str(len(body))})
    connection = UnixHTTPConnection(socket_path, 30)
    try:
        connection.request(method, f"/v1/projects/{quote(project_id, safe='')}{route}", body=body, headers=headers)
        response = connection.getresponse()
        content = response.read(1024 * 1024 + 1)
    except (OSError, http.client.HTTPException) as exc:
        raise UpdaterUnavailable("Neptune is not installed or is unavailable on this VPS") from exc
    finally:
        connection.close()
    if len(content) > 1024 * 1024:
        raise RuntimeError("Neptune response exceeds 1 MB")
    try:
        result = json.loads(content.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Neptune returned invalid JSON") from exc
    if not 200 <= response.status < 300:
        raise RuntimeError(str(result.get("error") or f"Neptune returned HTTP {response.status}"))
    return result
