from types import SimpleNamespace
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.security import (
    LoginRateLimiter,
    hash_password,
    is_password_hash,
    validate_runtime_settings,
    verify_password,
)


def production_settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "perimetr_env": "production",
        "perimetr_direct_username": "operator",
        "perimetr_entry_password": "correct-horse-battery-staple",
        "perimetr_pod_signing_secret": "p" * 48,
        "kernel_service_token": "k" * 32,
        "updater_control_token": "u" * 48,
        "perimetr_database_url": "postgresql://perimetr:secret@db/perimetr",
        "perimetr_cookie_secure": True,
        "perimetr_public_url": "https://perimetr.example.com",
        "kernel_url": "https://kernel.example.com",
        "perimetr_pod_update_public_key_path": "",
        "perimetr_pod_refresh_sec": 900,
        "perimetr_pod_download_timeout_sec": 120,
        "perimetr_pod_max_artifact_bytes": 320 * 1024 * 1024,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_scrypt_password_round_trip() -> None:
    encoded = hash_password("a sufficiently long password")

    assert is_password_hash(encoded)
    assert verify_password("a sufficiently long password", encoded)
    assert not verify_password("wrong password", encoded)


def test_production_rejects_example_secrets_and_insecure_transport() -> None:
    settings = production_settings(
        perimetr_entry_password="replace-with-password",
        perimetr_database_url="sqlite:///perimetr.sqlite",
        perimetr_cookie_secure=False,
        kernel_url="http://kernel.internal",
    )

    with pytest.raises(RuntimeError) as error:
        validate_runtime_settings(settings)

    message = str(error.value)
    assert "PERIMETR_ENTRY_PASSWORD" in message
    assert "PostgreSQL" in message
    assert "PERIMETR_COOKIE_SECURE" in message
    assert "KERNEL_URL" in message


def test_production_accepts_non_placeholder_secrets_and_https(tmp_path: Path) -> None:
    key_path = tmp_path / "pod-update-public-key.pem"
    key_path.write_bytes(
        ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    validate_runtime_settings(
        production_settings(perimetr_pod_update_public_key_path=str(key_path))
    )


def test_login_rate_limiter_blocks_then_expires_attempts() -> None:
    limiter = LoginRateLimiter(
        max_attempts=2,
        window_seconds=10,
        base_delay_seconds=0.25,
        maximum_delay_seconds=1,
    )

    assert limiter.check("client", now=0).allowed
    limiter.fail("client", now=0)
    assert limiter.check("client", now=1).delay_seconds == 0.25
    limiter.fail("client", now=1)
    blocked = limiter.check("client", now=2)
    assert not blocked.allowed
    assert blocked.retry_after_seconds == 8
    assert limiter.check("client", now=11).allowed


def test_login_rate_limiter_bounds_tracked_client_memory() -> None:
    limiter = LoginRateLimiter(max_clients=2)
    limiter.fail("first", now=0)
    limiter.fail("second", now=1)
    limiter.fail("third", now=2)

    assert len(limiter._attempts) == 2
    assert "first" not in limiter._attempts
