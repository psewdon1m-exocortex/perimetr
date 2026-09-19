from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api_service.app import create_app
from app.database import Base, get_db
from app.models import SystemSetting, SessionLease
from app.operator_settings import ensure_preferences
from app.security import hash_password
from app.settings import Settings, get_settings
from app import services


@pytest.fixture
def operator_app(monkeypatch):
    database = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(database)
    application = create_app()
    def db_dependency():
        with Session(database, expire_on_commit=False) as session:
            yield session
    application.dependency_overrides[get_db] = db_dependency
    yield application, database
    database.dispose()


def sign_in(client, key):
    response = client.post("/v1/auth/direct", json={"access_key": key})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response


@pytest.mark.parametrize("key", ["x", "  literal value  ", "\t雪\n+'$ /?#", "perimetr-entry-password", "a" * 4096])
def test_access_key_is_exact_and_has_no_composition_policy(operator_app, monkeypatch, key):
    application, database = operator_app
    monkeypatch.setenv("PERIMETR_ACCESS_KEY", key)
    get_settings.cache_clear()
    client = TestClient(application)
    sign_in(client, key)
    assert client.post("/v1/auth/direct", json={"access_key": key + "x"}).status_code == 401
    assert client.post("/v1/auth/direct", json={"access_key": ""}).status_code == 401
    assert client.post("/v1/auth/direct", json={"username": "admin", "password": key}).status_code == 422
    with Session(database) as db:
        value = db.scalar(select(SystemSetting)).value
        assert set(value["auth"]) == {"access_key_hash"}
    get_settings.cache_clear()


def test_unconfigured_access_key_fails_without_generating_one():
    database = create_engine("sqlite://")
    Base.metadata.create_all(database)
    with Session(database) as db:
        with pytest.raises(RuntimeError, match="required"):
            ensure_preferences(db, Settings(_env_file=None, perimetr_access_key=None))
    database.dispose()


def test_corrupted_stored_verifier_cannot_fall_back_to_environment(operator_app):
    _, database = operator_app
    with Session(database) as db:
        db.add(SystemSetting(scope='perimetr', key='perimetr.preferences', value={'auth': {'access_key_hash':'corrupt'}})); db.commit()
        with pytest.raises(RuntimeError, match='instead of reseeding'):
            ensure_preferences(db, Settings(_env_file=None, perimetr_access_key='new environment key'))


def test_rotation_revokes_other_sessions_and_rotates_current_csrf(operator_app):
    application, database = operator_app
    first, other = TestClient(application), TestClient(application)
    sign_in(first, "perimetr-entry-password")
    sign_in(other, "perimetr-entry-password")
    old_csrf = first.headers["X-CSRF-Token"]
    payload = {"current_key": "perimetr-entry-password", "new_key": " 雪\t", "confirm_key": " 雪\t"}
    result = first.post("/v1/settings/access-key", json=payload)
    assert result.status_code == 200
    assert result.json()["csrf_token"] != old_csrf
    assert other.get("/v1/status").status_code == 403
    first.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    assert first.get("/v1/status").status_code == 200
    sign_in(TestClient(application), " 雪\t")
    assert TestClient(application).post("/v1/auth/direct", json={"access_key": "perimetr-entry-password"}).status_code == 401
    assert first.post("/v1/auth/logout").status_code == 200
    with Session(database) as db:
        sessions = db.scalars(select(SessionLease)).all()
        assert sum(item.status == "active" for item in sessions) == 1


def test_csrf_origin_logout_and_public_metadata(operator_app):
    application, _ = operator_app
    client = TestClient(application)
    sign_in(client, "perimetr-entry-password")
    payload = {"name": "should not be created"}
    token = client.headers.pop("X-CSRF-Token")
    assert client.post("/v1/objects", json=payload).status_code == 403
    client.headers["X-CSRF-Token"] = token
    assert client.post("/v1/objects", json=payload, headers={"Origin": "https://attacker.invalid"}).status_code == 403
    assert client.post("/v1/objects", json=payload).status_code == 201
    anonymous = TestClient(application)
    assert anonymous.get("/v1/public/status").status_code == 404
    assert anonymous.get("/v1/reachability").json() == {"reachable": True}
    for route in ("/", "/v1/status", "/v1/settings/preferences"):
        response = anonymous.get(route)
        assert response.headers["cache-control"] == "no-store, private"
    html = anonymous.get("/").text
    assert 'name="access_key"' in html and 'name="username"' not in html
    assert 'value="perimetr-entry-password"' not in html


def test_public_preferences_are_versioned_and_secret_free(operator_app):
    application, _ = operator_app
    client = TestClient(application)
    sign_in(client, "perimetr-entry-password")
    before = client.get("/v1/settings/preferences").json()
    assert "auth" not in before and "scrypt" not in str(before)
    update = {"expected_revision": before["revision"], "theme": {"accent": "#62ff8c"},
              "layout": {"settings": ["logs", "appearance", "security", "backup", "updates"]}}
    after = client.patch("/v1/settings/preferences", json=update)
    assert after.status_code == 200
    assert after.json()["theme"]["accent"] == "#62FF8C"
    assert client.patch("/v1/settings/preferences", json=update).status_code == 409
    assert client.patch("/v1/settings/preferences", json={"expected_revision": after.json()["revision"], "theme": {"accent": "#010101"}}).status_code == 422
    assert client.get("/v1/settings/preferences").json() == after.json()


def test_disk_uses_available_blocks_and_uptime_is_process_local(monkeypatch):
    monkeypatch.setattr(services.os, "statvfs", lambda path: SimpleNamespace(f_blocks=100, f_frsize=1024, f_bavail=40, f_bfree=80), raising=False)
    monkeypatch.setattr(services.time, "monotonic", lambda: services.PROCESS_STARTED + 12.8)
    result = services.build_system_metrics()
    assert result["disk_used_bytes"] == 60 * 1024
    assert result["disk_percent"] == 60
    assert result["uptime_seconds"] == 12
