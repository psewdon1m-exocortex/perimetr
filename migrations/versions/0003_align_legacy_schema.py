"""Align databases created by the pre-Alembic runtime migrations.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-30
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


AGENT_ID_TABLES = (
    "agent_assignments",
    "agent_capabilities",
    "agent_certificates",
    "agent_commands",
    "agent_endpoints",
    "agent_heartbeats",
    "agent_state_events",
    "approval_decisions",
    "approval_requests",
    "job_events",
    "job_results",
    "jobs",
    "revocation_records",
    "session_leases",
)

SUBJECT_ID_TABLES = (
    "launch_authorizations",
    "pod_provisioning_records",
    "pods",
    "session_leases",
)


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        return

    op.execute("ALTER TABLE agents ALTER COLUMN id TYPE VARCHAR(64)")
    for table_name in AGENT_ID_TABLES:
        op.execute(
            f'ALTER TABLE "{table_name}" ALTER COLUMN agent_id TYPE VARCHAR(64)'
        )

    op.execute("ALTER TABLE objects ALTER COLUMN id TYPE VARCHAR(64)")
    op.execute("ALTER TABLE subjects ALTER COLUMN id TYPE VARCHAR(64)")
    op.execute("ALTER TABLE subjects ALTER COLUMN object_id TYPE VARCHAR(64)")
    for table_name in SUBJECT_ID_TABLES:
        op.execute(
            f'ALTER TABLE "{table_name}" ALTER COLUMN subject_id TYPE VARCHAR(64)'
        )

    op.execute(
        """
        UPDATE objects
        SET entity_id = upper(substr(translate(md5(id || clock_timestamp()::text), '0', '2'), 1, 16))
        WHERE entity_id IS NULL OR entity_id = ''
        """
    )
    op.execute(
        """
        UPDATE subjects
        SET entity_id = upper(substr(translate(md5(id || clock_timestamp()::text), '0', '2'), 1, 16))
        WHERE entity_id IS NULL OR entity_id = ''
        """
    )
    op.execute("ALTER TABLE objects ALTER COLUMN entity_id SET NOT NULL")
    op.execute("ALTER TABLE subjects ALTER COLUMN entity_id SET NOT NULL")

    indexes = (
        ("ix_agents_certificate_serial", "agents", "certificate_serial"),
        ("ix_agents_domain", "agents", "domain"),
        ("ix_agents_enrollment_state", "agents", "enrollment_state"),
        ("ix_agents_library_position", "agents", "library_position"),
        ("ix_certificate_denylist_agent_id", "certificate_denylist", "agent_id"),
        ("ix_pod_provisioning_records_login", "pod_provisioning_records", "login"),
        ("ix_pods_certificate_fingerprint", "pods", "certificate_fingerprint"),
        ("ix_pods_device_binding_fingerprint", "pods", "device_binding_fingerprint"),
        ("ix_pods_last_seen_at", "pods", "last_seen_at"),
        ("ix_pods_login", "pods", "login"),
        ("ix_pods_provisioning_id", "pods", "provisioning_id"),
        ("ix_pods_status", "pods", "status"),
        ("ix_subjects_kind", "subjects", "kind"),
    )
    for name, table_name, column_name in indexes:
        op.execute(
            f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table_name}" ("{column_name}")'
        )

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'pods_provisioning_id_fkey'
          ) THEN
            ALTER TABLE pods
              ADD CONSTRAINT pods_provisioning_id_fkey
              FOREIGN KEY (provisioning_id)
              REFERENCES pod_provisioning_records(id);
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "The legacy schema alignment is intentionally forward-only. Restore "
        "the mandatory pre-update backup with the previous image instead."
    )
