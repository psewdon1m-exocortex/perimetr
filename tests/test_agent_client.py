from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app import agent_client


def _identity_certificate() -> tuple[ec.EllipticCurvePrivateKey, str, str]:
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "agent-test")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    pem = certificate.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    fingerprint = "SHA256:" + certificate.fingerprint(hashes.SHA256()).hex().upper()
    return key, pem, fingerprint


def test_enroll_verifies_agent_challenge_and_fingerprint(monkeypatch) -> None:
    key, certificate_pem, fingerprint = _identity_certificate()
    observed: dict = {}

    def fake_request(method, url, **kwargs):
        observed.update({"method": method, "url": url, **kwargs})
        challenge = kwargs["json"]["challenge"]
        signature = key.sign(challenge.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        return httpx.Response(
            200,
            json={
                "status": "enrolled",
                "agent_id": "agent-1",
                "identity_certificate_pem": certificate_pem,
                "challenge_signature": base64.b64encode(signature).decode("ascii"),
            },
        )

    monkeypatch.setattr(agent_client.httpx, "request", fake_request)
    result = agent_client.enroll(
        base_url="https://agent.example:7443",
        agent_id="agent-1",
        enrollment_token="one-time-token",
        expected_fingerprint=fingerprint.lower(),
        controller_id="perimetr-1",
        heartbeat_endpoint="https://perimetr.example/api/agents/agent-1/heartbeat",
        timeout_seconds=4,
    )

    assert observed["method"] == "POST"
    assert observed["url"] == "https://agent.example:7443/v1/enroll"
    assert observed["headers"]["X-Controller-ID"] == "perimetr-1"
    assert observed["follow_redirects"] is False
    assert result["fingerprint_sha256"] == fingerprint
    assert result["certificate_serial"]


def test_agent_requests_are_readable_dispatch_and_decision_calls(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return httpx.Response(202, json={"status": "accepted"})

    monkeypatch.setattr(agent_client.httpx, "request", fake_request)
    now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
    agent_client.dispatch_job(
        base_url="http://127.0.0.1:7443",
        controller_id="controller",
        timeout_seconds=5,
        job_id="job-1",
        request_id="request-1",
        action="system.info",
        inputs={"verbose": True},
        created_at=now,
        expires_at=now + timedelta(minutes=15),
    )
    agent_client.decide_job(
        base_url="http://127.0.0.1:7443",
        controller_id="controller",
        timeout_seconds=5,
        job_id="job-1",
        decision="approved",
        approval_id="approval-1",
        plan_hash="sha256:plan",
        confirmation_phrase="EXTERMINATUS",
        hostname_confirmation="node-1",
    )

    assert calls[0][1].endswith("/v1/jobs")
    assert calls[0][2]["json"]["action"] == "system.info"
    assert calls[0][2]["json"]["expires_at"] == "2026-07-27T12:15:00Z"
    assert calls[1][1].endswith("/v1/jobs/job-1/approve")
    assert calls[1][2]["json"]["decision"] == "approved"
    assert calls[1][2]["json"]["approval"]["hostname_confirmation"] == "node-1"


def test_enroll_rejects_fingerprint_mismatch(monkeypatch) -> None:
    key, certificate_pem, _fingerprint = _identity_certificate()

    def fake_request(_method, _url, **kwargs):
        signature = key.sign(
            kwargs["json"]["challenge"].encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )
        return httpx.Response(
            200,
            json={
                "status": "enrolled",
                "agent_id": "agent-1",
                "identity_certificate_pem": certificate_pem,
                "challenge_signature": base64.b64encode(signature).decode("ascii"),
            },
        )

    monkeypatch.setattr(agent_client.httpx, "request", fake_request)
    try:
        agent_client.enroll(
            base_url="https://agent.example:7443",
            agent_id="agent-1",
            enrollment_token="one-time-token",
            expected_fingerprint="SHA256:WRONG",
            controller_id="perimetr-1",
            heartbeat_endpoint="https://perimetr.example/api/agents/agent-1/heartbeat",
            timeout_seconds=4,
        )
    except agent_client.AgentTransportError as exc:
        assert "fingerprint mismatch" in str(exc)
    else:
        raise AssertionError("fingerprint mismatch must be rejected")
