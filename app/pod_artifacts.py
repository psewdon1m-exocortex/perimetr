from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
import time
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


POD_CACHE_SCHEMA = "perimetr.pod-artifact-cache.v1"
MAX_MANIFEST_BYTES = 256 * 1024
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z.-]+))?$"
)
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_artifact_lock = threading.Lock()


class PodArtifactError(RuntimeError):
    pass


@dataclass(frozen=True)
class PodArtifact:
    version: str
    sha256: str
    path: Path
    source: str
    manifest: dict[str, Any]
    refresh_error: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def pod_discovery_url(repository_url: str) -> str:
    candidate = str(repository_url or "").strip().rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment:
        raise PodArtifactError("repositories.pod.url must be a valid HTTPS repository URL")
    if candidate.endswith(".git"):
        candidate = candidate[:-4]
    return f"{candidate}/releases/download/pod-current/pod-update.json"


def _semver(value: str) -> tuple[int, int, int, tuple[tuple[int, int | str], ...]]:
    match = SEMVER_PATTERN.fullmatch(str(value or ""))
    if not match:
        raise PodArtifactError(f"invalid semantic version: {value}")
    prerelease = match.group(4)
    if prerelease is None:
        suffix = ((2, ""),)
    else:
        values: list[tuple[int, int | str]] = []
        for item in prerelease.split("."):
            values.append((0, int(item)) if item.isdigit() else (1, item.lower()))
        suffix = tuple(values)
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), suffix


def compare_versions(left: str, right: str) -> int:
    left_value = _semver(left)
    right_value = _semver(right)
    return (left_value > right_value) - (left_value < right_value)


def _verify_manifest(
    manifest: dict[str, Any],
    public_key_path: Path,
    *,
    perimetr_version: str,
) -> dict[str, Any]:
    required = ("version", "channel", "url", "sha256", "signature")
    missing = [field for field in required if not manifest.get(field)]
    if missing:
        raise PodArtifactError(f"Pod update manifest is missing: {', '.join(missing)}")
    schema_version = manifest.get("schema_version")
    if schema_version not in {None, 1, 2}:
        raise PodArtifactError("unsupported Pod update manifest schema")
    if manifest.get("product") not in {None, "pod"}:
        raise PodArtifactError("Pod update manifest product mismatch")
    if manifest["channel"] != "stable":
        raise PodArtifactError("Pod update manifest channel must be stable")
    _semver(str(manifest["version"]))
    if "-" in str(manifest["version"]):
        raise PodArtifactError("stable Pod manifests cannot publish a prerelease version")
    if manifest.get("perimetr_api") not in {None, "v1"}:
        raise PodArtifactError("Pod release is incompatible with Perimetr API v1")
    minimum_perimetr = str(manifest.get("minimum_perimetr_version") or "").strip()
    if minimum_perimetr and compare_versions(perimetr_version, minimum_perimetr) < 0:
        raise PodArtifactError(
            f"Pod {manifest['version']} requires Perimetr {minimum_perimetr} or newer"
        )
    artifact_url = urlparse(str(manifest["url"]))
    if artifact_url.scheme != "https" or not artifact_url.hostname:
        raise PodArtifactError("Pod artifact URL must use HTTPS")
    digest = str(manifest["sha256"]).lower()
    if not SHA256_PATTERN.fullmatch(digest):
        raise PodArtifactError("Pod artifact SHA-256 is invalid")
    size = manifest.get("size")
    if size is not None and (not isinstance(size, int) or size < 2):
        raise PodArtifactError("Pod artifact size is invalid")
    try:
        public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
    except (OSError, ValueError, TypeError) as exc:
        raise PodArtifactError("trusted Pod update public key is unavailable or invalid") from exc
    if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(
        public_key.curve, ec.SECP256R1
    ):
        raise PodArtifactError("trusted Pod update key must be ECDSA P-256")
    unsigned = {key: value for key, value in manifest.items() if key != "signature"}
    try:
        signature = base64.b64decode(str(manifest["signature"]), validate=True)
        public_key.verify(signature, _canonical_json(unsigned), ec.ECDSA(hashes.SHA256()))
    except (ValueError, binascii.Error, InvalidSignature) as exc:
        raise PodArtifactError("Pod update manifest signature is invalid") from exc
    return {**manifest, "sha256": digest}


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = _canonical_json(value) + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _hash_executable(path: Path, maximum_bytes: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    prefix = b""
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                if not prefix:
                    prefix = chunk[:2]
                total += len(chunk)
                if total > maximum_bytes:
                    raise PodArtifactError("Pod executable exceeds the configured size limit")
                digest.update(chunk)
    except OSError as exc:
        raise PodArtifactError(f"Pod executable cannot be read: {exc}") from exc
    if prefix != b"MZ":
        raise PodArtifactError("Pod executable does not have a Windows PE header")
    return digest.hexdigest(), total


def _artifact_directory(cache_root: Path, digest: str) -> Path:
    return cache_root / "artifacts" / digest


def _load_artifact(cache_root: Path, digest: str, maximum_bytes: int) -> PodArtifact | None:
    if not SHA256_PATTERN.fullmatch(str(digest or "").lower()):
        return None
    normalized = digest.lower()
    directory = _artifact_directory(cache_root, normalized)
    executable = directory / "pod.exe"
    metadata = _load_json(directory / "manifest.json")
    try:
        actual, _ = _hash_executable(executable, maximum_bytes)
    except PodArtifactError:
        return None
    if actual != normalized:
        return None
    version = str(metadata.get("version") or "")
    try:
        _semver(version)
    except PodArtifactError:
        return None
    signed_manifest = metadata.get("signed_manifest")
    if not isinstance(signed_manifest, dict):
        signed_manifest = {
            key: value
            for key, value in metadata.items()
            if key not in {"cache_source", "verified_at"}
        }
    return PodArtifact(
        version=version,
        sha256=normalized,
        path=executable,
        source=str(metadata.get("cache_source") or "verified-cache"),
        manifest=signed_manifest,
    )


def _store_local_artifact(
    cache_root: Path,
    source: Path,
    *,
    version: str,
    maximum_bytes: int,
    cache_source: str,
) -> PodArtifact:
    _semver(version)
    digest, size = _hash_executable(source, maximum_bytes)
    directory = _artifact_directory(cache_root, digest)
    destination = directory / "pod.exe"
    directory.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = directory / f".pod.exe.{os.getpid()}.tmp"
        try:
            with source.open("rb") as input_handle, temporary.open("wb") as output_handle:
                shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
                output_handle.flush()
                os.fsync(output_handle.fileno())
            os.chmod(temporary, 0o700)
            copied_digest, copied_size = _hash_executable(temporary, maximum_bytes)
            if copied_digest != digest or copied_size != size:
                raise PodArtifactError("Pod executable changed while it was cached")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    manifest = {
        "schema_version": 2,
        "product": "pod",
        "version": version,
        "channel": "stable",
        "sha256": digest,
        "size": size,
        "cache_source": cache_source,
        "verified_at": _now_iso(),
    }
    _atomic_json(directory / "manifest.json", manifest)
    return PodArtifact(version, digest, destination, cache_source, manifest)


def _factory_artifact(settings: Any, cache_root: Path) -> PodArtifact | None:
    source = Path(settings.perimetr_pod_bundle_source).resolve()
    executable = next(
        (
            candidate
            for candidate in (source / "pod.exe", source / "dist" / "pod.exe")
            if candidate.is_file()
        ),
        None,
    )
    if executable is None:
        return None
    return _store_local_artifact(
        cache_root,
        executable,
        version=settings.perimetr_pod_version,
        maximum_bytes=settings.perimetr_pod_max_artifact_bytes,
        cache_source="factory",
    )


def _download_artifact(
    manifest: dict[str, Any],
    cache_root: Path,
    *,
    timeout_seconds: float,
    maximum_bytes: int,
    opener: Callable[..., Any],
) -> PodArtifact:
    digest = manifest["sha256"]
    cached = _load_artifact(cache_root, digest, maximum_bytes)
    if cached is not None:
        if cached.version != manifest["version"]:
            raise PodArtifactError("cached Pod artifact version does not match its digest metadata")
        return replace(cached, source="verified-cache", manifest=manifest)

    directory = _artifact_directory(cache_root, digest)
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".pod-download-", dir=directory)
    temporary = Path(temporary_name)
    request = Request(
        str(manifest["url"]),
        headers={"Accept": "application/octet-stream", "User-Agent": "Exocortex-Perimetr/1"},
        method="GET",
    )
    actual_digest = hashlib.sha256()
    total = 0
    prefix = b""
    try:
        with os.fdopen(descriptor, "wb") as output_handle:
            with opener(request, timeout=timeout_seconds) as response:
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > maximum_bytes:
                    raise PodArtifactError("Pod executable exceeds the configured size limit")
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    if not prefix:
                        prefix = chunk[:2]
                    total += len(chunk)
                    if total > maximum_bytes:
                        raise PodArtifactError("Pod executable exceeds the configured size limit")
                    actual_digest.update(chunk)
                    output_handle.write(chunk)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        if prefix != b"MZ":
            raise PodArtifactError("downloaded Pod artifact is not a Windows executable")
        if actual_digest.hexdigest() != digest:
            raise PodArtifactError("downloaded Pod artifact checksum mismatch")
        expected_size = manifest.get("size")
        if expected_size is not None and total != expected_size:
            raise PodArtifactError("downloaded Pod artifact size mismatch")
        os.chmod(temporary, 0o700)
        os.replace(temporary, directory / "pod.exe")
        cache_metadata = {
            "version": manifest["version"],
            "sha256": manifest["sha256"],
            "size": total,
            "signed_manifest": manifest,
            "cache_source": "remote",
            "verified_at": _now_iso(),
        }
        _atomic_json(directory / "manifest.json", cache_metadata)
        return PodArtifact(
            version=manifest["version"],
            sha256=digest,
            path=directory / "pod.exe",
            source="remote",
            manifest=manifest,
        )
    except (OSError, ValueError) as exc:
        if isinstance(exc, PodArtifactError):
            raise
        raise PodArtifactError(f"Pod artifact download failed: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _read_manifest_response(response: Any) -> dict[str, Any]:
    body = response.read(MAX_MANIFEST_BYTES + 1)
    if len(body) > MAX_MANIFEST_BYTES:
        raise PodArtifactError("Pod update manifest is too large")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PodArtifactError("Pod update manifest is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise PodArtifactError("Pod update manifest must be a JSON object")
    return value


def _state_fallback(settings: Any, cache_root: Path, state: dict[str, Any]) -> PodArtifact | None:
    current = state.get("current") if isinstance(state.get("current"), dict) else {}
    cached = _load_artifact(
        cache_root,
        str(current.get("sha256") or ""),
        settings.perimetr_pod_max_artifact_bytes,
    )
    if cached is not None:
        return replace(cached, source="last-known-good")
    return _factory_artifact(settings, cache_root)


def ensure_latest_pod_artifact(
    settings: Any,
    *,
    force: bool = False,
    opener: Callable[..., Any] = urlopen,
) -> PodArtifact:
    with _artifact_lock:
        cache_root = Path(settings.perimetr_pod_cache_dir).resolve()
        cache_root.mkdir(parents=True, exist_ok=True)
        state_path = cache_root / "state.json"
        state = _load_json(state_path)
        fallback = _state_fallback(settings, cache_root, state)
        initialized_current = False
        if fallback is not None and not isinstance(state.get("current"), dict):
            state["current"] = {
                "version": fallback.version,
                "sha256": fallback.sha256,
                "source": fallback.source,
            }
            initialized_current = True
        repository_url = str(settings.perimetr_pod_repository_url or "").strip()
        if not repository_url:
            if fallback is None:
                raise PodArtifactError("no verified Pod runtime is available")
            if initialized_current:
                _atomic_json(
                    state_path,
                    {
                        **state,
                        "schema": POD_CACHE_SCHEMA,
                        "last_checked_at": _now_iso(),
                        "last_error": "",
                    },
                )
            return fallback

        try:
            manifest_url = pod_discovery_url(repository_url)
            public_key_path = Path(settings.perimetr_pod_update_public_key_path).resolve()
            if not public_key_path.is_file():
                raise PodArtifactError("trusted Pod update public key is unavailable")
            checked_epoch = float(state.get("checked_epoch") or 0)
            if (
                not force
                and fallback is not None
                and checked_epoch
                and time.time() - checked_epoch < settings.perimetr_pod_refresh_sec
            ):
                return fallback
            headers = {
                "Accept": "application/json",
                "User-Agent": "Exocortex-Perimetr/1",
            }
            if state.get("manifest_url") == manifest_url and state.get("etag"):
                headers["If-None-Match"] = str(state["etag"])
            request = Request(manifest_url, headers=headers, method="GET")
            try:
                with opener(request, timeout=settings.perimetr_update_check_timeout_sec) as response:
                    manifest = _verify_manifest(
                        _read_manifest_response(response),
                        public_key_path,
                        perimetr_version=settings.perimetr_version,
                    )
                    etag = str(response.headers.get("ETag") or "")
            except HTTPError as exc:
                if exc.code == 304 and fallback is not None:
                    state.update(
                        {
                            "schema": POD_CACHE_SCHEMA,
                            "manifest_url": manifest_url,
                            "last_checked_at": _now_iso(),
                            "checked_epoch": time.time(),
                            "last_error": "",
                        }
                    )
                    _atomic_json(state_path, state)
                    return fallback
                raise

            if fallback is not None:
                comparison = compare_versions(manifest["version"], fallback.version)
                if comparison < 0:
                    raise PodArtifactError("Pod discovery manifest attempted a version downgrade")
                if comparison == 0 and manifest["sha256"] != fallback.sha256:
                    raise PodArtifactError("Pod release reused a version with a different checksum")
            artifact = _download_artifact(
                manifest,
                cache_root,
                timeout_seconds=settings.perimetr_pod_download_timeout_sec,
                maximum_bytes=settings.perimetr_pod_max_artifact_bytes,
                opener=opener,
            )
            state = {
                "schema": POD_CACHE_SCHEMA,
                "manifest_url": manifest_url,
                "etag": etag,
                "last_checked_at": _now_iso(),
                "checked_epoch": time.time(),
                "last_error": "",
                "current": {
                    "version": artifact.version,
                    "sha256": artifact.sha256,
                    "source": artifact.source,
                },
            }
            _atomic_json(state_path, state)
            return artifact
        except Exception as exc:
            error = exc if isinstance(exc, PodArtifactError) else PodArtifactError(str(exc))
            state.update(
                {
                    "schema": POD_CACHE_SCHEMA,
                    "last_checked_at": _now_iso(),
                    "checked_epoch": time.time(),
                    "last_error": str(error),
                }
            )
            _atomic_json(state_path, state)
            if fallback is not None:
                return replace(fallback, refresh_error=str(error))
            raise error


def resolve_pinned_pod_artifact(
    settings: Any,
    digest: str,
    version: str,
    *,
    manifest: dict[str, Any] | None = None,
    opener: Callable[..., Any] = urlopen,
) -> PodArtifact:
    with _artifact_lock:
        cache_root = Path(settings.perimetr_pod_cache_dir).resolve()
        artifact = _load_artifact(
            cache_root,
            str(digest or "").lower(),
            settings.perimetr_pod_max_artifact_bytes,
        )
        source = "pinned-cache"
        if artifact is None and isinstance(manifest, dict) and manifest:
            verified = _verify_manifest(
                manifest,
                Path(settings.perimetr_pod_update_public_key_path).resolve(),
                perimetr_version=settings.perimetr_version,
            )
            if verified["sha256"] != str(digest or "").lower():
                raise PodArtifactError(
                    "the stored Pod manifest does not match the pinned checksum"
                )
            if verified["version"] != version:
                raise PodArtifactError(
                    "the stored Pod manifest does not match the pinned version"
                )
            artifact = _download_artifact(
                verified,
                cache_root,
                timeout_seconds=settings.perimetr_pod_download_timeout_sec,
                maximum_bytes=settings.perimetr_pod_max_artifact_bytes,
                opener=opener,
            )
            source = "pinned-redownload"
        if artifact is None:
            raise PodArtifactError("the Pod runtime pinned to this provisioning record is unavailable")
        if artifact.version != version:
            raise PodArtifactError("the pinned Pod runtime version does not match its verified artifact")
        return replace(artifact, source=source)
