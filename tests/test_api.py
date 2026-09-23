from __future__ import annotations

import os
import re
import hashlib
import json
import base64
import time
import shutil
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.orm import close_all_sessions


TEST_DB_PATH = Path(__file__).parent / "test_perimetr.db"
TEST_POD_BUNDLE_PATH = Path("/tmp/perimetr-pod-test-bundle")
TEST_POD_CACHE_PATH = Path("/tmp/perimetr-pod-test-cache")
os.environ["PERIMETR_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["PERIMETR_PUBLIC_URL"] = "http://localhost:18080"
os.environ["PERIMETR_SESSION_TTL_SEC"] = "3600"
os.environ["PERIMETR_POD_BUNDLE_SOURCE"] = "/tmp/perimetr-pod-test-bundle"

from app.api_service.app import create_app  # noqa: E402
from app.database import engine
from app.security import LoginRateLimiter
from app.services import now_utc
from app.pod_service import heartbeat_signing_bytes  # noqa: E402
from app.logs_service.service import trim_log_directory, trim_log_file  # noqa: E402


def setup_module() -> None:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    shutil.rmtree(TEST_POD_CACHE_PATH, ignore_errors=True)
    TEST_POD_BUNDLE_PATH.mkdir(parents=True, exist_ok=True)
    (TEST_POD_BUNDLE_PATH / "pod.exe").write_bytes(b"MZ-test-portable-pod")
    from app.database_migrations import upgrade_database
    upgrade_database(os.environ["PERIMETR_DATABASE_URL"])


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
        json={"access_key": "perimetr-entry-password"},
    )
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert response.json()["target"] == "perimetr"
    assert response.json()["transport"] == "direct"
    assert "session_key" not in response.json()


def snapshot_member(archive, name):
    from app.pod_service import _fernet
    from app.settings import get_settings
    table = name.removesuffix('.json')
    lines = archive.read(f'data/{table}.jsonl').splitlines()
    return json.dumps([json.loads(_fernet(get_settings()).decrypt(line)) for line in lines]).encode()


def restore_archive(client, data):
    response = client.post('/v1/backups/import', content=data, headers={
        'Content-Type': 'application/zip', 'X-Backup-Sha256': hashlib.sha256(data).hexdigest(), 'X-Confirm-Replace': 'true'})
    if response.status_code == 200:
        login(client)
    return response


def test_direct_login_and_core_shell() -> None:
    with TestClient(create_app()) as client:
        assert client.get('/robots.txt').text == 'User-agent: *\nDisallow: /\n'
        for path in ['/docs', '/redoc', '/openapi.json', '/.env', '/.git/config', '/wp-admin', '/v1/public/status']:
            assert client.get(path).status_code == 404
        assert client.get('/assets/core.js').status_code == 403
        entry = client.get('/')
        assert 'name="access_key"' in entry.text and 'name="username"' not in entry.text
        assert 'no-store' in entry.headers['cache-control']
        assert client.get('/v1/health').json()['service'] == 'perimetr'
        assert client.get('/v1/health', headers={'X-Forwarded-For': '203.0.113.10'}).status_code == 404
        login(client)
        shell = client.get('/')
        for feature in ['Dashboard', 'Overview', 'Correlation Map', 'Documentation', 'Appearance', 'Security', 'Backup', 'Updates', 'Logs', 'Create Pod']:
            assert feature in shell.text
        assert client.get('/assets/core.js').status_code == 200
        assert client.get('/assets/operator.js').status_code == 200
        assert client.get('/v1/settings/runtime').json()['audit_limits']['max_entries'] == 10000


def test_direct_login_rate_limit_and_password_rotation() -> None:
    app = create_app()
    app.state.login_rate_limiter = LoginRateLimiter(max_attempts=2, window_seconds=600, base_delay_seconds=0)
    with TestClient(app) as client:
        for _ in range(2):
            assert client.post('/v1/auth/direct', json={'access_key': 'wrong'}).status_code == 401
        response = client.post('/v1/auth/direct', json={'access_key': 'perimetr-entry-password'})
        assert response.status_code == 429 and int(response.headers['retry-after']) >= 1
    with TestClient(create_app()) as client:
        login(client)
        for old, new in [('perimetr-entry-password', ' x '), (' x ', 'perimetr-entry-password')]:
            changed = client.post('/v1/settings/access-key', json={'current_key': old, 'new_key': new, 'confirm_key': new})
            assert changed.status_code == 200
            client.headers['X-CSRF-Token'] = changed.json()['csrf_token']
            assert client.get('/v1/settings/runtime').status_code == 200


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
        archive = backup
        with ZipFile(BytesIO(archive.content)) as bundle:
            assert b"perimetr.correlation_map" in snapshot_member(bundle, "system_settings.json")
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
        archive = backup
        with ZipFile(BytesIO(archive.content)) as bundle:
            assert b"perimetr.overview_blocks" in snapshot_member(bundle, "system_settings.json")

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
        metrics = client.get('/v1/system/metrics')
        assert metrics.status_code == 200 and metrics.json()['uptime_seconds'] >= 0
        assert 'cpu_cores' in metrics.json()
        archive = client.post('/v1/backups')
        assert archive.status_code == 200 and archive.headers['content-type'] == 'application/zip'
        assert client.get('/v1/backups').json() == []
        with ZipFile(BytesIO(archive.content)) as bundle:
            assert 'data/access_policies.jsonl' in bundle.namelist()
            assert 'data/session_leases.jsonl' not in bundle.namelist()
            settings = json.loads(snapshot_member(bundle, 'system_settings.json'))
            preferences = next(item for item in settings if item['key'] == 'perimetr.preferences')
            assert preferences['value']['auth']['access_key_hash'].startswith('scrypt$')
            assert b'perimetr-entry-password' not in archive.content
        assert restore_archive(client, archive.content).json()['restored'] is True
        assert client.post('/v1/audit/ui', json={'action':'appearance.theme.updated','target_type':'settings','target_id':'appearance'}).status_code == 200
        assert any(item['action']=='appearance.theme.updated' for item in client.get('/v1/logs/audit').json()['entries'])


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
        repeated_conversion = client.post(
            "/v1/subjects",
            json={"object_id": object_id, "runtime_type": "web"},
        )
        assert repeated_conversion.status_code == 201
        assert repeated_conversion.json()["id"] == subject_id
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

        provisioned = client.post(
            f"/v1/subjects/{subject_id}/pods",
            json={
                "login": "designer",
                "password": "designer-password",
                "confirm_password": "designer-password",
                "decoy_password": "designer-decoy-password",
                "confirm_decoy_password": "designer-decoy-password",
            },
        )
        assert provisioned.status_code == 201
        assert provisioned.json()["login"] == "designer"
        assert provisioned.json()["bundle_version"] == "0.1.3"
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
        assert enrolled.json()["access_mode"] == "primary"
        assert enrolled.json()["config"]["vless_connection"] == vless_uri
        assert client.post(f"/v1/pods/{pod_id}/verify", json={"username": "designer", "password": "wrong"}).status_code == 403
        primary_access = client.post(f"/v1/pods/{pod_id}/verify", json={"username": "designer", "password": "designer-password"})
        assert primary_access.status_code == 200
        assert primary_access.json()["access_mode"] == "primary"
        assert primary_access.json()["access_grant"]
        assert primary_access.json()["config"]["system_tabs"][0]["id"] == "site"
        decoy_access = client.post(f"/v1/pods/{pod_id}/verify", json={"username": "designer", "password": "designer-decoy-password"})
        assert decoy_access.status_code == 200
        assert decoy_access.json()["access_mode"] == "decoy"
        assert decoy_access.json()["access_grant"]
        assert decoy_access.json()["config"]["subject"] == {"id": "", "name": "Pod"}
        assert decoy_access.json()["config"]["system_tabs"] == []
        assert decoy_access.json()["config"]["default_navigation_url"] == "https://www.google.com/"
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
            # The client-provided mode is not authoritative; the signed grant is.
            "access_mode": "primary",
            "access_grant": decoy_access.json()["access_grant"],
            "temporary_tabs_count": 1,
        }
        # Heartbeats are time-bound; use a current timestamp after retaining deterministic field ordering.
        heartbeat["timestamp"] = now_utc().isoformat().replace("+00:00", "Z")
        heartbeat["signature"] = base64.b64encode(private_key.sign(heartbeat_signing_bytes(heartbeat), ec.ECDSA(hashes.SHA256()))).decode()
        accepted = client.post(f"/v1/pods/{pod_id}/heartbeat", json=heartbeat)
        assert accepted.status_code == 200
        assert accepted.json()["allowed"] is True
        assert accepted.json()["config"]["system_tabs"] == []
        assert accepted.json()["config"]["default_navigation_url"] == "https://www.google.com/"
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
        archive = backup
        with ZipFile(BytesIO(archive.content)) as bundle:
            assert "data/pod_provisioning_records.jsonl" in bundle.namelist()
            assert "data/pod_denylist.jsonl" in bundle.namelist()
            backed_up_subjects = json.loads(snapshot_member(bundle, "subjects.json"))
            backed_up_subject = next(item for item in backed_up_subjects if item["entity_id"] == subject_id)
            from app.pod_service import decrypt_secret
            from app.settings import get_settings
            assert "vless_connection" not in backed_up_subject
            assert decrypt_secret(backed_up_subject["vless_uri_encrypted"], get_settings()) == vless_uri
            assert base64.b64decode(backed_up_subject["image_data"]) == image_bytes
            backed_up_pods = json.loads(snapshot_member(bundle, "pods.json"))
            backed_up_pod = next(item for item in backed_up_pods if item["id"] == pod_id)
            assert backed_up_pod["login"] == "designer"
            assert backed_up_pod["password_hash"].startswith("pbkdf2_sha256$")
            assert backed_up_pod["decoy_password_hash"].startswith("pbkdf2_sha256$")
            assert b"designer-password-2" not in archive.content
            assert b"designer-decoy-password" not in archive.content


def test_entity_deletion_and_snapshot_id_compatibility() -> None:
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

        archive = client.post('/v1/backups').content
        deleted = client.delete(f"/v1/objects/{public_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"deleted": True, "id": public_id}
        assert f"object_{public_id}" not in client.get("/v1/correlation").json()["properties_by_block"]
        restored = restore_archive(client, archive)
        assert restored.status_code == 200
        assert any(item["id"] == public_id for item in client.get("/v1/objects").json())

        transformed = client.post("/v1/subjects", json={"object_id": public_id, "runtime_type": "web"})
        assert transformed.status_code == 201
        assert transformed.json()["pod_id"] is None
        subject_deleted = client.delete(f"/v1/subjects/{public_id}")
        assert subject_deleted.status_code == 200
        assert subject_deleted.json() == {"deleted": True, "id": public_id}
        assert client.get(f"/v1/subjects/{public_id}").status_code == 404


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
            assert {"manifest.json", "audit-events.jsonl", "errors.jsonl", "README.txt"} <= names
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["schema"] == "perimetr.logs.export.v2"
            assert manifest["error_count"] >= 1
            assert manifest["retention"]["max_total_bytes"] == 64 * 1024 * 1024
            errors = [json.loads(line) for line in archive.read("errors.jsonl").splitlines()]
            diagnostic = next(item for item in errors if item["target"] == "test:diagnostic-target")
            assert diagnostic["result"]["message"] == "Expanded diagnostic message"
            assert diagnostic["result"]["cause"] == "Synthetic test cause"
            assert diagnostic["result"]["stack_trace"] == "trace line 1\ntrace line 2"
            assert diagnostic["payload"]["request_id"] == "request-123"
            assert diagnostic["result"]["error_type"] == "TestFailure"
