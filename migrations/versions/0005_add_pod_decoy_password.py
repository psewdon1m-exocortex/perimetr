"""Add optional Pod decoy password hashes.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-13
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table_name: str) -> None:
    connection = op.get_bind()
    columns = {item["name"] for item in sa.inspect(connection).get_columns(table_name)}
    if "decoy_password_hash" not in columns:
        op.add_column(
            table_name,
            sa.Column(
                "decoy_password_hash",
                sa.Text(),
                nullable=False,
                server_default="",
            ),
        )


def upgrade() -> None:
    _add_column_if_missing("pod_provisioning_records")
    _add_column_if_missing("pods")


def downgrade() -> None:
    op.drop_column("pods", "decoy_password_hash")
    op.drop_column("pod_provisioning_records", "decoy_password_hash")
