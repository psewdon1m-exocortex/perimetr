from __future__ import annotations

import base64
from datetime import datetime, timezone
import secrets
from typing import Any
from urllib.parse import urljoin

import httpx
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec


class AgentTransportError(RuntimeError):
    pass


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
) -> dict[str, Any]:
    try:
        response = httpx.request(
            method,
            _endpoint(base_url, path),
            json=payload,
            headers={"X-Controller-ID": controller_id},
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
) -> dict[str, Any]:
    return _request(
        "POST",
        base_url,
        "/v1/jobs",
        timeout_seconds=timeout_seconds,
        controller_id=controller_id,
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
) -> dict[str, Any]:
    return _request(
        "POST",
        base_url,
        f"/v1/jobs/{job_id}/approve",
        timeout_seconds=timeout_seconds,
        controller_id=controller_id,
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
) -> dict[str, Any]:
    return _request(
        "POST",
        base_url,
        f"/v1/jobs/{job_id}/cancel",
        timeout_seconds=timeout_seconds,
        controller_id=controller_id,
    )


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
