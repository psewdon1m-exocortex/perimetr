from __future__ import annotations

import os
import re
import hashlib
import json
import base64
import time
import shutil
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from sqlalchemy.orm import close_all_sessions


TEST_DB_PATH = Path(__file__).parent / "test_perimetr.db"
TEST_POD_BUNDLE_PATH = Path("/tmp/perimetr-pod-test-bundle")
TEST_POD_CACHE_PATH = Path("/tmp/perimetr-pod-test-cache")
os.environ["PERIMETR_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["PERIMETR_PUBLIC_URL"] = "http://localhost:18080"
os.environ["PERIMETR_SESSION_TTL_SEC"] = "3600"
os.environ["PERIMETR_POD_BUNDLE_SOURCE"] = "/tmp/perimetr-pod-test-bundle"

from app.api_service.app import create_app  # noqa: E402
from app.api_service import app as api_app_module  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import SystemSetting  # noqa: E402
from app.security import LoginRateLimiter, is_password_hash  # noqa: E402
from app.services import now_utc, visible_agent_status  # noqa: E402
from app.pod_service import heartbeat_signing_bytes  # noqa: E402
from app.logs_service.service import trim_log_directory, trim_log_file  # noqa: E402


def setup_module() -> None:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    shutil.rmtree(TEST_POD_CACHE_PATH, ignore_errors=True)
    TEST_POD_BUNDLE_PATH.mkdir(parents=True, exist_ok=True)
    (TEST_POD_BUNDLE_PATH / "pod.exe").write_bytes(b"MZ-test-portable-pod")
    Base.metadata.create_all(bind=engine)


def teardown_module() -> None:
    close_all_sessions()
    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    shutil.rmtree(TEST_POD_BUNDLE_PATH, ignore_errors=True)
    shutil.rmtree(TEST_POD_CACHE_PATH, ignore_errors=True)


def login(client: TestClient) -> None:
    response = client.post(
        "/v1/auth/direct",
        json={"target": "perimetr", "username": "admin", "password": "perimetr-entry-password"},
    )
    assert response.status_code == 200
    assert response.json()["target"] == "perimetr"
    assert response.json()["transport"] == "direct"
    assert "session_key" not in response.json()


def test_direct_login_and_core_shell(monkeypatch) -> None:
    with TestClient(create_app()) as client:
        health = client.get("/v1/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok", "service": "perimetr"}

        entry = client.get("/")
        assert entry.status_code == 200
        assert 'aria-label="PERIMETR"' in entry.text
        assert 'placeholder="Login"' in entry.text
        assert 'placeholder="Password"' in entry.text
        assert 'id="signInButton" type="submit" disabled>Sign in' in entry.text
        assert "loginForm.requestSubmit(signInButton)" in entry.text
        assert 'font-size: clamp(48px, 14vw, 80px)' in entry.text
        assert "var(--dark) 90%, var(--light) 10%" in entry.text
        assert "var(--dark) 80%, var(--light) 20%" not in entry.text
        assert "--line-mid: color-mix(in srgb, var(--light) 75%, transparent)" in entry.text
        assert "border: 1px solid var(--line-outer)" in entry.text
        assert "form { border: 1px solid var(--line-mid)" not in entry.text

        denied = client.post(
            "/v1/auth/direct",
            json={"target": "perimetr", "username": "admin", "password": "wrong"},
        )
        assert denied.status_code == 401

        login(client)
        with SessionLocal() as db:
            preferences = db.scalar(
                select(SystemSetting).where(SystemSetting.key == "perimetr.preferences")
            )
            auth = dict((preferences.value if preferences else {}).get("auth") or {})
            assert "password" not in auth
            assert is_password_hash(str(auth.get("password_hash") or ""))
        shell = client.get("/")
        assert shell.status_code == 200
        assert "<title>perimetr</title>" in shell.text
        assert "Dashboard" in shell.text
        assert "Overview" in shell.text
        assert "Correlation Map" in shell.text
        assert "System Correlation" in shell.text
        assert "correlationCanvas" in shell.text
        assert "Center force" in shell.text
        assert "Repel force" in shell.text
        assert "Link distance" in shell.text
        assert "Text fade" in shell.text
        assert "const textOpacity = 1 - textFade" in shell.text
        assert 'class="graph-toolbar-toggle"' in shell.text
        assert 'class="correlation-toolbar collapsed"' in shell.text
        assert 'aria-expanded="false">Expand Controls' in shell.text
        assert "Expand Controls" in shell.text
        assert "text-transform: uppercase" in shell.text
        assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in shell.text
        assert "min-height: 815px" in shell.text
        assert ".fullscreen-body.entity-detail .block-interface { min-height: 658px; }" in shell.text
        assert "gap: 9px" in shell.text
        assert ".sidebar-footer form button { width: 140px; }" in shell.text
        assert 'data-view="documentation">Documentation</button>' in shell.text
        assert "Welcome To Perimetr" in shell.text
        assert 'id="documentationSearch"' in shell.text
        assert 'data-view="pods"><span>Pods</span><small>05</small></button>' in shell.text
        assert 'id="podsPageList"' in shell.text
        assert 'id="agentsPageSearch"' in shell.text
        assert 'id="podsPageSearch"' in shell.text
        assert 'id="propertiesPageSearch"' in shell.text
        assert "--sidebar-width: 242px" in shell.text
        assert "updateNavNumbers()" in shell.text
        assert "documentation-toc" not in shell.text
        assert '.sidebar-footer' in shell.text
        assert 'data-reset-graph-color="property"' in shell.text
        assert 'data-reset-graph-color="entity"' in shell.text
        assert "function graphNodeRadius" in shell.text
        assert 'target.closest("[data-expand]")' in shell.text
        assert 'data-metric-id="cpu"' in shell.text
        assert 'data-metric-id="uptime"' in shell.text
        assert 'id="systemUptime"' in shell.text
        assert 'data-overview-block="human_general"' in shell.text
        assert 'data-overview-block="turkey_global"' in shell.text
        assert 'data-overview-block="russia_sphere"' in shell.text
        assert 'data-overview-block="laboratory_block"' in shell.text
        assert 'data-overview-block="perimetr_block"' in shell.text
        assert 'target.closest("[data-overview-block]")' in shell.text
        for property_type in (
            "Plain Text",
            "Number",
            "Date",
            "Geo Location",
            "Service ID",
            "Document ID",
            "Device ID",
            "Phone Number",
            "Email Address",
            "Web Address",
            "Network Address",
            "Attachment",
        ):
            assert f">{property_type}</option>" in shell.text
        assert 'localStorage.setItem("perimetr.metricOrder"' in shell.text
        assert "Pods Settings" in shell.text
        assert "New Tab Policy" not in shell.text
        assert "Download Pod" not in shell.text
        assert 'download.click()' in shell.text
        assert 'id="newPodLogin"' in shell.text
        assert 'target.matches(".modal-backdrop.open")' in shell.text
        assert "--line-mid: color-mix(in srgb, var(--light) 75%, transparent)" in shell.text
        assert "--line-outer: var(--light)" in shell.text
        assert "var(--dark) 90%, var(--light) 10%" in shell.text
        assert "var(--dark) 80%, var(--light) 20%" not in shell.text
        assert "transform: translateX(-100%)" in shell.text
        assert "label: item.value || item.key" in shell.text
        assert 'contentEditable = "true"' in shell.text
        assert "item.slug" not in shell.text
        assert "Settings" in shell.text
        assert "Projects" in shell.text
        assert "window.PERIMETR_ACCESS" not in shell.text
        assert "Appearance" in shell.text
        assert "Security" in shell.text
        assert "LOGGER" in shell.text
        assert "Updater" in shell.text
        assert "Check for Updates" in shell.text
        assert "Retention limits are loading." in shell.text
        assert "Change Password" in shell.text
        assert "Import Backup" in shell.text
        assert "Download Latest" not in shell.text
        assert "applySafeHoverScale" in shell.text
        assert "modalDrag" in shell.text
        assert 'id="notificationStack"' in shell.text
        assert "function humanizeError" in shell.text
        assert "grid-auto-rows: max-content" in shell.text
        assert "Upload Image" in shell.text
        assert ".fullscreen-body::-webkit-scrollbar" in shell.text
        assert "Stable accepts production releases" in shell.text
        assert "Agent Nodes" in shell.text
        assert "Agent Library" in shell.text
        assert "Register Agent Node" in shell.text
        assert "Capability Catalog" in shell.text
        assert "Live execution" in shell.text
        assert "Server live view" in shell.text
        assert "Approval Required" in shell.text
        assert "Permanently delete this Agent Node from Perimetr" in shell.text
        assert 'data-view="agents"' in shell.text
        assert 'data-view="properties"' in shell.text
        assert "Delete Object" in shell.text
        assert "Delete Subject" in shell.text
        assert "Create Pod" in shell.text
        assert "showDropIndicator" in shell.text
        assert "drop-before" in shell.text
        assert "data-agent-library-index" in shell.text
        assert "data-library-property-index" in shell.text
        assert "Materialize</button>" not in shell.text
        assert "Authorize</button>" not in shell.text
        assert "Auto open and hide sidebar on mouse hover" in shell.text
        assert "The Agent Node and Sindri will remain installed on the server" in shell.text
        assert "Run In Test Mode" not in shell.text
        assert "Dry Run" not in shell.text
        assert "Shell Command" not in shell.text
        assert 'id="installUpdate"' in shell.text
        assert 'id="updaterAvailability"' in shell.text

        runtime = client.get("/v1/settings/runtime")
        assert runtime.status_code == 200
        assert runtime.json()["audit_limits"] == {
            "max_entries": 240,
            "retention_days": 30,
            "max_file_bytes": 5 * 1024 * 1024,
            "max_total_bytes": 64 * 1024 * 1024,
        }
        monkeypatch.setattr(
            api_app_module,
            "check_github_release",
            lambda **kwargs: {
                "service": "perimetr",
                "repository_url": kwargs["repository_url"],
                "installed_version": kwargs["current_version"],
                "available_version": "1.2.0",
                "update_available": True,
                "tag": "perimetr-v1.2.0",
                "release_url": "https://github.com/example/platform/releases/tag/perimetr-v1.2.0",
                "published_at": "2026-07-28T00:00:00Z",
                "prerelease": False,
                "apply_via": "updater",
                "backup_required": True,
            },
        )
        update_check = client.post("/v1/updater/check")
        assert update_check.status_code == 200
        assert update_check.json()["update_available"] is True
        assert update_check.json()["available_version"] == "1.2.0"

        monkeypatch.setattr(
            api_app_module.updater_client,
            "status",
            lambda _socket: {
                "installed": True,
                "available": True,
                "status": "ok",
                "service": "updater",
                "version": "0.1.0",
            },
        )
        updater_calls = []

        def fake_updater_request(socket_path, method, path, payload=None, timeout=10, control_token=""):
            updater_calls.append({
                "socket_path": socket_path,
                "method": method,
                "path": path,
                "payload": payload,
                "timeout": timeout,
                "control_token": control_token,
            })
            if method == "POST" and path == "/v1/updates":
                return {"id": "update-job-1", "state": "REQUESTED", "service": "perimetr"}
            return {"id": "update-job-1", "state": "COMPLETED", "service": "perimetr"}

        monkeypatch.setattr(api_app_module.updater_client, "request", fake_updater_request)
        status = client.get("/v1/updater/status")
        assert status.status_code == 200
        assert status.json()["available"] is True
        staged_backup = client.post("/v1/backups", json={"entity_type": "system"})
        assert staged_backup.status_code == 201
        assert client.get(f"/v1/backups/{staged_backup.json()['id']}").status_code == 200
        install = client.post(
            "/v1/updater/install",
            json={"version": "1.2.0", "backup_id": staged_backup.json()["id"]},
        )
        assert install.status_code == 202
        submitted = updater_calls[-1]
        assert submitted["path"] == "/v1/updates"
        assert submitted["payload"]["head_id"] == "perimetr"
        assert submitted["payload"]["service"] == "perimetr"
        assert submitted["payload"]["backup"]["sha256"] == hashlib.sha256(
            base64.b64decode(submitted["payload"]["backup"]["data_base64"])
        ).hexdigest()
        assert submitted["control_token"]
        assert client.get("/v1/updater/jobs/update-job-1").status_code == 200
        assert client.post("/v1/updater/jobs/update-job-1/rollback").status_code == 202


def test_direct_login_rate_limit_and_password_rotation() -> None:
    app = create_app()
    app.state.login_rate_limiter = LoginRateLimiter(
        max_attempts=2,
        window_seconds=600,
        base_delay_seconds=0,
    )
    with TestClient(app) as client:
        for _ in range(2):
            denied = client.post(
                "/v1/auth/direct",
                json={
                    "target": "perimetr",
                    "username": "admin",
                    "password": "wrong",
                },
            )
            assert denied.status_code == 401
        limited = client.post(
            "/v1/auth/direct",
            json={
                "target": "perimetr",
                "username": "admin",
                "password": "perimetr-entry-password",
            },
        )
        assert limited.status_code == 429
        assert int(limited.headers["retry-after"]) >= 1

    with TestClient(create_app()) as client:
        login(client)
        changed = client.post(
            "/v1/settings/password",
            json={
                "current_password": "perimetr-entry-password",
                "new_password": "strong-rotated-password",
                "confirm_password": "strong-rotated-password",
            },
        )
        assert changed.status_code == 200
        assert client.get("/v1/settings/runtime").status_code == 403
        assert client.post(
            "/v1/auth/direct",
            json={
                "target": "perimetr",
                "username": "admin",
                "password": "perimetr-entry-password",
            },
        ).status_code == 401
        assert client.post(
            "/v1/auth/direct",
            json={
                "target": "perimetr",
                "username": "admin",
                "password": "strong-rotated-password",
            },
        ).status_code == 200
        restored = client.post(
            "/v1/settings/password",
            json={
                "current_password": "strong-rotated-password",
                "new_password": "perimetr-entry-password",
                "confirm_password": "perimetr-entry-password",
            },
        )
        assert restored.status_code == 200


def test_stale_online_agent_is_reported_offline() -> None:
    agent = SimpleNamespace(
        enrollment_state="enrolled",
        status="ONLINE",
        last_heartbeat_at=now_utc() - timedelta(seconds=91),
    )
    assert visible_agent_status(agent) == "OFFLINE"


def test_correlation_state_and_percentage() -> None:
    with TestClient(create_app()) as client:
        login(client)
        entity_ids = ["human_general", "turkey_global", "russia_sphere", "laboratory_block", "perimetr_block"]
        entity_ids.extend(f"object_{item['id']}" for item in client.get("/v1/objects").json())
        entity_ids.extend(f"subject_{item['id']}" for item in client.get("/v1/subjects").json())
        property_item = {"id": "shared-property", "type": "plain_text", "key": "Shared", "value": "yes"}
        payload = {
            "descriptions_by_block": {},
            "properties_by_block": {entity_id: [property_item] for entity_id in entity_ids},
            "property_library": [property_item],
            "graph_settings": {"node_size": 8, "link_thickness": 2},
        }
        saved = client.put("/v1/correlation", json=payload)
        assert saved.status_code == 200
        assert saved.json()["correlation_percentage"] == 100.0
        loaded = client.get("/v1/correlation")
        assert loaded.status_code == 200
        assert loaded.json()["graph_settings"]["node_size"] == 8
        assert loaded.json()["property_library"][0]["id"] == "shared-property"
        backup = client.post("/v1/backups", json={"entity_type": "system"})
        archive = client.get(f"/v1/backups/{backup.json()['id']}")
        with ZipFile(BytesIO(archive.content)) as bundle:
            assert b"perimetr.correlation_map" in bundle.read("system_settings.json")
        assert client.put(
            "/v1/correlation",
            json={"descriptions_by_block": {}, "properties_by_block": {}, "property_library": [], "graph_settings": {}},
        ).status_code == 200


def test_overview_blocks_support_persistent_names_and_images() -> None:
    with TestClient(create_app()) as client:
        login(client)

        blocks = client.get("/v1/overview-blocks")
        assert blocks.status_code == 200
        assert {item["id"] for item in blocks.json()} == {
            "human_general",
            "turkey_global",
            "russia_sphere",
            "laboratory_block",
            "perimetr_block",
        }

        renamed = client.patch("/v1/overview-blocks/human_general", json={"name": "Human Context"})
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Human Context"

        image_bytes = b"\x89PNG\r\n\x1a\nperimetr-overview-image"
        uploaded = client.put(
            "/v1/overview-blocks/human_general/image",
            files={"image": ("overview.png", image_bytes, "image/png")},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["image_url"].startswith("/v1/overview-blocks/human_general/image?v=")
        image = client.get("/v1/overview-blocks/human_general/image")
        assert image.status_code == 200
        assert image.content == image_bytes

        backup = client.post("/v1/backups", json={"entity_type": "system"})
        archive = client.get(f"/v1/backups/{backup.json()['id']}")
        with ZipFile(BytesIO(archive.content)) as bundle:
            assert b"perimetr.overview_blocks" in bundle.read("system_settings.json")

        removed = client.delete("/v1/overview-blocks/human_general/image")
        assert removed.status_code == 200
        assert removed.json()["image_url"] is None
        assert client.get("/v1/overview-blocks/human_general/image").status_code == 404
        restored = client.patch(
            "/v1/overview-blocks/human_general",
            json={"name": "I as human in general"},
        )
        assert restored.status_code == 200


def test_metrics_and_backup_flow() -> None:
    with TestClient(create_app()) as client:
        login(client)

        metrics = client.get("/v1/system/metrics")
        assert metrics.status_code == 200
        assert set(metrics.json()) == {
            "cpu_percent",
            "ram_used_bytes",
            "ram_total_bytes",
            "ram_percent",
            "disk_used_bytes",
            "disk_total_bytes",
            "disk_percent",
            "uptime_seconds",
        }
        assert metrics.json()["uptime_seconds"] >= 0

        backup = client.post("/v1/backups", json={"entity_type": "system"})
        assert backup.status_code == 201
        backup_id = backup.json()["id"]

        backups = client.get("/v1/backups")
        assert backups.status_code == 200
        assert any(item["id"] == backup_id for item in backups.json())

        archive = client.get(f"/v1/backups/{backup_id}")
        assert archive.status_code == 200
        assert archive.headers["content-type"] == "application/zip"
        archive_path = Path(__file__).parent / "test-backup.zip"
        archive_path.write_bytes(archive.content)
        try:
            with ZipFile(archive_path) as bundle:
                assert "objects.json" in bundle.namelist()
                assert "subjects.json" in bundle.namelist()
                assert "pods.json" in bundle.namelist()
                assert "agents.json" in bundle.namelist()
                assert "agent_assignments.json" in bundle.namelist()
                assert "agent_capabilities.json" in bundle.namelist()
                assert "jobs.json" in bundle.namelist()
                assert "job_events.json" in bundle.namelist()
                assert "approval_requests.json" in bundle.namelist()
                assert "certificate_denylist.json" in bundle.namelist()
                assert "controller_identity.json" in bundle.namelist()
                assert "commands.json" in bundle.namelist()
                assert "recent_audit.json" in bundle.namelist()
                assert "logs.json" in bundle.namelist()
                assert "system_settings.json" in bundle.namelist()
                backed_up_settings = json.loads(bundle.read("system_settings.json"))
                preferences = next(
                    item for item in backed_up_settings
                    if item["key"] == "perimetr.preferences"
                )
                auth = preferences["value"]["auth"]
                assert "password" not in auth
                assert auth["password_hash"].startswith("scrypt$")
                assert b"perimetr-entry-password" not in archive.content
        finally:
            if archive_path.exists():
                archive_path.unlink()

        imported = client.post(
            "/v1/backups/import",
            files={"archive": ("backup.zip", archive.content, "application/zip")},
        )
        assert imported.status_code == 200
        assert imported.json()["restorable"] is True

        ui_audit = client.post(
            "/v1/audit/ui",
            json={"action": "appearance.theme.updated", "target_type": "settings", "target_id": "appearance"},
        )
        assert ui_audit.status_code == 200

        logs = client.get("/v1/logs/audit")
        assert logs.status_code == 200
        assert any(item["action"] == "appearance.theme.updated" for item in logs.json()["entries"])


def test_object_subject_web_runtime_flow() -> None:
    with TestClient(create_app()) as client:
        login(client)

        created_object = client.post(
            "/v1/objects",
            json={
                "name": "Mail Workspace",
                "kind": "workspace",
                "description": "Controlled web workspace",
                "tags": ["mail", "subject"],
            },
        )
        assert created_object.status_code == 201
        object_id = created_object.json()["id"]
        assert re.fullmatch(r"[A-HJ-NP-Z1-9]{16}", object_id)
        assert "status" not in created_object.json()
        assert "field" not in created_object.json()

        objects = client.get("/v1/objects")
        assert objects.status_code == 200
        assert any(item["id"] == object_id for item in objects.json())
        renamed_object = client.patch(f"/v1/objects/{object_id}", json={"name": "Mail Workspace Renamed"})
        assert renamed_object.status_code == 200
        assert renamed_object.json()["name"] == "Mail Workspace Renamed"
        property_item = {"id": "mail-property", "type": "plain_text", "key": "Phone", "value": "+0505"}
        assert client.put(
            "/v1/correlation",
            json={
                "descriptions_by_block": {f"object_{object_id}": "mail description"},
                "properties_by_block": {f"object_{object_id}": [property_item]},
                "property_library": [property_item],
                "graph_settings": {},
            },
        ).status_code == 200

        created_subject = client.post(
            "/v1/subjects",
            json={
                "object_id": object_id,
                "runtime_type": "web",
                "pod_spec": {
                    "host_id": "perimetr-core",
                    "path": f"/var/lib/perimetr/subjects/{object_id}",
                    "launcher_path": f"/subjects/{object_id}/web",
                    "is_portable": True,
                },
            },
        )
        assert created_subject.status_code == 201
        subject_id = created_subject.json()["id"]
        assert subject_id == object_id
        assert created_subject.json()["name"] == "Mail Workspace Renamed"
        assert "status" not in created_subject.json()
        assert "field" not in created_subject.json()
        assert all(item["id"] != object_id for item in client.get("/v1/objects").json())
        assert any(item["id"] == object_id for item in client.get("/v1/subjects").json())
        correlation = client.get("/v1/correlation").json()
        assert f"object_{object_id}" not in correlation["properties_by_block"]
        assert correlation["properties_by_block"][f"subject_{object_id}"][0]["value"] == "+0505"
        renamed_subject = client.patch(f"/v1/subjects/{subject_id}", json={"name": "Mail Subject"})
        assert renamed_subject.status_code == 200
        assert renamed_subject.json()["name"] == "Mail Subject"
        assert created_subject.json()["pod_id"]
        pod_id = created_subject.json()["pod_id"]
        pod = client.get(f"/v1/pods/{pod_id}")
        assert pod.status_code == 200
        assert pod.json()["subject_id"]
        assert client.post(
            f"/v1/pods/{pod_id}/heartbeat",
            json={"status": "active", "runtime_state": {"ready": True}, "observed_at": "2026-07-19T12:00:00Z"},
        ).status_code == 200

        materialized = client.post(f"/v1/subjects/{subject_id}/materialize")
        assert materialized.status_code == 200
        assert materialized.json()["primary_route"] == f"/subjects/{subject_id}/web"

        blocked_runtime = client.get(f"/subjects/{subject_id}/web")
        assert blocked_runtime.status_code == 403

        authorized = client.post(f"/v1/subjects/{subject_id}/authorize")
        assert authorized.status_code == 200
        assert authorized.json()["decision"] == "approved"
        assert authorized.json()["subject_id"] == subject_id

        runtime = client.get(f"/subjects/{subject_id}/web")
        assert runtime.status_code == 200
        assert "WEB SUBJECT" in runtime.text
        assert "Mail Subject" in runtime.text

        state = client.put(
            f"/v1/subjects/{subject_id}/state",
            json={"title": "Mail Workspace Runtime", "body": "persistent subject state"},
        )
        assert state.status_code == 200
        assert state.json()["state"]["body"] == "persistent subject state"

        runtime = client.get(f"/subjects/{subject_id}/web")
        assert runtime.status_code == 200
        assert "persistent subject state" in runtime.text

        revoked = client.post(f"/v1/subjects/{subject_id}/revoke")
        assert revoked.status_code == 200
        assert revoked.json()["decision"] == "revoked"

        blocked_runtime = client.get(f"/subjects/{subject_id}/web")
        assert blocked_runtime.status_code == 403


def test_pod_provisioning_identity_heartbeat_clone_and_revoke() -> None:
    with TestClient(create_app()) as client:
        login(client)
        object_id = client.post(
            "/v1/objects",
            json={"name": "Pod Subject", "kind": "workspace", "description": "", "tags": []},
        ).json()["id"]
        image_bytes = b"\x89PNG\r\n\x1a\nperimetr-test-image"
        uploaded_image = client.put(
            f"/v1/objects/{object_id}/image",
            files={"image": ("entity.png", image_bytes, "image/png")},
        )
        assert uploaded_image.status_code == 200
        assert uploaded_image.json()["image_url"].startswith(f"/v1/objects/{object_id}/image?v=")
        assert client.get(f"/v1/objects/{object_id}/image").content == image_bytes
        subject_id = client.post("/v1/subjects", json={"object_id": object_id, "runtime_type": "web"}).json()["id"]
        assert client.get(f"/v1/subjects/{subject_id}").json()["image_url"].startswith(f"/v1/subjects/{subject_id}/image?v=")
        vless_uri = "vless://22951f92-7722-47c3-8343-9bbf38404550@199.68.196.107:8021?encryption=none&security=reality&type=tcp&sni=example.com&fp=chrome&pbk=public&sid=abcd"
        configured = client.put(
            f"/v1/subjects/{subject_id}/pod-config",
            json={
                "vless_connection": vless_uri,
                "system_tabs": [{"id": "site", "title": "Site", "url": "https://example.com", "required": True, "position": 0}],
                "update_channel": "stable",
            },
        )
        assert configured.status_code == 200
        assert configured.json()["vless_connection"] == vless_uri
        assert configured.json()["network_profile_version"] == 2

        provisioned = client.post(f"/v1/subjects/{subject_id}/pods", json={"login": "designer", "password": "designer-password", "confirm_password": "designer-password"})
        assert provisioned.status_code == 201
        assert provisioned.json()["login"] == "designer"
        assert provisioned.json()["bundle_version"] == "0.1.2"
        assert re.fullmatch(r"[a-f0-9]{64}", provisioned.json()["artifact_sha256"])
        assert provisioned.json()["runtime_source"] in {"factory", "last-known-good"}
        provisioning_id = provisioned.json()["id"]
        downloaded = client.get(provisioned.json()["download_url"])
        assert downloaded.status_code == 200
        with ZipFile(BytesIO(downloaded.content)) as bundle:
            bootstrap = json.loads(bundle.read("state/config/bootstrap.json"))
            assert bootstrap["subject"]["id"] == subject_id
            assert "enrollment_token" in bootstrap
            assert bootstrap["application_name"] == "designer"
            assert bootstrap["executable_name"] == "designer.exe"
            assert bundle.read("designer.exe") == b"MZ-test-portable-pod"
            runtime_manifest = json.loads(bundle.read("pod_manifest.json"))
            assert runtime_manifest["version"] == provisioned.json()["bundle_version"]
            assert runtime_manifest["sha256"] == provisioned.json()["artifact_sha256"]
            assert bundle.read("state/assets/entity-icon.png") == image_bytes
            assert bundle.read("designer.ico").endswith(image_bytes)

        def identity():
            private_key = ec.generate_private_key(ec.SECP256R1())
            public_key = private_key.public_key()
            public_pem = public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
            der = public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
            fingerprint = "SHA256:" + hashlib.sha256(der).hexdigest().upper()
            return private_key, public_pem, fingerprint

        private_key, public_pem, fingerprint = identity()
        enrolled = client.post(
            "/v1/pods/enroll",
            json={
                "provisioning_id": provisioning_id,
                "enrollment_token": bootstrap["enrollment_token"],
                "username": "designer",
                "password": "designer-password",
                "name": "Designer Laptop",
                "public_key_pem": public_pem,
                "certificate_fingerprint": fingerprint,
                "device_binding_fingerprint": "SHA256:DEVICE-A",
                "host_id": "designer-pc",
                "pod_version": "0.1.0",
            },
        )
        assert enrolled.status_code == 201
        pod_id = enrolled.json()["pod_id"]
        assert enrolled.json()["config"]["vless_connection"] == vless_uri
        assert client.post(f"/v1/pods/{pod_id}/verify", json={"username": "designer", "password": "wrong"}).status_code == 403
        assert client.post(f"/v1/pods/{pod_id}/verify", json={"username": "designer", "password": "designer-password"}).status_code == 200
        changed_password = client.put(f"/v1/pods/{pod_id}/password", json={"new_password": "designer-password-2", "confirm_password": "designer-password-2"})
        assert changed_password.status_code == 200
        assert client.post(f"/v1/pods/{pod_id}/verify", json={"username": "designer", "password": "designer-password"}).status_code == 403
        assert client.post(f"/v1/pods/{pod_id}/verify", json={"username": "designer", "password": "designer-password-2"}).status_code == 200

        heartbeat = {
            "certificate_fingerprint": fingerprint,
            "sequence": 1,
            "timestamp": "2026-07-19T12:00:00Z",
            "pod_version": "0.1.0",
            "device_binding_fingerprint": "SHA256:DEVICE-A",
            "device_binding_status": "valid",
            "proxy_engine": "xray-core",
            "xray_version": "25.6.8",
            "network_status": "proxy_verified",
            "temporary_tabs_count": 1,
        }
        # Heartbeats are time-bound; use a current timestamp after retaining deterministic field ordering.
        heartbeat["timestamp"] = now_utc().isoformat().replace("+00:00", "Z")
        heartbeat["signature"] = base64.b64encode(private_key.sign(heartbeat_signing_bytes(heartbeat), ec.ECDSA(hashes.SHA256()))).decode()
        accepted = client.post(f"/v1/pods/{pod_id}/heartbeat", json=heartbeat)
        assert accepted.status_code == 200
        assert accepted.json()["allowed"] is True
        assert any(item["id"] == pod_id and item["subject_name"] == "Pod Subject" for item in client.get("/v1/pods").json())
        assert any(item["action"] == "pod.session.opened" and item["target_id"] == pod_id for item in client.get("/v1/audit").json())
        assert client.post(f"/v1/pods/{pod_id}/heartbeat", json=heartbeat).status_code == 409

        mismatch = {**heartbeat, "sequence": 2, "device_binding_fingerprint": "SHA256:DEVICE-B"}
        mismatch["signature"] = base64.b64encode(private_key.sign(heartbeat_signing_bytes(mismatch), ec.ECDSA(hashes.SHA256()))).decode()
        assert client.post(f"/v1/pods/{pod_id}/heartbeat", json=mismatch).status_code == 403

        clone_key, clone_public, clone_fingerprint = identity()
        clone = client.post(
            "/v1/pods/enroll",
            json={
                "clone_from_pod_id": pod_id,
                "username": "designer",
                "password": "designer-password-2",
                "name": "Designer Laptop Copy",
                "public_key_pem": clone_public,
                "certificate_fingerprint": clone_fingerprint,
                "device_binding_fingerprint": "SHA256:DEVICE-B",
                "host_id": "designer-pc-copy",
                "pod_version": "0.1.0",
            },
        )
        assert clone.status_code == 201
        assert clone.json()["pod_id"] != pod_id
        clone_id = clone.json()["pod_id"]
        assert client.delete(f"/v1/pods/{clone_id}").status_code == 200
        assert client.delete(f"/v1/pods/{clone_id}").status_code == 200
        status_payload = {"certificate_fingerprint": clone_fingerprint, "timestamp": now_utc().isoformat().replace("+00:00", "Z")}
        status_payload["signature"] = base64.b64encode(clone_key.sign(heartbeat_signing_bytes(status_payload), ec.ECDSA(hashes.SHA256()))).decode()
        deleted_status = client.post(f"/v1/pods/{clone_id}/status", json=status_payload)
        assert deleted_status.status_code == 200
        assert deleted_status.json() == {"deleted": True, "status": "revoked"}
        denied_clone = client.post(
            "/v1/pods/enroll",
            json={
                "clone_from_pod_id": pod_id,
                "username": "designer",
                "password": "designer-password-2",
                "name": "Revoked Copy",
                "public_key_pem": clone_public,
                "certificate_fingerprint": clone_fingerprint,
                "device_binding_fingerprint": "SHA256:DEVICE-C",
                "host_id": "designer-pc-copy-2",
                "pod_version": "0.1.0",
            },
        )
        assert denied_clone.status_code == 403
        listed = client.get(f"/v1/subjects/{subject_id}/pods").json()
        assert all(item["id"] != clone_id for item in listed["instances"])
        backup = client.post("/v1/backups", json={"entity_type": "system"})
        archive = client.get(f"/v1/backups/{backup.json()['id']}")
        with ZipFile(BytesIO(archive.content)) as bundle:
            assert "pod_provisioning_records.json" in bundle.namelist()
            assert "pod_denylist.json" in bundle.namelist()
            backed_up_subjects = json.loads(bundle.read("subjects.json"))
            backed_up_subject = next(item for item in backed_up_subjects if item["entity_id"] == subject_id)
            assert backed_up_subject["vless_connection"] == vless_uri
            assert base64.b64decode(backed_up_subject["image_data"]) == image_bytes
            backed_up_pods = json.loads(bundle.read("pods.json"))
            backed_up_pod = next(item for item in backed_up_pods if item["id"] == pod_id)
            assert backed_up_pod["login"] == "designer"
            assert backed_up_pod["password_hash"].startswith("pbkdf2_sha256$")
            assert b"designer-password-2" not in archive.content


def test_agent_command_queue_still_available() -> None:
    with TestClient(create_app()) as client:
        login(client)

        register = client.post(
            "/v1/agents/register",
            json={
                "name": "Core Agent",
                "agent_type": "agent",
                "host_id": "core-agent",
                "api_base_url": "http://agent.local",
                "identity_fingerprint": "fingerprint",
                "capabilities": ["status", "logs"],
            },
        )
        assert register.status_code == 201
        agent_id = register.json()["id"]

        command = client.post(
            f"/v1/agents/{agent_id}/commands",
            json={"command": "status", "target": {"service": "perimetr"}, "params": {}},
        )
        assert command.status_code == 201

        pending = client.get(f"/v1/agents/{agent_id}/commands/pending")
        assert pending.status_code == 200
        assert [item["id"] for item in pending.json()] == [command.json()["id"]]


def test_entity_deletion_and_legacy_backup_id_compatibility() -> None:
    with TestClient(create_app()) as client:
        login(client)
        created = client.post(
            "/v1/objects",
            json={"name": "Legacy Compatible", "kind": "workspace", "description": "", "tags": []},
        ).json()
        public_id = created["id"]
        prop = {"id": "delete-property", "type": "plain_text", "key": "Phone", "value": "+0505"}
        assert client.put("/v1/correlation", json={
            "descriptions_by_block": {f"object_{public_id}": "temporary"},
            "properties_by_block": {f"object_{public_id}": [prop]},
            "property_library": [prop],
            "graph_settings": {},
        }).status_code == 200

        backup = client.post("/v1/backups", json={"entity_type": "system"}).json()
        archive = client.get(f"/v1/backups/{backup['id']}").content
        source = ZipFile(BytesIO(archive))
        files = {name: source.read(name) for name in source.namelist() if name != "manifest.json"}
        object_rows = json.loads(files["objects.json"])
        target = next(item for item in object_rows if item["entity_id"] == public_id)
        target["slug"] = target.pop("entity_id")
        files["objects.json"] = json.dumps(object_rows, indent=2).encode()
        manifest = json.loads(source.read("manifest.json"))
        manifest["files"] = {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
        legacy_archive = BytesIO()
        with ZipFile(legacy_archive, "w", ZIP_DEFLATED) as converted:
            converted.writestr("manifest.json", json.dumps(manifest, indent=2))
            for name, content in files.items():
                converted.writestr(name, content)

        deleted = client.delete(f"/v1/objects/{public_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"deleted": True, "id": public_id}
        assert f"object_{public_id}" not in client.get("/v1/correlation").json()["properties_by_block"]
        restored = client.post("/v1/backups/import", files={"archive": ("legacy.zip", legacy_archive.getvalue(), "application/zip")})
        assert restored.status_code == 200
        assert any(item["id"] == public_id for item in client.get("/v1/objects").json())

        transformed = client.post("/v1/subjects", json={"object_id": public_id, "runtime_type": "web"})
        assert transformed.status_code == 201
        assert transformed.json()["pod_id"] is None
        subject_deleted = client.delete(f"/v1/subjects/{public_id}")
        assert subject_deleted.status_code == 200
        assert subject_deleted.json() == {"deleted": True, "id": public_id}
        assert client.get(f"/v1/subjects/{public_id}").status_code == 404


def test_agent_control_plane_registry_assignments_jobs_and_backup() -> None:
    with TestClient(create_app()) as client:
        login(client)

        enrolled = client.post(
            "/api/agents/enroll",
            json={
                "agent_id": "73b93a46-82c4-4f41-b919-9b89b0f48e42",
                "display_name": "Production Server",
                "domain": "node.example.net",
                "port": 7443,
                "identity_fingerprint": "SHA256:AB4219",
                "identity_certificate": "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----",
                "certificate_serial": "1001",
                "agent_version": "1.0.0",
                "sindri_version": "1.0.0",
                "sindri_protocol_version": "1",
                "capabilities": [
                    {"action": "system.info", "title": "System info", "group": "System", "risk": "read", "inputs": []},
                    {"action": "system.reboot", "title": "Reboot", "group": "System", "risk": "dangerous", "inputs": []},
                ],
            },
        )
        assert enrolled.status_code == 201
        agent_id = enrolled.json()["id"]
        assert enrolled.json()["assignment_count"] == 0

        library_empty = client.get("/api/agents/library")
        assert library_empty.status_code == 200
        assert any(item["id"] == agent_id for item in library_empty.json())

        assigned = client.post(
            "/api/blocks/laboratory/agents?block_type=laboratory",
            json={"agent_id": agent_id, "created_by": "operator"},
        )
        assert assigned.status_code == 201
        assert assigned.json()["agent"]["display_name"] == "Production Server"
        linked_agent = next(item for item in client.get("/api/agents/library").json() if item["id"] == agent_id)
        assert linked_agent["assignments"] == [{"block_type": "laboratory", "block_id": "laboratory", "name": "Laboratory"}]

        duplicate_limit = client.post(
            "/api/agents/enroll",
            json={
                "agent_id": "83b93a46-82c4-4f41-b919-9b89b0f48e43",
                "display_name": "Second Server",
                "domain": "node2.example.net",
                "port": 7444,
                "identity_fingerprint": "SHA256:SECOND",
            },
        )
        assert duplicate_limit.status_code == 201
        second_agent_id = duplicate_limit.json()["id"]
        blocked = client.post(
            "/api/blocks/laboratory/agents?block_type=laboratory",
            json={"agent_id": second_agent_id, "created_by": "operator"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["message"] == "AGENT_LIMIT_REACHED"

        library = client.get("/api/agents/library")
        assert library.status_code == 200
        assert any(item["id"] == agent_id for item in library.json())
        assert any(item["id"] == second_agent_id for item in library.json())
        reversed_library_ids = [item["id"] for item in reversed(library.json())]
        reordered_library = client.post("/api/agents/reorder", json={"ordered_agent_ids": reversed_library_ids})
        assert reordered_library.status_code == 200
        assert [item["id"] for item in client.get("/api/agents/library").json()] == reversed_library_ids

        heartbeat = client.post(
            f"/api/agents/{agent_id}/heartbeat",
            json={
                "protocol_version": "1",
                "agent_id": agent_id,
                "timestamp": "2026-07-10T18:30:00Z",
                "sequence": 1,
                "status": "healthy",
                "agent_version": "1.0.0",
                "sindri_version": "1.0.0",
                "sindri_protocol_version": "1",
                "hostname": "node-01",
                "boot_id": "boot-1",
                "queue_length": 0,
                "resources": {"cpu_load_1m": 0.2},
                "listener": {"port": 7443, "status": "listening"},
            },
        )
        assert heartbeat.status_code == 200
        assert heartbeat.json()["status"] == "ONLINE"

        job = client.post(
            f"/api/agents/{agent_id}/jobs",
            json={"action": "system.reboot", "inputs": {}, "created_by": "operator"},
        )
        assert job.status_code == 201
        job_id = job.json()["job_id"]
        assert "test" not in job.request.content.decode()

        approval_event = client.post(
            f"/api/agents/{agent_id}/jobs/{job_id}/events",
            json={
                "type": "job.approval_required",
                "status": "approval_required",
                "approval": {
                    "approval_id": "approval-1",
                    "plan_hash": "sha256:plan",
                    "risk": "dangerous",
                    "warning": "The server will reboot.",
                    "plan": [{"id": "reboot", "name": "Request system reboot"}],
                    "expires_at": "2026-07-10T19:00:00Z",
                },
            },
        )
        assert approval_event.status_code == 200

        approvals = client.get(f"/api/agents/{agent_id}/approvals")
        assert approvals.status_code == 200
        assert approvals.json()[0]["approval_id"] == "approval-1"

        approved = client.post(
            f"/api/agents/{agent_id}/jobs/{job_id}/approve",
            json={"approval_id": "approval-1", "plan_hash": "sha256:plan", "decided_by": "operator"},
        )
        assert approved.status_code == 200
        assert approved.json()["decision"] == "approved"

        events = client.get(f"/api/agents/{agent_id}/jobs/{job_id}/events")
        assert events.status_code == 200
        assert [item["sequence"] for item in events.json()] == sorted(item["sequence"] for item in events.json())
        assert any(item["event_type"] == "job.approved" for item in events.json())

        removed = client.delete(f"/api/blocks/laboratory/agents/{agent_id}?block_type=laboratory")
        assert removed.status_code == 200
        assert removed.json() == {"removed": True, "revoke_sent": False}

        library_after_remove = client.get("/api/agents/library")
        assert library_after_remove.status_code == 200
        assert any(item["id"] == agent_id for item in library_after_remove.json())

        detached = client.get(f"/api/agents/{agent_id}")
        assert detached.status_code == 200
        assert detached.json()["status"] == "DETACHED"

        backup = client.post("/v1/backups", json={"entity_type": "system"})
        assert backup.status_code == 201
        archive = client.get(f"/v1/backups/{backup.json()['id']}")
        assert archive.status_code == 200
        archive_path = Path(__file__).parent / "test-agent-backup.zip"
        archive_path.write_bytes(archive.content)
        try:
            with ZipFile(archive_path) as bundle:
                assert "agent_assignments.json" in bundle.namelist()
                assert "jobs.json" in bundle.namelist()
                assert "job_events.json" in bundle.namelist()
                assert "approval_requests.json" in bundle.namelist()
        finally:
            if archive_path.exists():
                archive_path.unlink()


def test_remote_agent_enrollment_dispatch_and_approval_are_forwarded(monkeypatch) -> None:
    agent_id = "remote-agent-dispatch-1"
    fingerprint = "SHA256:REMOTE:AGENT:1"
    calls: dict[str, list[dict]] = {"enroll": [], "dispatch": [], "decision": []}

    def fake_enroll(**kwargs):
        calls["enroll"].append(kwargs)
        now = now_utc()
        return {
            "status": "enrolled",
            "agent_id": agent_id,
            "identity_certificate_pem": "verified-agent-certificate",
            "fingerprint_sha256": fingerprint,
                "certificate_serial": "remote-serial-1",
                "certificate_valid_not_before": now - timedelta(minutes=1),
                "certificate_valid_not_after": now + timedelta(days=30),
                "agent_version": "1.0.0-test",
                "sindri_version": "1.0.0-test",
                "sindri_protocol_version": "1",
                "capabilities": [
                    {
                        "action": "system.reboot",
                        "title": "Reboot",
                        "group": "System",
                        "risk": "dangerous",
                        "inputs": [],
                        "available": True,
                    },
                    {
                        "action": "user.password_change",
                        "title": "Change password",
                        "group": "Users",
                        "risk": "change",
                        "inputs": [
                            {"name": "username", "type": "string", "required": True},
                            {
                                "name": "password",
                                "type": "secret",
                                "required": True,
                                "secret": True,
                            },
                        ],
                        "available": True,
                    },
                ],
            }

    def fake_dispatch(**kwargs):
        calls["dispatch"].append(kwargs)
        return {"status": "accepted"}

    def fake_decision(**kwargs):
        calls["decision"].append(kwargs)
        return {"status": "accepted"}

    monkeypatch.setattr(api_app_module, "enroll_remote_agent", fake_enroll)
    monkeypatch.setattr(api_app_module, "dispatch_remote_agent_job", fake_dispatch)
    monkeypatch.setattr(api_app_module, "decide_remote_agent_job", fake_decision)

    with TestClient(create_app()) as client:
        login(client)
        enrolled = client.post(
            "/api/agents/enroll",
            json={
                "agent_id": agent_id,
                "display_name": "Remote Agent",
                "domain": "agent.remote.example",
                "port": 7443,
                "api_base_url": "https://agent.remote.example:7443",
                "identity_fingerprint": fingerprint,
                "enrollment_token": "one-time-token",
                "capabilities": [
                    {
                        "action": "system.reboot",
                        "title": "Reboot",
                        "group": "System",
                        "risk": "dangerous",
                        "inputs": [],
                    }
                ],
            },
        )
        assert enrolled.status_code == 201
        assert calls["enroll"][0]["heartbeat_endpoint"].endswith(
            f"/api/agents/{agent_id}/heartbeat"
        )
        capabilities = client.get(f"/api/agents/{agent_id}/capabilities")
        assert capabilities.status_code == 200
        assert {item["action"] for item in capabilities.json()["items"]} == {
            "system.reboot",
            "user.password_change",
        }

        heartbeat_payload = {
            "protocol_version": "1",
            "agent_id": agent_id,
            "timestamp": "2026-07-27T12:00:00Z",
            "sequence": 1,
            "status": "healthy",
        }
        assert client.post(
            f"/api/agents/{agent_id}/heartbeat",
            json=heartbeat_payload,
        ).status_code == 403
        heartbeat = client.post(
            f"/api/agents/{agent_id}/heartbeat",
            headers={"X-Agent-Fingerprint": fingerprint},
            json=heartbeat_payload,
        )
        assert heartbeat.status_code == 200

        secret_job = client.post(
            f"/api/agents/{agent_id}/jobs",
            json={
                "action": "user.password_change",
                "inputs": {
                    "username": "managed-user",
                    "password": "very-secret-password",
                },
                "created_by": "operator",
            },
        )
        assert secret_job.status_code == 201
        assert secret_job.json()["inputs"]["password"] == "[redacted]"
        assert calls["dispatch"][0]["inputs"]["password"] == "very-secret-password"

        created = client.post(
            f"/api/agents/{agent_id}/jobs",
            json={"action": "system.reboot", "inputs": {}, "created_by": "operator"},
        )
        assert created.status_code == 201
        job_id = created.json()["job_id"]
        assert calls["dispatch"][1]["job_id"] == job_id
        assert calls["dispatch"][1]["action"] == "system.reboot"

        approval_event = client.post(
            f"/api/agents/{agent_id}/jobs/{job_id}/events",
            headers={"X-Agent-Fingerprint": fingerprint},
            json={
                "type": "job.approval_required",
                "status": "approval_required",
                "approval": {
                    "approval_id": "approval-remote-1",
                    "plan_hash": "sha256:remote-plan",
                    "risk": "dangerous",
                    "plan": [{"id": "reboot", "name": "Request system reboot"}],
                },
            },
        )
        assert approval_event.status_code == 200
        pending = client.get("/api/approvals/pending")
        assert pending.status_code == 200
        current_approval = next(
            item
            for item in pending.json()
            if item["approval_id"] == "approval-remote-1"
        )
        assert current_approval["action"] == "system.reboot"
        assert current_approval["hostname"] == "agent.remote.example"
        approved = client.post(
            f"/api/agents/{agent_id}/jobs/{job_id}/approve",
            json={
                "approval_id": "approval-remote-1",
                "plan_hash": "sha256:remote-plan",
                "decided_by": "operator",
            },
        )
        assert approved.status_code == 200
        assert approved.json()["forward_to_agent"] is True
        assert calls["decision"][0]["job_id"] == job_id
        assert calls["decision"][0]["decision"] == "approved"


def test_agent_subject_multi_assignment_reorder_and_perimetr_limit() -> None:
    perimetr_block_id = "5f0b6d3d90f548a9a2f1d6e9cb7f3412"
    with TestClient(create_app()) as client:
        login(client)

        created_object = client.post(
            "/v1/objects",
            json={
                "name": "Agent Subject Workspace",
                "kind": "workspace",
                "description": "",
                "tags": [],
            },
        )
        assert created_object.status_code == 201
        created_subject = client.post(
            "/v1/subjects",
            json={"object_id": created_object.json()["id"], "runtime_type": "web"},
        )
        assert created_subject.status_code == 201
        subject_id = created_subject.json()["id"]

        agent_ids = [
            "93b93a46-82c4-4f41-b919-9b89b0f48e51",
            "93b93a46-82c4-4f41-b919-9b89b0f48e52",
        ]
        for index, agent_id in enumerate(agent_ids, start=1):
            enrolled = client.post(
                "/api/agents/enroll",
                json={
                    "agent_id": agent_id,
                    "display_name": f"Subject Agent {index}",
                    "domain": f"subject-agent-{index}.example.net",
                    "port": 7443 + index,
                    "identity_fingerprint": f"SHA256:SUBJECT:{index}",
                    "capabilities": [
                        {"action": "system.info", "title": "System info", "group": "System", "risk": "read", "inputs": []}
                    ],
                },
            )
            assert enrolled.status_code == 201

        for agent_id in agent_ids:
            assigned = client.post(
                f"/api/blocks/{subject_id}/agents?block_type=subject",
                json={"agent_id": agent_id, "created_by": "operator"},
            )
            assert assigned.status_code == 201

        subject_agents = client.get(f"/api/blocks/{subject_id}/agents?block_type=subject")
        assert subject_agents.status_code == 200
        assert [item["agent_id"] for item in subject_agents.json()] == agent_ids

        reordered = client.post(
            f"/api/blocks/{subject_id}/agents/reorder?block_type=subject",
            json={"ordered_agent_ids": list(reversed(agent_ids))},
        )
        assert reordered.status_code == 200
        assert reordered.json() == {"reordered": True}
        subject_agents = client.get(f"/api/blocks/{subject_id}/agents?block_type=subject")
        assert [item["agent_id"] for item in subject_agents.json()] == list(reversed(agent_ids))

        perimetr_first = client.post(
            f"/api/blocks/{perimetr_block_id}/agents?block_type=perimetr",
            json={"agent_id": agent_ids[0], "created_by": "operator"},
        )
        assert perimetr_first.status_code == 201
        perimetr_second = client.post(
            f"/api/blocks/{perimetr_block_id}/agents?block_type=perimetr",
            json={"agent_id": agent_ids[1], "created_by": "operator"},
        )
        assert perimetr_second.status_code == 409
        assert perimetr_second.json()["error"]["message"] == "AGENT_LIMIT_REACHED"

        removed_subject_assignment = client.delete(f"/api/blocks/{subject_id}/agents/{agent_ids[0]}?block_type=subject")
        assert removed_subject_assignment.status_code == 200
        library = client.get("/api/agents/library")
        assert any(item["id"] == agent_ids[0] for item in library.json())

        removed_perimetr_assignment = client.delete(
            f"/api/blocks/{perimetr_block_id}/agents/{agent_ids[0]}?block_type=perimetr"
        )
        assert removed_perimetr_assignment.status_code == 200
        library = client.get("/api/agents/library")
        assert any(item["id"] == agent_ids[0] for item in library.json())


def test_agent_restore_resumes_heartbeat_and_revoked_identity_cannot_rotate_back() -> None:
    agent_id = "a3b93a46-82c4-4f41-b919-9b89b0f48e61"
    with TestClient(create_app()) as client:
        login(client)
        enrollment = {
            "agent_id": agent_id,
            "display_name": "Restore Agent",
            "domain": "restore-agent.example.net",
            "port": 7443,
            "identity_fingerprint": "SHA256:RESTORE:ORIGINAL",
            "identity_certificate": "certificate-original",
            "certificate_serial": "restore-1001",
        }
        assert client.post("/api/agents/enroll", json=enrollment).status_code == 201
        assert client.post(
            "/api/blocks/laboratory/agents?block_type=laboratory",
            json={"agent_id": agent_id, "created_by": "operator"},
        ).status_code == 201

        heartbeat = {
            "protocol_version": "1",
            "agent_id": agent_id,
            "timestamp": "2026-07-12T12:00:00Z",
            "sequence": 1,
            "status": "healthy",
            "agent_version": "1.0.0",
            "sindri_protocol_version": "1",
            "hostname": "restore-agent",
            "queue_length": 0,
        }
        assert client.post(f"/api/agents/{agent_id}/heartbeat", json=heartbeat).status_code == 200

        backup = client.post("/v1/backups", json={"entity_type": "system"})
        archive = client.get(f"/v1/backups/{backup.json()['id']}")
        assert archive.status_code == 200
        source_buffer = BytesIO(archive.content)
        corrupt_buffer = BytesIO()
        with ZipFile(source_buffer) as source, ZipFile(corrupt_buffer, "w", ZIP_DEFLATED) as corrupt:
            for name in source.namelist():
                corrupt.writestr(name, b"[]" if name == "agents.json" else source.read(name))
        rejected = client.post(
            "/v1/backups/import",
            files={"archive": ("corrupt.zip", corrupt_buffer.getvalue(), "application/zip")},
        )
        assert rejected.status_code == 400
        archive_path = Path(__file__).parent / "test-restore-agent.zip"
        archive_path.write_bytes(archive.content)
        try:
            with ZipFile(archive_path) as bundle:
                for required in ["agent_certificates.json", "agent_endpoints.json", "agent_heartbeats.json", "agent_state_events.json", "certificate_denylist.json", "controller_identity.json"]:
                    assert required in bundle.namelist()
        finally:
            archive_path.unlink(missing_ok=True)

        assert client.delete(f"/api/blocks/laboratory/agents/{agent_id}?block_type=laboratory").status_code == 200
        assert client.patch(f"/api/agents/{agent_id}", json={"display_name": "Changed After Backup"}).status_code == 200
        restored = client.post(
            "/v1/backups/import",
            files={"archive": ("restore.zip", archive.content, "application/zip")},
        )
        assert restored.status_code == 200
        assignments = client.get("/api/blocks/laboratory/agents?block_type=laboratory").json()
        assert any(item["agent_id"] == agent_id and item["agent"]["display_name"] == "Restore Agent" for item in assignments)
        heartbeat["sequence"] = 2
        assert client.post(f"/api/agents/{agent_id}/heartbeat", json=heartbeat).status_code == 200

        revoke = client.post(f"/api/agents/{agent_id}/revoke")
        assert revoke.status_code == 200
        rotated = {**enrollment, "identity_fingerprint": "SHA256:RESTORE:ROTATED", "certificate_serial": "restore-1002"}
        assert client.post("/api/agents/enroll", json=rotated).status_code == 409
        assert client.post(f"/api/agents/{agent_id}/heartbeat", json=heartbeat).status_code == 403


def test_global_agent_delete_removes_assignments_and_deny_lists_identity() -> None:
    agent_id = "b3b93a46-82c4-4f41-b919-9b89b0f48e71"
    enrollment = {
        "agent_id": agent_id,
        "display_name": "Disposable Agent",
        "domain": "disposable.example.net",
        "port": 7443,
        "identity_fingerprint": "SHA256:DISPOSABLE",
        "certificate_serial": "delete-1001",
    }
    with TestClient(create_app()) as client:
        login(client)
        assert client.post("/api/agents/enroll", json=enrollment).status_code == 201
        object_id = client.post(
            "/v1/objects",
            json={"name": "Agent Delete Host", "kind": "workspace", "description": "", "tags": []},
        ).json()["id"]
        subject_id = client.post("/v1/subjects", json={"object_id": object_id, "runtime_type": "web"}).json()["id"]
        assert client.post(
            f"/api/blocks/{subject_id}/agents?block_type=subject",
            json={"agent_id": agent_id, "created_by": "operator"},
        ).status_code == 201
        renamed = client.patch(f"/api/agents/{agent_id}", json={"display_name": "Renamed Agent"})
        assert renamed.status_code == 200
        assert renamed.json()["display_name"] == "Renamed Agent"

        deleted = client.delete(f"/api/agents/{agent_id}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
        assert all(item["id"] != agent_id for item in client.get("/api/agents/library").json())
        assert client.get(f"/api/agents/{agent_id}").status_code == 404
        assert client.get(f"/api/blocks/{subject_id}/agents?block_type=subject").json() == []
        assert client.post("/api/agents/enroll", json=enrollment).status_code == 409


def test_logger_retention_limits_lines_age_and_total_size(tmp_path: Path) -> None:
    active = tmp_path / "active.jsonl"
    active.write_bytes(b"first\nsecond\nthird\n")
    trim_log_file(active, max_lines=2, max_bytes=32)
    assert active.read_bytes() == b"second\nthird\n"

    oversized = tmp_path / "oversized.jsonl"
    oversized.write_bytes(b"x" * 64 + b"\nsmall\n")
    trim_log_file(oversized, max_lines=5, max_bytes=16)
    assert oversized.read_bytes() == b"small\n"

    old = tmp_path / "old.jsonl"
    old.write_bytes(b"old\n")
    old_timestamp = time.time() - (40 * 24 * 60 * 60)
    os.utime(old, (old_timestamp, old_timestamp))
    audit = tmp_path / "audit.jsonl"
    audit.write_bytes(b"a" * 12)
    entity = tmp_path / "object_R5Z1.jsonl"
    entity.write_bytes(b"b" * 12)
    trim_log_directory(tmp_path, retention_days=30, max_total_bytes=16)
    assert not old.exists()
    assert audit.exists()
    assert not entity.exists()


def test_logger_download_contains_diagnostics_manifest_and_detailed_errors() -> None:
    with TestClient(create_app()) as client:
        login(client)
        recorded = client.post(
            "/v1/audit/ui",
            json={
                "action": "test.operation.failed",
                "target_type": "test",
                "target_id": "diagnostic-target",
                "payload": {"request_id": "request-123", "method": "POST"},
                "result": {
                    "status": "failed",
                    "error_type": "TestFailure",
                    "message": "Expanded diagnostic message",
                    "cause": "Synthetic test cause",
                    "stack_trace": "trace line 1\ntrace line 2",
                },
            },
        )
        assert recorded.status_code == 200

        response = client.get("/v1/logs/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        with ZipFile(BytesIO(response.content)) as archive:
            names = set(archive.namelist())
            assert {"manifest.json", "audit-events.json", "errors.json", "README.txt"} <= names
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["schema"] == "perimetr.logs.export.v1"
            assert manifest["error_count"] >= 1
            assert manifest["retention"]["max_total_bytes"] == 64 * 1024 * 1024
            errors = json.loads(archive.read("errors.json"))
            diagnostic = next(item for item in errors if item["target"]["id"] == "diagnostic-target")
            assert diagnostic["message"] == "Expanded diagnostic message"
            assert diagnostic["cause"] == "Synthetic test cause"
            assert diagnostic["stack_trace"] == "trace line 1\ntrace line 2"
            assert diagnostic["request_id"] == "request-123"
            assert diagnostic["context"]["result"]["error_type"] == "TestFailure"
