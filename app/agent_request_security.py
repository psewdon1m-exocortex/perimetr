from __future__ import annotations

import base64
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import hmac
import re
import threading
import time
from typing import Mapping

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec


SIGNATURE_VERSION = "1"
SIGNATURE_CONTEXT = "exocortex-agent-request-v1"
MAX_CLOCK_SKEW_SECONDS = 300
NONCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22,128}$")


class AgentRequestAuthError(ValueError):
    pass


class AgentRequestReplayCache:
    def __init__(self, *, max_entries: int = 10_000) -> None:
        self.max_entries = max_entries
        self._entries: OrderedDict[str, int] = OrderedDict()
        self._lock = threading.Lock()

    def consume(self, fingerprint: str, nonce: str, timestamp: int, *, now: int) -> bool:
        key = f"{fingerprint}:{nonce}"
        cutoff = now - MAX_CLOCK_SKEW_SECONDS
        with self._lock:
            while self._entries:
                _, oldest = next(iter(self._entries.items()))
                if oldest >= cutoff:
                    break
                self._entries.popitem(last=False)
            if key in self._entries:
                return False
            self._entries[key] = timestamp
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
        return True


def request_target(path: str, query: str = "") -> str:
    return f"{path}?{query}" if query else path


def signing_bytes(
    *,
    method: str,
    target: str,
    timestamp: str,
    nonce: str,
    body: bytes,
) -> bytes:
    body_hash = hashlib.sha256(body).hexdigest()
    return "\n".join(
        (
            SIGNATURE_CONTEXT,
            method.upper(),
            target,
            timestamp,
            nonce,
            body_hash,
        )
    ).encode("utf-8")


def verify_agent_request(
    *,
    certificate_pem: str,
    expected_fingerprint: str,
    method: str,
    target: str,
    body: bytes,
    headers: Mapping[str, str],
    replay_cache: AgentRequestReplayCache,
    now: int | None = None,
) -> None:
    version = str(headers.get("x-agent-signature-version") or "")
    fingerprint = str(headers.get("x-agent-fingerprint") or "")
    timestamp_text = str(headers.get("x-agent-timestamp") or "")
    nonce = str(headers.get("x-agent-nonce") or "")
    signature_text = str(headers.get("x-agent-signature") or "")
    if version != SIGNATURE_VERSION:
        raise AgentRequestAuthError("AGENT_SIGNATURE_VERSION_INVALID")
    if not fingerprint or not timestamp_text or not nonce or not signature_text:
        raise AgentRequestAuthError("AGENT_SIGNATURE_REQUIRED")
    if not NONCE_PATTERN.fullmatch(nonce):
        raise AgentRequestAuthError("AGENT_NONCE_INVALID")
    try:
        timestamp = int(timestamp_text)
    except ValueError as exc:
        raise AgentRequestAuthError("AGENT_TIMESTAMP_INVALID") from exc
    current = int(time.time()) if now is None else now
    if abs(current - timestamp) > MAX_CLOCK_SKEW_SECONDS:
        raise AgentRequestAuthError("AGENT_TIMESTAMP_OUT_OF_RANGE")
    try:
        certificate = x509.load_pem_x509_certificate(certificate_pem.encode("utf-8"))
        public_key = certificate.public_key()
        signature = base64.b64decode(signature_text, validate=True)
    except (TypeError, ValueError) as exc:
        raise AgentRequestAuthError("AGENT_IDENTITY_INVALID") from exc
    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise AgentRequestAuthError("AGENT_IDENTITY_INVALID")
    actual_fingerprint = "SHA256:" + certificate.fingerprint(hashes.SHA256()).hex().upper()
    if not _constant_time_equal(actual_fingerprint, expected_fingerprint) or not _constant_time_equal(
        fingerprint, expected_fingerprint
    ):
        raise AgentRequestAuthError("AGENT_IDENTITY_MISMATCH")
    current_dt = datetime.fromtimestamp(current, tz=timezone.utc)
    if current_dt < certificate.not_valid_before_utc or current_dt > certificate.not_valid_after_utc:
        raise AgentRequestAuthError("AGENT_CERTIFICATE_EXPIRED")
    try:
        public_key.verify(
            signature,
            signing_bytes(
                method=method,
                target=target,
                timestamp=timestamp_text,
                nonce=nonce,
                body=body,
            ),
            ec.ECDSA(hashes.SHA256()),
        )
    except InvalidSignature as exc:
        raise AgentRequestAuthError("AGENT_SIGNATURE_INVALID") from exc
    if not replay_cache.consume(actual_fingerprint, nonce, timestamp, now=current):
        raise AgentRequestAuthError("AGENT_REQUEST_REPLAYED")


def has_signature_headers(headers: Mapping[str, str]) -> bool:
    return any(
        headers.get(name)
        for name in (
            "x-agent-signature-version",
            "x-agent-timestamp",
            "x-agent-nonce",
            "x-agent-signature",
        )
    )


def _constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(
        hashlib.sha256(left.upper().encode("utf-8")).digest(),
        hashlib.sha256(right.upper().encode("utf-8")).digest(),
    )
