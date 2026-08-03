"""Hash the Perimetr operator password stored in preferences.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-30
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16_384,
        r=8,
        p=1,
        dklen=64,
        maxmem=64 * 1024 * 1024,
    )
    return f"scrypt${_encode(salt)}${_encode(derived)}"


def upgrade() -> None:
    settings = sa.table(
        "system_settings",
        sa.column("id", sa.String),
        sa.column("key", sa.String),
        sa.column("value", sa.JSON),
    )
    connection = op.get_bind()
    row = connection.execute(
        sa.select(settings.c.id, settings.c.value).where(
            settings.c.key == "perimetr.preferences"
        )
    ).first()
    if row is None:
        return
    value = row.value
    if isinstance(value, str):
        value = json.loads(value)
    preferences = dict(value or {})
    auth = dict(preferences.get("auth") or {})
    plaintext = str(auth.pop("password", "") or "")
    if plaintext and not str(auth.get("password_hash") or "").startswith("scrypt$"):
        auth["password_hash"] = _hash_password(plaintext)
    preferences["auth"] = auth
    connection.execute(
        settings.update().where(settings.c.id == row.id).values(value=preferences)
    )


def downgrade() -> None:
    raise RuntimeError(
        "Operator password hashing is irreversible. Restore the mandatory "
        "pre-update backup together with the previous application image."
    )
