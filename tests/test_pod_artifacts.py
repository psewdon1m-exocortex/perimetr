from __future__ import annotations

import base64
from io import BytesIO
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.pod_artifacts import (
    PodArtifactError,
    ensure_latest_pod_artifact,
    pod_discovery_url,
    resolve_pinned_pod_artifact,
)


class FakeResponse:
    def __init__(self, body: bytes, *, headers: dict[str, str] | None = None):
        self._body = BytesIO(body)
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class QueueOpener:
    def __init__(self, *results):
        self.results = list(results)
        self.requests = []

    def __call__(self, request, *, timeout):
        self.requests.append((request, timeout))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def canonical_json(value: dict) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def signed_manifest(private_key, artifact: bytes, *, version: str = "1.1.0") -> dict:
    manifest = {
        "schema_version": 2,
        "product": "pod",
        "version": version,
        "channel": "stable",
        "perimetr_api": "v1",
        "minimum_perimetr_version": "1.1.0",
        "url": f"https://github.com/example/pod/releases/download/pod-v{version}/pod.exe",
        "sha256": hashlib.sha256(artifact).hexdigest(),
        "size": len(artifact),
    }
    manifest["signature"] = base64.b64encode(
        private_key.sign(canonical_json(manifest), ec.ECDSA(hashes.SHA256()))
    ).decode("ascii")
    return manifest


@pytest.fixture
def artifact_settings(tmp_path: Path):
    factory = tmp_path / "factory"
    factory.mkdir()
    (factory / "pod.exe").write_bytes(b"MZ-factory-pod")
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key_path = tmp_path / "pod-update-public-key.pem"
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    settings = SimpleNamespace(
        perimetr_version="1.1.0",
        perimetr_pod_bundle_source=str(factory),
        perimetr_pod_cache_dir=str(tmp_path / "cache"),
        perimetr_pod_version="1.0.0",
        perimetr_pod_repository_url="https://github.com/example/pod.git",
        perimetr_pod_update_public_key_path=str(public_key_path),
        perimetr_pod_refresh_sec=900,
        perimetr_pod_download_timeout_sec=30,
        perimetr_pod_max_artifact_bytes=1024 * 1024,
        perimetr_update_check_timeout_sec=5,
    )
    return settings, private_key


def test_repository_url_drives_signed_latest_release_and_persistent_cache(
    artifact_settings,
) -> None:
    settings, private_key = artifact_settings
    executable = b"MZ-newest-verified-pod"
    manifest = signed_manifest(private_key, executable)
    opener = QueueOpener(
        FakeResponse(json.dumps(manifest).encode(), headers={"ETag": '"pod-1.1.0"'}),
        FakeResponse(executable, headers={"Content-Length": str(len(executable))}),
    )

    artifact = ensure_latest_pod_artifact(settings, force=True, opener=opener)

    assert artifact.version == "1.1.0"
    assert artifact.sha256 == manifest["sha256"]
    assert artifact.source == "remote"
    assert artifact.path.read_bytes() == executable
    assert opener.requests[0][0].full_url == pod_discovery_url(
        settings.perimetr_pod_repository_url
    )
    assert opener.requests[1][0].full_url == manifest["url"]

    pinned = resolve_pinned_pod_artifact(settings, artifact.sha256, artifact.version)
    assert pinned.path == artifact.path
    assert pinned.source == "pinned-cache"

    def unexpected_network_call(*_, **__):
        raise AssertionError("refresh interval should suppress the network request")

    interval_cached = ensure_latest_pod_artifact(
        settings,
        force=False,
        opener=unexpected_network_call,
    )
    assert interval_cached.sha256 == artifact.sha256


def test_304_and_offline_refresh_keep_last_known_good(artifact_settings) -> None:
    settings, private_key = artifact_settings
    executable = b"MZ-current-pod"
    manifest = signed_manifest(private_key, executable)
    first = QueueOpener(
        FakeResponse(json.dumps(manifest).encode(), headers={"ETag": '"current"'}),
        FakeResponse(executable),
    )
    current = ensure_latest_pod_artifact(settings, force=True, opener=first)

    not_modified = HTTPError(
        pod_discovery_url(settings.perimetr_pod_repository_url),
        304,
        "Not Modified",
        {},
        None,
    )
    cached = ensure_latest_pod_artifact(
        settings,
        force=True,
        opener=QueueOpener(not_modified),
    )
    assert cached.sha256 == current.sha256
    assert cached.refresh_error == ""

    offline = ensure_latest_pod_artifact(
        settings,
        force=True,
        opener=QueueOpener(URLError("network unavailable")),
    )
    assert offline.sha256 == current.sha256
    assert offline.source == "last-known-good"
    assert "network unavailable" in offline.refresh_error


def test_invalid_signature_cannot_replace_last_known_good(artifact_settings) -> None:
    settings, private_key = artifact_settings
    executable = b"MZ-current-pod"
    manifest = signed_manifest(private_key, executable)
    current = ensure_latest_pod_artifact(
        settings,
        force=True,
        opener=QueueOpener(FakeResponse(json.dumps(manifest).encode()), FakeResponse(executable)),
    )

    candidate = signed_manifest(private_key, b"MZ-untrusted-pod", version="1.2.0")
    candidate["signature"] = base64.b64encode(b"not-a-valid-signature").decode()
    fallback = ensure_latest_pod_artifact(
        settings,
        force=True,
        opener=QueueOpener(FakeResponse(json.dumps(candidate).encode())),
    )

    assert fallback.sha256 == current.sha256
    assert fallback.source == "last-known-good"
    assert fallback.refresh_error == "Pod update manifest signature is invalid"


def test_checksum_failure_preserves_factory_and_no_fallback_fails(artifact_settings) -> None:
    settings, private_key = artifact_settings
    manifest = signed_manifest(private_key, b"MZ-expected", version="1.1.0")
    fallback = ensure_latest_pod_artifact(
        settings,
        force=True,
        opener=QueueOpener(
            FakeResponse(json.dumps(manifest).encode()),
            FakeResponse(b"MZ-tampered"),
        ),
    )
    assert fallback.version == "1.0.0"
    assert fallback.source == "factory"
    assert fallback.refresh_error == "downloaded Pod artifact checksum mismatch"

    Path(settings.perimetr_pod_bundle_source, "pod.exe").unlink()
    empty_settings = SimpleNamespace(**vars(settings))
    empty_settings.perimetr_pod_cache_dir = str(
        Path(settings.perimetr_pod_cache_dir).parent / "empty-cache"
    )
    with pytest.raises(PodArtifactError, match="network unavailable"):
        ensure_latest_pod_artifact(
            empty_settings,
            force=True,
            opener=QueueOpener(URLError("network unavailable")),
        )


def test_factory_is_persisted_as_last_known_good_without_repository(
    artifact_settings,
) -> None:
    settings, _ = artifact_settings
    settings.perimetr_pod_repository_url = ""
    factory = ensure_latest_pod_artifact(settings)
    Path(settings.perimetr_pod_bundle_source, "pod.exe").unlink()

    persisted = ensure_latest_pod_artifact(settings)

    assert persisted.sha256 == factory.sha256
    assert persisted.source == "last-known-good"


def test_tampered_pinned_artifact_is_rejected(artifact_settings) -> None:
    settings, private_key = artifact_settings
    executable = b"MZ-current-pod"
    manifest = signed_manifest(private_key, executable)
    current = ensure_latest_pod_artifact(
        settings,
        force=True,
        opener=QueueOpener(FakeResponse(json.dumps(manifest).encode()), FakeResponse(executable)),
    )
    current.path.write_bytes(b"MZ-tampered-after-cache")

    with pytest.raises(PodArtifactError, match="pinned.*unavailable"):
        resolve_pinned_pod_artifact(settings, current.sha256, current.version)


def test_signed_manifest_restores_missing_pinned_artifact(artifact_settings) -> None:
    settings, private_key = artifact_settings
    executable = b"MZ-restorable-pod"
    manifest = signed_manifest(private_key, executable)
    current = ensure_latest_pod_artifact(
        settings,
        force=True,
        opener=QueueOpener(FakeResponse(json.dumps(manifest).encode()), FakeResponse(executable)),
    )
    current.path.unlink()

    restored = resolve_pinned_pod_artifact(
        settings,
        current.sha256,
        current.version,
        manifest=current.manifest,
        opener=QueueOpener(FakeResponse(executable)),
    )

    assert restored.source == "pinned-redownload"
    assert restored.path.read_bytes() == executable
