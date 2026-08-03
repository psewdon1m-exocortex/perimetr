"""Pin provisioning records to verified Pod artifacts.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {item["name"] for item in sa.inspect(connection).get_columns("pod_provisioning_records")}
    if "artifact_sha256" not in columns:
        op.add_column(
            "pod_provisioning_records",
            sa.Column("artifact_sha256", sa.String(length=64), nullable=False, server_default=""),
        )
    indexes = {item["name"] for item in sa.inspect(connection).get_indexes("pod_provisioning_records")}
    if "ix_pod_provisioning_records_artifact_sha256" not in indexes:
        op.create_index(
            "ix_pod_provisioning_records_artifact_sha256",
            "pod_provisioning_records",
            ["artifact_sha256"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_pod_provisioning_records_artifact_sha256",
        table_name="pod_provisioning_records",
    )
    op.drop_column("pod_provisioning_records", "artifact_sha256")
