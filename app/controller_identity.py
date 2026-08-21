from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ControllerIdentity
from .pod_service import decrypt_secret, encrypt_secret
from .settings import Settings


@dataclass(frozen=True)
class ControllerSigningMaterial:
    certificate_pem: str
    private_key_pem: str


def ensure_controller_signing_material(
    db: Session,
    settings: Settings,
    controller_id: str,
) -> ControllerSigningMaterial:
    identity = db.scalar(
        select(ControllerIdentity).where(
            ControllerIdentity.controller_id == controller_id,
        )
    )
    if (
        identity
        and identity.status == "active"
        and identity.certificate_pem
        and identity.encrypted_private_key
    ):
        return ControllerSigningMaterial(
            certificate_pem=identity.certificate_pem,
            private_key_pem=decrypt_secret(identity.encrypted_private_key, settings),
        )

    private_key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, controller_id)])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=730))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False
        )
        .sign(private_key, hashes.SHA256())
    )
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    private_key_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    if identity is None:
        identity = ControllerIdentity(controller_id=controller_id)
        db.add(identity)
    identity.certificate_pem = certificate_pem
    identity.encrypted_private_key = encrypt_secret(private_key_pem, settings)
    identity.encryption_metadata = {
        "scheme": "fernet-sha256-derived-v1",
        "request_auth": "ecdsa-p256-sha256-v1",
    }
    identity.status = "active"
    db.flush()
    return ControllerSigningMaterial(
        certificate_pem=certificate_pem,
        private_key_pem=private_key_pem,
    )
