from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import Settings


class Base(DeclarativeBase):
    pass


settings = Settings()  # Opening the local database must not depend on a remote Register.


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(
    _normalize_database_url(settings.perimetr_database_url),
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args(settings.perimetr_database_url),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(Session, "after_begin")
def serialize_application_transactions(session, transaction, connection):
    if connection.dialect.name == "postgresql" and not transaction.nested:
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('perimetr-logical-state'))"))


@event.listens_for(Session, "after_commit")
def flush_committed_audit(session):
    if session.in_nested_transaction():
        return
    from .logs_service.service import write_audit_log
    for settings, event_record in session.info.pop("audit_file_events", []):
        try:
            write_audit_log(settings, event_record)
        except OSError:
            # The database audit is committed. Do not report the operation as failed
            # (and invite a duplicate mutation) because its secondary sink is full.
            import logging
            logging.getLogger("perimetr").error("Audit file sink unavailable; database event retained")


@event.listens_for(Session, "after_rollback")
def discard_uncommitted_audit(session):
    session.info.pop("audit_file_events", None)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
