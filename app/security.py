from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import base64
import hashlib
from pathlib import Path
import re
import secrets
import threading
import time
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


SCRYPT_N = 16_384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
SCRYPT_MAXMEM = 64 * 1024 * 1024
PASSWORD_PREFIX = "scrypt"
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
PLACEHOLDER_MARKERS = (
    "change-this",
    "replace-with",
    "example-password",
    "perimetr-entry-password",
)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
        maxmem=SCRYPT_MAXMEM,
    )
    return f"{PASSWORD_PREFIX}${_encode(salt)}${_encode(derived)}"


def is_password_hash(value: str) -> bool:
    return isinstance(value, str) and value.startswith(f"{PASSWORD_PREFIX}$")


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_value, expected_value = encoded.split("$", 2)
        if algorithm != PASSWORD_PREFIX:
            return False
        salt = _decode(salt_value)
        expected = _decode(expected_value)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=len(expected),
            maxmem=SCRYPT_MAXMEM,
        )
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def constant_time_text_equal(left: str, right: str) -> bool:
    return secrets.compare_digest(str(left).encode("utf-8"), str(right).encode("utf-8"))


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return not lowered or any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def validate_runtime_settings(settings: Any) -> None:
    if str(settings.perimetr_env).strip().lower() != "production":
        return

    issues: list[str] = []
    username = str(settings.perimetr_direct_username)
    password = str(settings.perimetr_entry_password)
    signing_secret = str(settings.perimetr_pod_signing_secret)
    kernel_token = str(settings.kernel_service_token)
    updater_token = str(settings.updater_control_token)

    if not USERNAME_PATTERN.fullmatch(username):
        issues.append(
            "PERIMETR_DIRECT_USERNAME must contain 3-64 letters, numbers, dots, underscores or hyphens"
        )
    if len(password) < 12 or _is_placeholder(password):
        issues.append("PERIMETR_ENTRY_PASSWORD must contain at least 12 non-placeholder characters")
    if len(signing_secret) < 32 or _is_placeholder(signing_secret):
        issues.append("PERIMETR_POD_SIGNING_SECRET must contain at least 32 non-placeholder characters")
    if len(kernel_token) < 24 or _is_placeholder(kernel_token):
        issues.append("KERNEL_SERVICE_TOKEN must contain at least 24 non-placeholder characters")
    if len(updater_token) < 32 or _is_placeholder(updater_token):
        issues.append("UPDATER_CONTROL_TOKEN must contain at least 32 non-placeholder characters")
    if not str(settings.perimetr_database_url).startswith(
        ("postgresql://", "postgresql+psycopg://")
    ):
        issues.append("PERIMETR_DATABASE_URL must use PostgreSQL in production")
    if _is_placeholder(str(settings.perimetr_database_url)):
        issues.append("PERIMETR_DATABASE_URL contains a placeholder credential")
    if not bool(settings.perimetr_cookie_secure):
        issues.append("PERIMETR_COOKIE_SECURE must be true in production")
    if not str(settings.perimetr_public_url).startswith("https://"):
        issues.append("Perimetr public URL resolved from Kernel Register must use HTTPS in production")
    if not str(settings.kernel_url).startswith("https://"):
        issues.append("KERNEL_URL must use HTTPS in production")
    try:
        pod_update_key = serialization.load_pem_public_key(
            Path(str(settings.perimetr_pod_update_public_key_path)).read_bytes()
        )
        valid_pod_update_key = isinstance(
            pod_update_key, ec.EllipticCurvePublicKey
        ) and isinstance(pod_update_key.curve, ec.SECP256R1)
    except (OSError, TypeError, ValueError):
        valid_pod_update_key = False
    if not valid_pod_update_key:
        issues.append("PERIMETR_POD_UPDATE_PUBLIC_KEY_PATH must reference the trusted Pod ECDSA public key")
    if not 60 <= int(settings.perimetr_pod_refresh_sec) <= 86_400:
        issues.append("PERIMETR_POD_REFRESH_SEC must be between 60 and 86400")
    if not 10 <= float(settings.perimetr_pod_download_timeout_sec) <= 900:
        issues.append("PERIMETR_POD_DOWNLOAD_TIMEOUT_SEC must be between 10 and 900")
    if not 10 * 1024 * 1024 <= int(settings.perimetr_pod_max_artifact_bytes) <= 1024 * 1024 * 1024:
        issues.append("PERIMETR_POD_MAX_ARTIFACT_BYTES must be between 10 MiB and 1 GiB")

    if issues:
        raise RuntimeError("; ".join(issues))


@dataclass(frozen=True)
class LoginDecision:
    allowed: bool
    retry_after_seconds: int = 0
    delay_seconds: float = 0.0


class LoginRateLimiter:
    def __init__(
        self,
        *,
        max_attempts: int = 10,
        window_seconds: int = 10 * 60,
        base_delay_seconds: float = 0.25,
        maximum_delay_seconds: float = 2.0,
        max_clients: int = 10_000,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.base_delay_seconds = base_delay_seconds
        self.maximum_delay_seconds = maximum_delay_seconds
        self.max_clients = max_clients
        self._attempts: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> LoginDecision:
        timestamp = time.monotonic() if now is None else now
        with self._lock:
            attempts = self._attempts.get(key)
            if attempts is None:
                return LoginDecision(True)
            self._trim(attempts, timestamp)
            if not attempts:
                self._attempts.pop(key, None)
                return LoginDecision(True)
            if len(attempts) >= self.max_attempts:
                retry_after = max(
                    1,
                    int(self.window_seconds - (timestamp - attempts[0]) + 0.999),
                )
                return LoginDecision(False, retry_after_seconds=retry_after)
            delay = min(
                self.maximum_delay_seconds,
                self.base_delay_seconds * len(attempts),
            )
            return LoginDecision(True, delay_seconds=delay)

    def fail(self, key: str, *, now: float | None = None) -> None:
        timestamp = time.monotonic() if now is None else now
        with self._lock:
            attempts = self._attempts.get(key)
            if attempts is None:
                if len(self._attempts) >= self.max_clients:
                    self._attempts.pop(next(iter(self._attempts)))
                attempts = deque()
                self._attempts[key] = attempts
            self._trim(attempts, timestamp)
            attempts.append(timestamp)

    def success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def _trim(self, attempts: deque[float], timestamp: float) -> None:
        cutoff = timestamp - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
