"""Import the existing salted verifier as the exact single-operator Access Key.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    settings = sa.table("system_settings", sa.column("key", sa.String), sa.column("value", sa.JSON))
    value = connection.execute(sa.select(settings.c.value).where(settings.c.key == "perimetr.preferences")).scalar()
    if value:
        value = dict(value)
        auth = dict(value.get("auth") or {})
        verifier = auth.get("access_key_hash") or auth.get("password_hash")
        if verifier:
            value["auth"] = {"access_key_hash": verifier}
            value["backup"] = {"include_audit": True, "include_sessions": False}
            connection.execute(settings.update().where(settings.c.key == "perimetr.preferences").values(value=value))
    # Old sessions do not cross the changed authentication boundary.
    sessions = sa.table("session_leases", sa.column("status", sa.String), sa.column("transport", sa.String))
    connection.execute(sessions.update().where(sessions.c.transport == "direct").values(status="revoked"))


def downgrade() -> None:
    # A username cannot be reconstructed after intentionally removing it.
    # Restore the saved 1.2.3 snapshot through the old image for rollback.
    raise RuntimeError("Access Key rollback requires the saved pre-migration snapshot with the previous image")
