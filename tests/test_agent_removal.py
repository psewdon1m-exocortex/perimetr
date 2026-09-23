"""Removal is enforced at the API, persistence and recovery boundaries."""
import io
import json
import os
from datetime import datetime, timezone
from uuid import uuid4
from zipfile import ZipFile

import pytest
import sqlalchemy as sa
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app.backup_service.snapshot import InvalidBackup, build_snapshot, preflight, signature
from app.database import Base
from app.database_migrations import alembic_config, upgrade_database
from app.security import hash_password
from test_operator_contract import operator_app, sign_in
from test_recovery_contract import snapshot_database


RETIRED_TABLES = {
    "agents", "agent_assignments", "agent_endpoints", "agent_certificates",
    "agent_capabilities", "agent_heartbeats", "agent_state_events", "agent_commands",
    "jobs", "job_events", "job_results", "approval_requests", "approval_decisions",
    "revocation_records", "certificate_denylist", "controller_identity",
}


def test_removed_routes_and_schemas_are_unavailable(operator_app):
    application, _ = operator_app
    schema = application.openapi()
    assert not any("/agents" in path or "/approvals" in path for path in schema["paths"])
    assert not any(name.startswith(("Agent", "Approval", "JobEvent")) for name in schema["components"]["schemas"])
    client = TestClient(application)
    paths = ["/v1/agents", "/v1/agents/register", "/v1/agents/a/heartbeat",
             "/v1/agents/a/commands", "/v1/agents/a/commands/pending",
             "/v1/agents/a/commands/c/status", "/api/agents/library",
             "/api/agents/enroll", "/api/agents/reorder", "/api/agents/a",
             "/api/agents/a/capabilities", "/api/agents/a/heartbeat",
             "/api/agents/a/jobs", "/api/agents/a/jobs/j", "/api/agents/a/jobs/j/events",
             "/api/agents/a/jobs/j/approve", "/api/agents/a/jobs/j/reject",
             "/api/agents/a/jobs/j/cancel", "/api/agents/a/approvals",
             "/api/agents/a/revoke", "/api/approvals/pending",
             "/api/blocks/laboratory/agents", "/api/blocks/s/agents/a",
             "/api/blocks/p/agents/reorder"]
    for authenticated in (False, True):
        if authenticated:
            sign_in(client, "perimetr-entry-password")
        for path in paths:
            for method in ("GET", "POST", "PATCH", "DELETE"):
                assert client.request(method, path).status_code == 404, (method, path)
    assert "agent_count" not in client.get("/v1/status").json()
    topology = client.get("/v1/topology").json()
    assert not {"agents", "agent_assignments", "agent_capabilities", "commands"} & topology.keys()
    assert client.get("/v1/pods").status_code == 200


def test_snapshot_excludes_removed_state_and_rejects_old_schema(snapshot_database):
    db, settings = snapshot_database
    data = build_snapshot(db, settings).getvalue()
    assert not RETIRED_TABLES & set(Base.metadata.tables)
    with ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["schema"] == "perimetr.full-backup.v4"
        assert manifest["database_revision"] == "0007"
        assert len(manifest["members"]) == 9
        assert not {f"data/{name}.jsonl" for name in RETIRED_TABLES} & set(archive.namelist())
        manifest.pop("authentication")
        manifest.update(schema="perimetr.full-backup.v3", database_revision="0006")
        manifest["authentication"] = signature(manifest, settings)
        old = io.BytesIO()
        with ZipFile(old, "w") as output:
            for name in archive.namelist():
                output.writestr(name, json.dumps(manifest) if name == "manifest.json" else archive.read(name))
    with pytest.raises(InvalidBackup, match="Unsupported backup schema"):
        preflight(old.getvalue(), settings)


@pytest.fixture(params=["sqlite", "postgresql"])
def migration_url(request, tmp_path):
    if request.param == "sqlite":
        yield f"sqlite:///{(tmp_path / 'retirement.sqlite').as_posix()}"
        return
    configured = os.getenv("PERIMETR_TEST_POSTGRES_URL")
    if not configured:
        pytest.skip("Dedicated disposable PostgreSQL not configured")
    url = make_url(configured).set(drivername="postgresql+psycopg")
    assert url.database == "perimetr_test", "Refusing a non-test database"
    engine = sa.create_engine(url)
    namespace = "removal_" + uuid4().hex
    try:
        with engine.begin() as connection:
            connection.execute(sa.schema.CreateSchema(namespace))
        scoped = url.update_query_dict({"options": f"-csearch_path={namespace}"})
        yield scoped.render_as_string(hide_password=False)
    finally:
        with engine.begin() as connection:
            connection.execute(sa.schema.DropSchema(namespace, cascade=True))
        engine.dispose()


def test_upgrade_removes_populated_control_plane_preserving_domain_data(migration_url):
    command.upgrade(alembic_config(migration_url), "0006")
    engine = sa.create_engine(migration_url)
    now = datetime.now(timezone.utc)
    verifier = hash_password("retained exact key")
    try:
        previous = sa.MetaData()
        previous.reflect(engine)
        with engine.begin() as connection:
            def insert(table_name, **values):
                table = previous.tables[table_name]
                row = {"id": table_name}
                for column in table.columns:
                    if column.name in row or column.nullable or column.server_default:
                        continue
                    kind = column.type.python_type
                    row[column.name] = {str: "fixture", int: 0, bool: False, dict: {}, datetime: now}[kind]
                row.update(values)
                connection.execute(table.insert().values(**row))
            insert("objects", name="Keep Object", entity_id="KEEP_OBJECT_0001")
            insert("access_policies", rules={"allow": True})
            insert("subjects", name="Keep Subject", entity_id="KEEP_SUBJECT_001", object_id="objects", access_policy_id="access_policies")
            insert("pods", subject_id="subjects", name="Keep Pod")
            insert("agents", name="Retired Server")
            for name in RETIRED_TABLES - {"agents"}:
                insert(name, **({"agent_id": "agents"} if "agent_id" in previous.tables[name].c else {}))
            insert("session_leases", id="operator", agent_id=None, access_scope="perimetr", status="active")
            insert("session_leases", id="remote", agent_id="agents")
            insert("launch_authorizations", subject_id="subjects", pod_id="pods")
            insert("audit_events", action="agent.enrolled", target_id="agents")
            insert("system_settings", key="perimetr.preferences", value={
                "auth": {"access_key_hash": verifier}, "revision": 5,
                "layout": {"navigation": ["pods", "agents", "dashboard"], "settings": ["backup"]}})
        upgrade_database(migration_url)
        inspector = sa.inspect(engine)
        assert set(inspector.get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
        assert "agent_id" not in {column["name"] for column in inspector.get_columns("session_leases")}
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT name FROM objects")) == "Keep Object"
            assert connection.scalar(sa.text("SELECT object_id FROM subjects")) == "objects"
            assert connection.scalar(sa.text("SELECT subject_id FROM pods")) == "subjects"
            assert connection.scalar(sa.text("SELECT pod_id FROM launch_authorizations")) == "pods"
            assert connection.execute(sa.text("SELECT id FROM session_leases")).scalars().all() == ["operator"]
            assert connection.scalar(sa.text("SELECT action FROM audit_events")) == "agent.enrolled"
            value = connection.execute(sa.select(previous.tables["system_settings"].c.value)).scalar_one()
            assert value["auth"]["access_key_hash"] == verifier
            assert value["layout"] == {"navigation": ["pods", "dashboard"], "settings": ["backup"]}
            assert value["revision"] == 6
        command.check(alembic_config(migration_url))
        upgrade_database(migration_url)  # Restart at the new head is a no-op.
    finally:
        engine.dispose()
