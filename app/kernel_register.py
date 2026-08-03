from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .pod_artifacts import pod_discovery_url


SNAPSHOT_SCHEMA = "exocortex.register.snapshot.v1"
REVISION_PATTERN = re.compile(r"^register-[A-Za-z0-9-]+$")


class KernelRegisterError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _verify_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise KernelRegisterError("unsupported Kernel Register schema")
    revision = snapshot.get("revision")
    if not isinstance(revision, str) or not REVISION_PATTERN.fullmatch(revision):
        raise KernelRegisterError("invalid Kernel Register revision")
    values = snapshot.get("values")
    if not isinstance(values, dict):
        raise KernelRegisterError("Kernel Register values must be an object")
    expected = "sha256:" + hashlib.sha256(
        _canonical_json({"values": values}).encode("utf-8")
    ).hexdigest()
    if snapshot.get("checksum") != expected:
        raise KernelRegisterError("Kernel Register checksum mismatch")
    return snapshot


def _read_cache(path: Path) -> dict[str, Any]:
    try:
        return _verify_snapshot(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as exc:
        raise KernelRegisterError("no valid Kernel Register last-known-good cache") from exc


def _write_cache(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    body = _canonical_json(snapshot) + "\n"
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        _read_cache(temporary)
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        if temporary.exists():
            temporary.unlink()


def _registered_kernel_url(snapshot: dict[str, Any], bootstrap_url: str) -> str:
    parsed = urlparse(bootstrap_url)
    if parsed.scheme not in {"http", "https"}:
        raise KernelRegisterError("KERNEL_URL must use http or https")
    values = snapshot["values"]
    sni = _required_string(values, "services.kernel.sni")
    port = _required_port(values, "services.kernel.port")
    check = urlparse(f"http://{sni}")
    if not check.hostname or check.port is not None or check.path not in {"", "/"}:
        raise KernelRegisterError("Kernel Register services.kernel.sni is invalid")
    host = f"[{sni}]" if ":" in sni and not sni.startswith("[") else sni
    return parsed._replace(
        netloc=f"{host}:{port}",
        path="",
        params="",
        query="",
        fragment="",
    ).geturl()


def load_snapshot(
    *,
    kernel_url: str,
    service_token: str,
    cache_path: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    cache = Path(cache_path)
    if not kernel_url and not service_token:
        return {}
    if not kernel_url or not service_token:
        raise KernelRegisterError("KERNEL_URL and KERNEL_SERVICE_TOKEN must be configured together")

    cached: dict[str, Any] | None = None
    try:
        cached = _read_cache(cache)
    except KernelRegisterError:
        pass
    headers = {
        "Authorization": f"Bearer {service_token}",
        "Accept": "application/vnd.exocortex.register+json; version=1",
    }
    if cached:
        headers["If-None-Match"] = f'"{cached["revision"]}"'
    urls = [kernel_url.rstrip("/")]
    if cached:
        try:
            registered_url = _registered_kernel_url(cached, kernel_url).rstrip("/")
            if registered_url != urls[0]:
                urls.insert(0, registered_url)
        except KernelRegisterError:
            pass
    last_error: Exception | None = None
    for remote_url in urls:
        request = Request(
            f"{remote_url}/api/v1/register/snapshot",
            headers=headers,
            method="GET",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read(3 * 1024 * 1024 + 1)
                if len(body) > 3 * 1024 * 1024:
                    raise KernelRegisterError("Kernel Register response is too large")
                snapshot = _verify_snapshot(json.loads(body.decode("utf-8")))
                _write_cache(cache, snapshot)
                return snapshot
        except HTTPError as remote_error:
            if remote_error.code == 304 and cached:
                return cached
            last_error = remote_error
        except (
            URLError,
            TimeoutError,
            OSError,
            ValueError,
            KernelRegisterError,
        ) as remote_error:
            last_error = remote_error
    if cached:
        return cached
    raise KernelRegisterError(
        "Kernel unavailable and no valid Register last-known-good cache exists"
    ) from last_error


def _resolve(values: dict[str, Any], key: str) -> Any:
    cursor: Any = values
    for part in key.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def _required_string(values: dict[str, Any], key: str) -> str:
    value = _resolve(values, key)
    if not isinstance(value, str) or not value.strip():
        raise KernelRegisterError(f"Kernel Register is missing required key {key}")
    return value.strip()


def _required_url(values: dict[str, Any], key: str) -> str:
    value = _required_string(values, key)
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise KernelRegisterError(f"Kernel Register key {key} must be a valid HTTPS URL")
    return value


def _positive_int(values: dict[str, Any], key: str, current: int, minimum: int, maximum: int) -> int:
    value = _resolve(values, key)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return current
    return parsed if minimum <= parsed <= maximum else current


def _required_port(values: dict[str, Any], key: str) -> int:
    value = _required_string(values, key)
    try:
        port = int(value)
    except ValueError as exc:
        raise KernelRegisterError(
            f"Kernel Register key {key} must be an integer port"
        ) from exc
    if not 1 <= port <= 65535:
        raise KernelRegisterError(
            f"Kernel Register key {key} must be between 1 and 65535"
        )
    return port


def apply_register(settings):
    snapshot = load_snapshot(
        kernel_url=settings.kernel_url,
        service_token=settings.kernel_service_token,
        cache_path=settings.kernel_cache_path,
        timeout_seconds=settings.kernel_timeout_sec,
    )
    if not snapshot:
        return settings
    values = snapshot["values"]

    settings.perimetr_repository_url = _required_url(
        values, "repositories.perimetr.url"
    )
    settings.perimetr_pod_repository_url = _required_url(
        values, "repositories.pod.url"
    )
    settings.perimetr_pod_update_manifest_url = pod_discovery_url(
        settings.perimetr_pod_repository_url
    )
    settings.perimetr_sni = _required_string(values, "services.perimetr.sni")
    settings.perimetr_service_port = _required_port(
        values, "services.perimetr.port"
    )
    parsed = urlparse(f"http://{settings.perimetr_sni}")
    if not parsed.hostname or parsed.path not in {"", "/"}:
        raise KernelRegisterError("Kernel Register services.perimetr.sni is invalid")
    host = (
        f"[{settings.perimetr_sni}]"
        if ":" in settings.perimetr_sni and not settings.perimetr_sni.startswith("[")
        else settings.perimetr_sni
    )
    public_port = (
        "" if settings.perimetr_service_port == 443
        else f":{settings.perimetr_service_port}"
    )
    settings.perimetr_public_url = f"https://{host}{public_port}"
    settings.kernel_refresh_sec = _positive_int(
        values,
        "intervals.kernel.refresh_sec",
        settings.kernel_refresh_sec,
        5,
        3600,
    )
    settings.kernel_register_revision = snapshot["revision"]
    return settings
