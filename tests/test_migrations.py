from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.database import Base
from app.database_migrations import alembic_config, upgrade_database
from app.models import SystemSetting
from app.security import is_password_hash
import app.models  # noqa: F401


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def test_empty_database_upgrades_to_numbered_head(tmp_path: Path) -> None:
    path = tmp_path / "empty.sqlite"
    url = sqlite_url(path)
    upgrade_database(url)

    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert "objects" in tables
        assert "system_settings" in tables
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"

        from alembic import command

        command.check(alembic_config(url))
    finally:
        engine.dispose()


def test_existing_current_schema_is_adopted_and_plaintext_password_is_hashed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "existing.sqlite"
    url = sqlite_url(path)
    engine = create_engine(url)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(
                SystemSetting(
                    scope="perimetr",
                    key="perimetr.preferences",
                    value={
                        "auth": {
                            "username": "admin",
                            "password": "legacy-password",
                            "direct_enabled": True,
                        }
                    },
                )
            )
            db.commit()
    finally:
        engine.dispose()

    upgrade_database(url)

    engine = create_engine(url)
    try:
        with Session(engine) as db:
            setting = db.scalar(
                select(SystemSetting).where(SystemSetting.key == "perimetr.preferences")
            )
            auth = dict((setting.value if setting else {}).get("auth") or {})
            assert "password" not in auth
            assert is_password_hash(str(auth.get("password_hash") or ""))
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
    finally:
        engine.dispose()


def test_unversioned_unknown_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unknown.sqlite"
    url = sqlite_url(path)
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE unexpected (id INTEGER PRIMARY KEY)"))
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="predates the 0001 baseline"):
        upgrade_database(url)
