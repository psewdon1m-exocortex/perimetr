import hashlib
import json
from urllib.error import HTTPError

import pytest

from app.kernel_register import (
    KernelRegisterError,
    _verify_snapshot,
    _write_cache,
    _registered_kernel_url,
    apply_register,
    load_snapshot,
)
from app.settings import Settings


def snapshot(values=None):
    values = values or {
        "repositories": {
            "perimetr": {"url": "https://github.com/example/perimetr"},
            "pod": {"url": "https://github.com/example/pod"},
        },
        "services": {
            "kernel": {"sni": "kernel.internal", "port": "18180"},
            "perimetr": {"sni": "perimetr.internal", "port": "18443"},
        },
        "intervals": {"kernel": {"refresh_sec": "60"}},
    }
    canonical = json.dumps(
        {"values": values},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "schema": "exocortex.register.snapshot.v1",
        "revision": "register-test-001",
        "checksum": "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "published_at": "2026-07-27T09:00:00Z",
        "valid_until": None,
        "values": values,
    }


def test_invalid_snapshot_is_rejected():
    payload = snapshot()
    payload["values"]["services"]["perimetr"]["sni"] = "changed.invalid"
    with pytest.raises(KernelRegisterError, match="checksum"):
        _verify_snapshot(payload)


def test_registered_kernel_url_uses_snapshot_sni_and_port():
    assert (
        _registered_kernel_url(
            snapshot(), "https://127.0.0.1:18180/bootstrap?ignored=true"
        )
        == "https://kernel.internal:18180"
    )


def test_unavailable_kernel_uses_validated_last_known_good(tmp_path):
    cache = tmp_path / "register.snapshot.json"
    payload = snapshot()
    _write_cache(cache, payload)

    loaded = load_snapshot(
        kernel_url="http://127.0.0.1:1",
        service_token="test-service-token",
        cache_path=str(cache),
        timeout_seconds=0.1,
    )

    assert loaded["revision"] == payload["revision"]
    assert loaded["checksum"] == payload["checksum"]


def test_unchanged_revision_uses_conditional_get_and_cached_snapshot(tmp_path, monkeypatch):
    cache = tmp_path / "register.snapshot.json"
    payload = snapshot()
    _write_cache(cache, payload)

    def not_modified(request, timeout):
        assert timeout == 0.5
        assert request.full_url == (
            "https://kernel.internal:18180/api/v1/register/snapshot"
        )
        assert request.get_header("If-none-match") == f'"{payload["revision"]}"'
        raise HTTPError(request.full_url, 304, "Not Modified", {}, None)

    monkeypatch.setattr("app.kernel_register.urlopen", not_modified)
    loaded = load_snapshot(
        kernel_url="https://kernel.internal",
        service_token="test-service-token",
        cache_path=str(cache),
        timeout_seconds=0.5,
    )

    assert loaded == payload


def test_register_builds_perimetr_url_from_registered_sni_and_port(tmp_path, monkeypatch):
    payload = snapshot()
    monkeypatch.setattr("app.kernel_register.load_snapshot", lambda **_: payload)
    settings = Settings(
        _env_file=None,
        kernel_url="https://kernel.internal",
        kernel_service_token="test-service-token",
        kernel_cache_path=str(tmp_path / "register.snapshot.json"),
    )

    applied = apply_register(settings)

    assert applied.perimetr_sni == "perimetr.internal"
    assert applied.perimetr_service_port == 18443
    assert applied.perimetr_public_url == "https://perimetr.internal:18443"
    assert applied.perimetr_repository_url == "https://github.com/example/perimetr"
    assert applied.perimetr_pod_repository_url == "https://github.com/example/pod"
    assert applied.perimetr_pod_update_manifest_url == (
        "https://github.com/example/pod/releases/download/pod-current/pod-update.json"
    )
    assert applied.kernel_register_revision == payload["revision"]


def test_register_omits_standard_https_port(tmp_path, monkeypatch):
    values = snapshot()["values"]
    values["services"]["perimetr"] = {
        "sni": "perimetr.example.com",
        "port": "443",
    }
    payload = snapshot(values)
    monkeypatch.setattr("app.kernel_register.load_snapshot", lambda **_: payload)
    settings = Settings(
        _env_file=None,
        kernel_url="https://kernel.example.com",
        kernel_service_token="test-service-token",
        kernel_cache_path=str(tmp_path / "register.snapshot.json"),
    )

    applied = apply_register(settings)

    assert applied.perimetr_public_url == "https://perimetr.example.com"
