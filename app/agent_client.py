from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import secrets
import time
from typing import Any
from urllib.parse import urljoin

import httpx
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


class AgentTransportError(RuntimeError):
    pass


CONTROLLER_SIGNATURE_CONTEXT = "exocortex-controller-request-v1"


def _endpoint(base_url: str, path: str) -> str:
    normalized = base_url.strip().rstrip("/") + "/"
    if not normalized.startswith(("http://", "https://")):
        raise AgentTransportError("Agent endpoint must use HTTP or HTTPS")
    return urljoin(normalized, path.lstrip("/"))


def _request(
    method: str,
    base_url: str,
    path: str,
    *,
    timeout_seconds: float,
    controller_id: str,
    payload: dict[str, Any] | None = None,
    controller_private_key_pem: str = "",
) -> dict[str, Any]:
    url = _endpoint(base_url, path)
    body = (
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if payload is not None
        else b""
    )
    headers = {"X-Controller-ID": controller_id}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if controller_private_key_pem:
        headers.update(
            _controller_signature_headers(
                method=method,
                url=url,
                body=body,
                private_key_pem=controller_private_key_pem,
            )
        )
    try:
        response = httpx.request(
            method,
            url,
            content=body if payload is not None else None,
            headers=headers,
            timeout=timeout_seconds,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise AgentTransportError(f"Agent request failed: {exc}") from exc
    if response.status_code < 200 or response.status_code >= 300:
        detail = response.text[:1000].strip()
        raise AgentTransportError(
            f"Agent returned HTTP {response.status_code}: {detail or 'empty response'}"
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise AgentTransportError("Agent returned invalid JSON") from exc
    if not isinstance(body, dict):
        raise AgentTransportError("Agent returned a non-object response")
    return body


def enroll(
    *,
    base_url: str,
    agent_id: str,
    enrollment_token: str,
    expected_fingerprint: str,
    controller_id: str,
    controller_certificate_pem: str,
    heartbeat_endpoint: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    challenge = secrets.token_urlsafe(32)
    response = _request(
        "POST",
        base_url,
        "/v1/enroll",
        timeout_seconds=timeout_seconds,
        controller_id=controller_id,
        payload={
            "protocol_version": "1",
            "agent_id": agent_id,
            "enrollment_token": enrollment_token,
            "challenge": challenge,
            "controller_id": controller_id,
            "controller_cert": controller_certificate_pem,
            "heartbeat_endpoint": heartbeat_endpoint,
        },
    )
    if response.get("status") != "enrolled" or response.get("agent_id") != agent_id:
        raise AgentTransportError("Agent enrollment response does not match the request")
    certificate_pem = str(response.get("identity_certificate_pem") or "")
    signature_text = str(response.get("challenge_signature") or "")
    try:
        certificate = x509.load_pem_x509_certificate(certificate_pem.encode("utf-8"))
        fingerprint = "SHA256:" + certificate.fingerprint(hashes.SHA256()).hex().upper()
        signature = base64.b64decode(signature_text, validate=True)
        public_key = certificate.public_key()
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            raise AgentTransportError("Agent identity certificate does not use an EC key")
        public_key.verify(signature, challenge.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise AgentTransportError("Agent enrollment challenge verification failed") from exc
    if not secrets.compare_digest(fingerprint.upper(), expected_fingerprint.strip().upper()):
        raise AgentTransportError(
            f"Agent identity fingerprint mismatch: received {fingerprint}"
        )
    return {
        **response,
        "identity_certificate_pem": certificate_pem,
        "fingerprint_sha256": fingerprint,
        "certificate_serial": str(certificate.serial_number),
        "certificate_valid_not_before": certificate.not_valid_before_utc,
        "certificate_valid_not_after": certificate.not_valid_after_utc,
    }


def dispatch_job(
    *,
    base_url: str,
    controller_id: str,
    timeout_seconds: float,
    job_id: str,
    request_id: str,
    action: str,
    inputs: dict[str, Any],
    created_at: datetime,
    expires_at: datetime,
    controller_private_key_pem: str = "",
) -> dict[str, Any]:
    return _request(
        "POST",
        base_url,
        "/v1/jobs",
        timeout_seconds=timeout_seconds,
        controller_id=controller_id,
        controller_private_key_pem=controller_private_key_pem,
        payload={
            "protocol_version": "1",
            "job_id": job_id,
            "request_id": request_id,
            "created_at": _utc_iso(created_at),
            "expires_at": _utc_iso(expires_at),
            "action": action,
            "test": False,
            "inputs": inputs,
        },
    )


def decide_job(
    *,
    base_url: str,
    controller_id: str,
    timeout_seconds: float,
    job_id: str,
    decision: str,
    approval_id: str,
    plan_hash: str,
    confirmation_phrase: str = "",
    hostname_confirmation: str = "",
    controller_private_key_pem: str = "",
) -> dict[str, Any]:
    return _request(
        "POST",
        base_url,
        f"/v1/jobs/{job_id}/approve",
        timeout_seconds=timeout_seconds,
        controller_id=controller_id,
        controller_private_key_pem=controller_private_key_pem,
        payload={
            "decision": decision,
            "approval_id": approval_id,
            "plan_hash": plan_hash,
            "approval": {
                "confirmation_phrase": confirmation_phrase,
                "hostname_confirmation": hostname_confirmation,
            },
        },
    )


def cancel_job(
    *,
    base_url: str,
    controller_id: str,
    timeout_seconds: float,
    job_id: str,
    controller_private_key_pem: str = "",
) -> dict[str, Any]:
    return _request(
        "POST",
        base_url,
        f"/v1/jobs/{job_id}/cancel",
        timeout_seconds=timeout_seconds,
        controller_id=controller_id,
        controller_private_key_pem=controller_private_key_pem,
    )


def _controller_signature_headers(
    *,
    method: str,
    url: str,
    body: bytes,
    private_key_pem: str,
) -> dict[str, str]:
    parsed = httpx.URL(url)
    target = parsed.raw_path.decode("ascii")
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(18)
    canonical = "\n".join(
        (
            CONTROLLER_SIGNATURE_CONTEXT,
            method.upper(),
            target,
            timestamp,
            nonce,
            hashlib.sha256(body).hexdigest(),
        )
    ).encode("utf-8")
    try:
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"), password=None
        )
    except (TypeError, ValueError) as exc:
        raise AgentTransportError("Controller request-signing key is invalid") from exc
    if not isinstance(private_key, ec.EllipticCurvePrivateKey):
        raise AgentTransportError("Controller request-signing key must use EC")
    signature = private_key.sign(canonical, ec.ECDSA(hashes.SHA256()))
    return {
        "X-Controller-Signature-Version": "1",
        "X-Controller-Timestamp": timestamp,
        "X-Controller-Nonce": nonce,
        "X-Controller-Signature": base64.b64encode(signature).decode("ascii"),
    }


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
