from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from .database import Base, _connect_args, _normalize_database_url
from . import models  # noqa: F401


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["database_url_explicit"] = True
    config.set_main_option(
        "script_location",
        str(PROJECT_ROOT / "migrations"),
    )
    config.set_main_option(
        "sqlalchemy.url",
        _normalize_database_url(database_url).replace("%", "%%"),
    )
    return config


def upgrade_database(database_url: str) -> None:
    normalized_url = _normalize_database_url(database_url)
    engine = create_engine(
        normalized_url,
        future=True,
        pool_pre_ping=True,
        connect_args=_connect_args(database_url),
    )
    config = alembic_config(database_url)
    try:
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                connection.execute(
                    text("SELECT pg_advisory_lock(hashtext('perimetr-alembic-migrations'))")
                )
            try:
                config.attributes["connection"] = connection
                tables = set(inspect(connection).get_table_names())
                if tables and "alembic_version" not in tables:
                    expected_tables = set(Base.metadata.tables)
                    missing_tables = sorted(expected_tables - tables)
                    if missing_tables:
                        raise RuntimeError(
                            "Existing unversioned Perimetr database predates the "
                            f"0001 baseline and is missing tables: {', '.join(missing_tables)}. "
                            "Upgrade it with the legacy bridge release before installing "
                            "this version."
                        )
                    command.stamp(config, "0001")
                command.upgrade(config, "head")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                if engine.dialect.name == "postgresql":
                    connection.execute(
                        text("SELECT pg_advisory_unlock(hashtext('perimetr-alembic-migrations'))")
                    )
                    connection.commit()
    finally:
        engine.dispose()
