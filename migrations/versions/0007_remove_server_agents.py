"""Remove the server Agent Node control plane.

Revision ID: 0007
Revises: 0006

Keep a pre-migration database snapshot with the previous image for rollback.
This migration performs no network calls or remote server operations.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

REMOVED_TABLES = (
    "agent_assignments", "agent_endpoints", "agent_certificates",
    "agent_capabilities", "agent_heartbeats", "agent_state_events",
    "agent_commands", "job_events", "job_results", "approval_requests",
    "approval_decisions", "revocation_records", "certificate_denylist",
    "controller_identity", "jobs", "agents",
)


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    # A device session associated with a retired identity must not survive as
    # an unscoped operator session after its identity column disappears.
    op.execute(sa.text("DELETE FROM session_leases WHERE agent_id IS NOT NULL"))
    naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    with op.batch_alter_table("session_leases", naming_convention=naming) as batch:
        for constraint in inspector.get_foreign_keys("session_leases"):
            if constraint["constrained_columns"] == ["agent_id"]:
                batch.drop_constraint(constraint["name"] or "fk_session_leases_agent_id_agents", type_="foreignkey")
        batch.drop_index("ix_session_leases_agent_id")
        batch.drop_column("agent_id")
    for table in REMOVED_TABLES:
        op.drop_table(table)

    settings = sa.table("system_settings", sa.column("key", sa.String), sa.column("value", sa.JSON))
    value = connection.execute(sa.select(settings.c.value).where(settings.c.key == "perimetr.preferences")).scalar()
    if value and "agents" in value.get("layout", {}).get("navigation", []):
        value = dict(value)
        value["layout"] = {**value["layout"], "navigation": [item for item in value["layout"]["navigation"] if item != "agents"]}
        value["revision"] = value.get("revision", 1) + 1
        connection.execute(settings.update().where(settings.c.key == "perimetr.preferences").values(value=value))


def downgrade() -> None:
    raise RuntimeError("Restore the pre-0007 database snapshot with its previous image to recover removed server-agent data")
