import hashlib
import json
from urllib.error import HTTPError

import pytest

from app.kernel_register import (
    KernelRegisterError,
    _verify_snapshot,
    _write_cache,
    apply_register,
    load_snapshot,
)
from app.settings import Settings


def reference(number: int) -> str:
    return f"volt://{number:08x}-1111-4111-8111-111111111111/{number:08x}-2222-4222-8222-222222222222"


RESOLVED = {
    "repositories.perimetr.url": "https://github.com/example/perimetr",
    "repositories.pod.url": "https://github.com/example/pod",
    "services.perimetr.sni": "perimetr.internal",
    "services.perimetr.port": "18443",
    "intervals.kernel.refresh_sec": "60",
}


def snapshot(values=None):
    references = {key: reference(index + 1) for index, key in enumerate(RESOLVED)}
    values = values or {
        "repositories": {
            "perimetr": {"url": references["repositories.perimetr.url"]},
            "pod": {"url": references["repositories.pod.url"]},
        },
        "services": {
            "perimetr": {
                "sni": references["services.perimetr.sni"],
                "port": references["services.perimetr.port"],
            },
        },
        "intervals": {"kernel": {"refresh_sec": references["intervals.kernel.refresh_sec"]}},
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
            "https://kernel.internal/api/v1/register/snapshot"
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
    monkeypatch.setattr("app.kernel_register.resolve_values", lambda **_: RESOLVED)
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
    payload = snapshot()
    monkeypatch.setattr("app.kernel_register.load_snapshot", lambda **_: payload)
    monkeypatch.setattr("app.kernel_register.resolve_values", lambda **_: {
        **RESOLVED,
        "services.perimetr.sni": "perimetr.example.com",
        "services.perimetr.port": "443",
    })
    settings = Settings(
        _env_file=None,
        kernel_url="https://kernel.example.com",
        kernel_service_token="test-service-token",
        kernel_cache_path=str(tmp_path / "register.snapshot.json"),
    )

    applied = apply_register(settings)

    assert applied.perimetr_public_url == "https://perimetr.example.com"
