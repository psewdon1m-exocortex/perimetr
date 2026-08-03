from __future__ import annotations

import base64
from datetime import timedelta
import hashlib
import hmac
import io
import json
from pathlib import Path
import re
import secrets
import struct
from urllib.parse import parse_qs, urlparse
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from .models import Pod, PodProvisioningRecord, Subject
from .pod_artifacts import PodArtifact
from .settings import Settings


SUPPORTED_VLESS_SECURITY = {"none", "tls", "reality"}
SUPPORTED_VLESS_TRANSPORT = {"tcp", "ws", "grpc", "http", "httpupgrade", "xhttp"}
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{index}" for index in range(1, 10)), *(f"LPT{index}" for index in range(1, 10))}


def _fernet(settings: Settings) -> Fernet:
    digest = hashlib.sha256(settings.perimetr_pod_signing_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str, settings: Settings) -> str:
    return _fernet(settings).encrypt(value.encode("utf-8")).decode("ascii") if value else ""


def decrypt_secret(value: str, settings: Settings) -> str:
    if not value:
        return ""
    try:
        return _fernet(settings).decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise HTTPException(status_code=500, detail="pod_secret_key_mismatch") from exc


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_pod_password(value: str) -> str:
    if len(value) < 8:
        raise HTTPException(status_code=400, detail="pod_password_too_short")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256$310000${base64.urlsafe_b64encode(salt).decode('ascii')}${base64.urlsafe_b64encode(digest).decode('ascii')}"


def verify_pod_password(value: str, stored: str) -> bool:
    try:
        algorithm, iterations, encoded_salt, encoded_digest = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
        expected = base64.urlsafe_b64decode(encoded_digest.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def pod_executable_name(login: str) -> str:
    candidate = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", login.strip()).strip(" .")
    candidate = re.sub(r"\s+", " ", candidate)[:80].strip(" .") or "pod"
    if candidate.upper() in WINDOWS_RESERVED_NAMES:
        candidate = f"pod-{candidate}"
    return f"{candidate}.exe"


def png_icon_bytes(encoded_png: str) -> tuple[bytes, bytes] | None:
    if not encoded_png:
        return None
    try:
        png = base64.b64decode(encoded_png, validate=True)
    except ValueError:
        return None
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
    return png, header + entry + png


def validate_vless_uri(value: str) -> str:
    candidate = (value or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme.lower() != "vless" or not parsed.username or not parsed.hostname or not parsed.port:
        raise HTTPException(status_code=400, detail="invalid_vless_connection")
    if not re.fullmatch(r"[0-9a-fA-F-]{32,36}", parsed.username):
        raise HTTPException(status_code=400, detail="invalid_vless_identity")
    query = parse_qs(parsed.query)
    security = (query.get("security") or ["none"])[0].lower()
    transport = (query.get("type") or ["tcp"])[0].lower()
    if security not in SUPPORTED_VLESS_SECURITY:
        raise HTTPException(status_code=400, detail=f"unsupported_vless_security:{security}")
    if transport not in SUPPORTED_VLESS_TRANSPORT:
        raise HTTPException(status_code=400, detail=f"unsupported_vless_transport:{transport}")
    return candidate


def validate_subject_pod_config(subject: Subject, settings: Settings) -> None:
    validate_vless_uri(decrypt_secret(subject.vless_uri_encrypted, settings))
    if not settings.perimetr_public_url:
        raise HTTPException(status_code=400, detail="perimetr_endpoint_not_configured")
    if not subject.update_channel:
        raise HTTPException(status_code=400, detail="update_channel_not_configured")


def subject_pod_config(subject: Subject, settings: Settings) -> dict:
    security_policy = dict(subject.security_policy or {})
    if settings.perimetr_pod_update_manifest_url:
        try:
            update_public_key = Path(
                settings.perimetr_pod_update_public_key_path
            ).read_text(encoding="ascii")
        except (OSError, UnicodeError):
            update_public_key = ""
        if update_public_key:
            # The repository-derived URL and the release-pinned trust anchor
            # are a pair. Subject data must not silently redirect Pod updates
            # to a manifest signed by another key.
            security_policy["update_manifest_url"] = (
                settings.perimetr_pod_update_manifest_url
            )
            security_policy["update_public_key_pem"] = update_public_key
    if settings.perimetr_xray_dns_url:
        security_policy.setdefault("xray_dns_url", settings.perimetr_xray_dns_url)
    if settings.perimetr_proxy_verification_url:
        security_policy.setdefault(
            "proxy_verification_url",
            settings.perimetr_proxy_verification_url,
        )
    return {
        "subject": {"id": subject.entity_id, "name": subject.name},
        "perimetr_endpoint": settings.perimetr_public_url.rstrip("/"),
        "vless_connection": decrypt_secret(subject.vless_uri_encrypted, settings),
        "network_profile_version": subject.network_profile_version,
        "system_tabs": sorted(subject.system_tabs or [], key=lambda item: item.get("position", 0)),
        "system_tabs_profile_version": subject.system_tabs_profile_version,
        "update_channel": subject.update_channel,
        "ui_policy": subject.ui_policy or {},
        "security_policy": security_policy,
        "minimum_pod_version": settings.perimetr_pod_version,
        "default_navigation_url": settings.perimetr_default_pod_url,
    }


def issue_enrollment_token(settings: Settings) -> tuple[str, str, str]:
    plain = secrets.token_urlsafe(32)
    return plain, hash_token(plain), encrypt_secret(plain, settings)


def public_key_fingerprint(public_key_pem: str) -> str:
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="invalid_pod_public_key") from exc
    if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(public_key.curve, ec.SECP256R1):
        raise HTTPException(status_code=400, detail="pod_public_key_must_be_ecdsa_p256")
    der = public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return "SHA256:" + hashlib.sha256(der).hexdigest().upper()


def issue_identity_certificate(pod: Pod, settings: Settings) -> str:
    certificate = {
        "version": 1,
        "pod_id": pod.id,
        "subject_id": pod.subject.entity_id,
        "fingerprint": pod.certificate_fingerprint,
        "device_binding_fingerprint": pod.device_binding_fingerprint,
        "issued_at": pod.activated_at.isoformat() if pod.activated_at else "",
    }
    encoded = base64.urlsafe_b64encode(json.dumps(certificate, sort_keys=True, separators=(",", ":")).encode()).decode()
    signature = hmac.new(settings.perimetr_pod_signing_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def heartbeat_signing_bytes(payload: dict) -> bytes:
    content = {key: value for key, value in payload.items() if key != "signature"}
    for key, value in list(content.items()):
        if hasattr(value, "isoformat"):
            content[key] = value.isoformat().replace("+00:00", "Z")
    return json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_heartbeat_signature(public_key_pem: str, payload: dict, signature: str) -> None:
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        public_key.verify(base64.b64decode(signature), heartbeat_signing_bytes(payload), ec.ECDSA(hashes.SHA256()))
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise HTTPException(status_code=403, detail="invalid_pod_signature") from exc


def provisioning_payload(record: PodProvisioningRecord, subject: Subject, settings: Settings) -> dict:
    return {
        "id": record.id,
        "subject_id": subject.entity_id,
        "name": record.name,
        "login": record.login,
        "status": record.status,
        "bundle_version": record.bundle_version,
        "artifact_sha256": record.artifact_sha256,
        "runtime_source": str((record.metadata_json or {}).get("runtime_source") or ""),
        "runtime_warning": str((record.metadata_json or {}).get("runtime_warning") or ""),
        "download_count": record.download_count,
        "downloaded_at": record.downloaded_at,
        "expires_at": record.expires_at,
        "activated_at": record.activated_at,
        "download_url": f"/v1/subjects/{subject.entity_id}/pods/{record.id}/download" if record.status not in {"revoked", "expired", "active"} else None,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def pod_payload(pod: Pod, subject: Subject) -> dict:
    return {
        "id": pod.id,
        "subject_id": subject.entity_id,
        "name": pod.name,
        "login": pod.login,
        "status": pod.status,
        "last_seen": pod.last_seen_at,
        "last_seen_at": pod.last_seen_at,
        "last_heartbeat_at": pod.last_heartbeat_at,
        "certificate_fingerprint": pod.certificate_fingerprint,
        "device_binding_fingerprint": pod.device_binding_fingerprint,
        "device_binding_status": pod.device_binding_status,
        "pod_version": pod.pod_version,
        "xray_version": pod.xray_version,
        "network_profile_version": pod.network_profile_version,
        "system_tabs_profile_version": pod.system_tabs_profile_version,
        "created_at": pod.created_at,
        "activated_at": pod.activated_at,
    }


def build_pod_bundle(
    record: PodProvisioningRecord,
    subject: Subject,
    settings: Settings,
    artifact: PodArtifact,
) -> bytes:
    token = decrypt_secret(record.enrollment_token_encrypted, settings)
    executable_name = pod_executable_name(record.login)
    bootstrap = {
        "format_version": 1,
        "provisioning_id": record.id,
        "enrollment_token": token,
        "perimetr_endpoint": settings.perimetr_public_url.rstrip("/"),
        "subject": {"id": subject.entity_id, "name": subject.name},
        "application_name": record.login,
        "executable_name": executable_name,
        "icon_path": "state/assets/entity-icon.png" if subject.image_data else "",
        "executable_icon_path": f"{Path(executable_name).stem}.ico" if subject.image_data else "",
        "bundle_version": record.bundle_version,
    }
    output = io.BytesIO()
    manifest_payload = {
        "name": "Perimetr Pod",
        "version": artifact.version,
        "sha256": artifact.sha256,
        "runtime": "electron-chromium",
        "proxy_engine": "xray-core",
        "update_channel": subject.update_channel,
        "perimetr_api": "v1",
        "repository": settings.perimetr_pod_repository_url,
        "update_manifest": settings.perimetr_pod_update_manifest_url,
        "xray": {
            "version": settings.perimetr_xray_version,
            "source": settings.perimetr_xray_source_url,
            "sha256": settings.perimetr_xray_sha256,
        },
    }
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("state/config/bootstrap.json", json.dumps(bootstrap, ensure_ascii=True, indent=2))
        archive.writestr(
            "README.txt",
            f"Perimetr Pod\r\n\r\nRun {executable_name}. Keep the complete directory together. "
            "The first launch requires this Pod login and password and creates a device-bound identity.\r\n",
        )
        icon = png_icon_bytes(subject.image_data)
        if icon:
            archive.writestr("state/assets/entity-icon.png", icon[0])
            archive.writestr(f"{Path(executable_name).stem}.ico", icon[1])
        archive.write(artifact.path, executable_name, compress_type=ZIP_STORED)
        archive.writestr(
            "pod_manifest.json",
            json.dumps(manifest_payload, ensure_ascii=True, indent=2),
        )
    return output.getvalue()


def provisioning_expiry(settings: Settings):
    from .services import now_utc

    return now_utc() + timedelta(seconds=settings.perimetr_pod_enrollment_ttl_sec)
