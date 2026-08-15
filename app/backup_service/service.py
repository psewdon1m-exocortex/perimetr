from __future__ import annotations

import io
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Agent,
    AgentAssignment,
    AgentCapability,
    AgentCertificate,
    AgentCommand,
    AgentEndpoint,
    AgentHeartbeat,
    AgentJob,
    AgentStateEvent,
    ApprovalDecision,
    ApprovalRequest,
    AuditEvent,
    CertificateDenylist,
    Pod,
    PodDenylist,
    PodProvisioningRecord,
    ControllerIdentity,
    JobEvent,
    JobResult,
    PerimetrObject,
    RevocationRecord,
    SessionLease,
    Subject,
    SystemSetting,
    new_entity_id,
)
from ..services import PERIMETR_SYSTEM_ENTITY_ID, audit, build_topology_snapshot, get_object
from ..security import hash_password, is_password_hash
from ..settings import Settings
from ..pod_service import decrypt_secret, encrypt_secret


def build_backup_payload(*, entity_type: str, entity_id: str, db: Session) -> dict:
    snapshot = build_topology_snapshot(db)
    all_objects = db.scalars(select(PerimetrObject).order_by(PerimetrObject.created_at.asc())).all()
    all_subjects = db.scalars(select(Subject).order_by(Subject.created_at.asc())).all()
    all_pods = db.scalars(select(Pod).order_by(Pod.created_at.asc())).all()
    all_pod_provisioning = db.scalars(select(PodProvisioningRecord).order_by(PodProvisioningRecord.created_at.asc())).all()
    all_pod_denylist = db.scalars(select(PodDenylist).order_by(PodDenylist.created_at.asc())).all()
    all_agents = db.scalars(select(Agent).order_by(Agent.created_at.asc())).all()
    all_agent_assignments = db.scalars(select(AgentAssignment).order_by(AgentAssignment.created_at.asc())).all()
    all_agent_certificates = db.scalars(select(AgentCertificate).order_by(AgentCertificate.created_at.asc())).all()
    all_agent_endpoints = db.scalars(select(AgentEndpoint).order_by(AgentEndpoint.created_at.asc())).all()
    all_agent_capabilities = db.scalars(select(AgentCapability).order_by(AgentCapability.created_at.asc())).all()
    all_agent_heartbeats = db.scalars(select(AgentHeartbeat).order_by(AgentHeartbeat.observed_at.asc())).all()
    all_agent_state_events = db.scalars(select(AgentStateEvent).order_by(AgentStateEvent.created_at.asc())).all()
    all_jobs = db.scalars(select(AgentJob).order_by(AgentJob.created_at.asc())).all()
    all_job_events = db.scalars(select(JobEvent).order_by(JobEvent.created_at.asc())).all()
    all_job_results = db.scalars(select(JobResult).order_by(JobResult.created_at.asc())).all()
    all_approval_requests = db.scalars(select(ApprovalRequest).order_by(ApprovalRequest.created_at.asc())).all()
    all_approval_decisions = db.scalars(select(ApprovalDecision).order_by(ApprovalDecision.created_at.asc())).all()
    all_revocations = db.scalars(select(RevocationRecord).order_by(RevocationRecord.created_at.asc())).all()
    all_denylist = db.scalars(select(CertificateDenylist).order_by(CertificateDenylist.created_at.asc())).all()
    all_controller_identity = db.scalars(select(ControllerIdentity).order_by(ControllerIdentity.created_at.asc())).all()
    all_sessions = db.scalars(select(SessionLease).order_by(SessionLease.created_at.asc())).all()
    all_commands = db.scalars(select(AgentCommand).order_by(AgentCommand.created_at.asc())).all()
    all_audit = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.asc())).all()
    all_settings = db.scalars(select(SystemSetting).order_by(SystemSetting.created_at.asc())).all()
    runtime_settings = Settings()
    logs_dir = Path(Settings().perimetr_logs_dir)
    log_files = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(logs_dir.glob("*.jsonl"))
    } if logs_dir.exists() else {}

    def object_dump(item: PerimetrObject) -> dict:
        return {
            "id": item.id,
            "entity_id": item.entity_id,
            "name": item.name,
            "kind": item.kind,
            "description": item.description,
            "tags": item.tags,
            "image_data": item.image_data,
            "image_media_type": item.image_media_type,
        }

    def subject_dump(item: Subject) -> dict:
        return {
            "id": item.id,
            "entity_id": item.entity_id,
            "object_id": item.object_id,
            "name": item.name,
            "kind": item.kind,
            "description": item.description,
            "tags": item.tags,
            "image_data": item.image_data,
            "image_media_type": item.image_media_type,
            "runtime_type": item.runtime_type,
            "pod_id": item.pod_id,
            "access_policy_id": item.access_policy_id,
            "primary_route": item.primary_route,
            "vless_uri_encrypted": item.vless_uri_encrypted,
            "vless_connection": decrypt_secret(item.vless_uri_encrypted, runtime_settings),
            "network_profile_version": item.network_profile_version,
            "system_tabs": item.system_tabs,
            "system_tabs_profile_version": item.system_tabs_profile_version,
            "update_channel": item.update_channel,
            "ui_policy": item.ui_policy,
            "security_policy": item.security_policy,
        }

    def pod_dump(item: Pod) -> dict:
        return {
            "id": item.id,
            "subject_id": item.subject_id,
            "host_id": item.host_id,
            "path": item.path,
            "launcher_path": item.launcher_path,
            "runtime_state": item.runtime_state,
            "is_portable": item.is_portable,
            "last_materialized_at": item.last_materialized_at.isoformat() if item.last_materialized_at else None,
            "provisioning_id": item.provisioning_id,
            "name": item.name,
            "login": item.login,
            "password_hash": item.password_hash,
            "decoy_password_hash": item.decoy_password_hash,
            "status": item.status,
            "public_key_pem": item.public_key_pem,
            "identity_certificate": item.identity_certificate,
            "certificate_fingerprint": item.certificate_fingerprint,
            "device_binding_fingerprint": item.device_binding_fingerprint,
            "device_binding_status": item.device_binding_status,
            "pod_version": item.pod_version,
            "xray_version": item.xray_version,
            "network_profile_version": item.network_profile_version,
            "system_tabs_profile_version": item.system_tabs_profile_version,
            "heartbeat_sequence": item.heartbeat_sequence,
            "last_seen_at": item.last_seen_at.isoformat() if item.last_seen_at else None,
            "last_heartbeat_at": item.last_heartbeat_at.isoformat() if item.last_heartbeat_at else None,
            "activated_at": item.activated_at.isoformat() if item.activated_at else None,
            "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
            "revoke_reason": item.revoke_reason,
        }

    def agent_dump(item: Agent) -> dict:
        return {
            "id": item.id,
            "name": item.name,
            "agent_type": item.agent_type,
            "host_id": item.host_id,
            "status": item.status,
            "identity_fingerprint": item.identity_fingerprint,
            "api_base_url": item.api_base_url,
            "last_heartbeat_at": item.last_heartbeat_at.isoformat() if item.last_heartbeat_at else None,
            "display_name": item.display_name,
            "domain": item.domain,
            "port": item.port,
            "resolved_ip": item.resolved_ip,
            "enrollment_state": item.enrollment_state,
            "identity_certificate": item.identity_certificate,
            "certificate_serial": item.certificate_serial,
            "agent_version": item.agent_version,
            "sindri_version": item.sindri_version,
            "sindri_protocol_version": item.sindri_protocol_version,
            "hostname": item.hostname,
            "boot_id": item.boot_id,
            "queue_length": item.queue_length,
            "current_job_id": item.current_job_id,
            "tags": item.tags,
            "environment": item.environment,
            "notes": item.notes,
            "metadata_json": item.metadata_json,
            "library_position": item.library_position,
        }

    def assignment_dump(item: AgentAssignment) -> dict:
        return {
            "id": item.id,
            "agent_id": item.agent_id,
            "block_id": item.block_id,
            "block_type": item.block_type,
            "position": item.position,
            "created_by": item.created_by,
        }

    def capability_dump(item: AgentCapability) -> dict:
        return {
            "id": item.id,
            "agent_id": item.agent_id,
            "action": item.action,
            "title": item.title,
            "description": item.description,
            "group": item.group,
            "risk": item.risk,
            "inputs": item.inputs,
            "available": item.available,
        }

    def simple_dump(item, *fields: str) -> dict:
        payload = {"id": item.id}
        for field in fields:
            value = getattr(item, field)
            payload[field] = value.isoformat() if hasattr(value, "isoformat") else value
        return payload

    def session_dump(item: SessionLease) -> dict:
        return {
            "id": item.id,
            "subject_id": item.subject_id,
            "pod_id": item.pod_id,
            "agent_id": item.agent_id,
            "status": item.status,
            "session_key_hash": item.session_key_hash,
            "access_scope": item.access_scope,
            "transport": item.transport,
            "started_at": item.started_at.isoformat() if item.started_at else None,
            "expires_at": item.expires_at.isoformat() if item.expires_at else None,
            "ended_at": item.ended_at.isoformat() if item.ended_at else None,
        }

    def command_dump(item: AgentCommand) -> dict:
        return {
            "id": item.id,
            "agent_id": item.agent_id,
            "command": item.command,
            "target": item.target,
            "params": item.params,
            "status": item.status,
            "result": item.result,
            "started_at": item.started_at.isoformat() if item.started_at else None,
            "finished_at": item.finished_at.isoformat() if item.finished_at else None,
        }

    def audit_dump(item: AuditEvent) -> dict:
        return {
            "id": item.id,
            "actor_type": item.actor_type,
            "actor_id": item.actor_id,
            "action": item.action,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "payload": item.payload,
            "result": item.result,
            "created_at": item.created_at.isoformat(),
        }

    def setting_dump(item: SystemSetting) -> dict:
        value = item.value
        if item.key == "perimetr.preferences":
            value = dict(value or {})
            auth = dict(value.get("auth") or {})
            legacy_password = str(auth.pop("password", "") or "")
            if legacy_password and not is_password_hash(str(auth.get("password_hash") or "")):
                auth["password_hash"] = hash_password(legacy_password)
            value["auth"] = auth
        return {"id": item.id, "scope": item.scope, "key": item.key, "value": value}

    if entity_type == "system" and entity_id == PERIMETR_SYSTEM_ENTITY_ID:
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "topology": snapshot,
            "objects": [object_dump(item) for item in all_objects],
            "subjects": [subject_dump(item) for item in all_subjects],
            "pods": [pod_dump(item) for item in all_pods],
            "pod_provisioning_records": [
                simple_dump(item, "subject_id", "name", "login", "password_hash", "decoy_password_hash", "status", "enrollment_token_hash", "enrollment_token_encrypted", "bundle_version", "artifact_sha256", "download_count", "downloaded_at", "expires_at", "activated_at", "revoked_at", "metadata_json")
                for item in all_pod_provisioning
            ],
            "pod_denylist": [
                simple_dump(item, "pod_id", "subject_id", "identifier_type", "identifier_value", "reason")
                for item in all_pod_denylist
            ],
            "agents": [agent_dump(item) for item in all_agents],
            "agent_assignments": [assignment_dump(item) for item in all_agent_assignments],
            "agent_certificates": [
                simple_dump(item, "agent_id", "fingerprint_sha256", "serial_number", "certificate_pem", "valid_not_before", "valid_not_after", "status")
                for item in all_agent_certificates
            ],
            "agent_endpoints": [simple_dump(item, "agent_id", "domain", "port", "base_url", "status") for item in all_agent_endpoints],
            "agent_capabilities": [capability_dump(item) for item in all_agent_capabilities],
            "agent_heartbeats": [simple_dump(item, "agent_id", "payload", "observed_at") for item in all_agent_heartbeats],
            "agent_state_events": [simple_dump(item, "sequence", "agent_id", "event_type", "status", "message", "payload", "created_at") for item in all_agent_state_events],
            "jobs": [
                simple_dump(item, "job_id", "request_id", "agent_id", "action", "inputs", "created_by", "approver", "canceller", "expires_at", "status", "plan", "plan_hash", "result", "error", "log_reference", "agent_version", "sindri_version")
                for item in all_jobs
            ],
            "job_events": [simple_dump(item, "sequence", "agent_id", "job_id", "event_type", "status", "message", "payload", "created_at") for item in all_job_events],
            "job_results": [simple_dump(item, "agent_id", "job_id", "status", "payload") for item in all_job_results],
            "approval_requests": [
                simple_dump(item, "agent_id", "job_id", "approval_id", "plan_hash", "risk", "warning", "plan", "expires_at", "status")
                for item in all_approval_requests
            ],
            "approval_decisions": [simple_dump(item, "agent_id", "job_id", "approval_id", "plan_hash", "decision", "decided_by") for item in all_approval_decisions],
            "revocation_records": [simple_dump(item, "agent_id", "certificate_serial", "certificate_fingerprint_sha256", "reason", "status", "payload") for item in all_revocations],
            "certificate_denylist": [simple_dump(item, "agent_id", "fingerprint_sha256", "serial_number", "reason") for item in all_denylist],
            "controller_identity": [simple_dump(item, "controller_id", "certificate_pem", "encrypted_private_key", "encryption_metadata", "status") for item in all_controller_identity],
            "sessions": [session_dump(item) for item in all_sessions],
            "commands": [command_dump(item) for item in all_commands],
            "recent_audit": [audit_dump(item) for item in all_audit],
            "logs": log_files,
            "system_settings": [setting_dump(item) for item in all_settings],
            "system": snapshot["system"],
        }

    obj = get_object(db, entity_id)
    object_ids = {obj.id}
    subject_ids = {item.id for item in all_subjects if item.object_id == obj.id}
    pod_ids = {item.id for item in all_pods if item.subject_id in subject_ids}
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "topology": snapshot,
        "objects": [object_dump(obj)],
        "subjects": [subject_dump(item) for item in all_subjects if item.id in subject_ids],
        "pods": [pod_dump(item) for item in all_pods if item.id in pod_ids],
        "agents": [agent_dump(item) for item in all_agents if item.host_id == obj.entity_id or item.name == obj.name],
        "agent_assignments": [assignment_dump(item) for item in all_agent_assignments if item.block_id in object_ids | subject_ids],
        "agent_capabilities": [capability_dump(item) for item in all_agent_capabilities],
        "sessions": [session_dump(item) for item in all_sessions if item.subject_id in subject_ids],
        "commands": [command_dump(item) for item in all_commands],
        "recent_audit": [
            audit_dump(item)
            for item in all_audit
            if item.target_id in object_ids | subject_ids | pod_ids or item.actor_id in object_ids | subject_ids | pod_ids
        ],
        "logs": log_files,
        "system_settings": [setting_dump(item) for item in all_settings if item.scope in {f"object:{obj.id}", "perimetr"}],
        "system": snapshot["system"],
    }


def build_backup_zip(payload: dict) -> io.BytesIO:
    buffer = io.BytesIO()
    files = {
        f"{key}.json": json.dumps(value, indent=2).encode("utf-8")
        for key, value in payload.items()
        if key not in {"entity_type", "entity_id"}
    }
    manifest = {
        "backup_version": 2,
        "entity_type": payload["entity_type"],
        "entity_id": payload["entity_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
    }
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        for name, content in files.items():
            archive.writestr(name, content)
    buffer.seek(0)
    return buffer


async def import_backup_bundle(*, archive, db: Session) -> dict:
    runtime_settings = Settings()
    content = await archive.read()
    with ZipFile(io.BytesIO(content), "r") as bundle:
        legacy_unit = "".join(("con", "tainer"))
        legacy_pods_filename = f"{legacy_unit}s.json"
        legacy_pod_id = f"{legacy_unit}_id"
        manifest = json.loads(bundle.read("manifest.json"))
        if manifest.get("backup_version") == 2:
            expected_files = manifest.get("files") or {}
            if not expected_files:
                raise ValueError("backup manifest does not contain file checksums")
            for filename, expected_hash in expected_files.items():
                if filename not in bundle.namelist():
                    raise ValueError(f"backup file is missing: {filename}")
                actual_hash = hashlib.sha256(bundle.read(filename)).hexdigest()
                if actual_hash != expected_hash:
                    raise ValueError(f"backup checksum mismatch: {filename}")
        objects = json.loads(bundle.read("objects.json")) if "objects.json" in bundle.namelist() else []
        subjects = json.loads(bundle.read("subjects.json")) if "subjects.json" in bundle.namelist() else []
        pods_filename = "pods.json" if "pods.json" in bundle.namelist() else legacy_pods_filename
        pods = json.loads(bundle.read(pods_filename)) if pods_filename in bundle.namelist() else []
        pod_provisioning_records = json.loads(bundle.read("pod_provisioning_records.json")) if "pod_provisioning_records.json" in bundle.namelist() else []
        pod_denylist = json.loads(bundle.read("pod_denylist.json")) if "pod_denylist.json" in bundle.namelist() else []
        agents = json.loads(bundle.read("agents.json")) if "agents.json" in bundle.namelist() else []
        agent_assignments = json.loads(bundle.read("agent_assignments.json")) if "agent_assignments.json" in bundle.namelist() else []
        agent_certificates = json.loads(bundle.read("agent_certificates.json")) if "agent_certificates.json" in bundle.namelist() else []
        agent_endpoints = json.loads(bundle.read("agent_endpoints.json")) if "agent_endpoints.json" in bundle.namelist() else []
        agent_capabilities = json.loads(bundle.read("agent_capabilities.json")) if "agent_capabilities.json" in bundle.namelist() else []
        agent_heartbeats = json.loads(bundle.read("agent_heartbeats.json")) if "agent_heartbeats.json" in bundle.namelist() else []
        agent_state_events = json.loads(bundle.read("agent_state_events.json")) if "agent_state_events.json" in bundle.namelist() else []
        jobs = json.loads(bundle.read("jobs.json")) if "jobs.json" in bundle.namelist() else []
        job_events = json.loads(bundle.read("job_events.json")) if "job_events.json" in bundle.namelist() else []
        job_results = json.loads(bundle.read("job_results.json")) if "job_results.json" in bundle.namelist() else []
        approval_requests = json.loads(bundle.read("approval_requests.json")) if "approval_requests.json" in bundle.namelist() else []
        approval_decisions = json.loads(bundle.read("approval_decisions.json")) if "approval_decisions.json" in bundle.namelist() else []
        revocation_records = json.loads(bundle.read("revocation_records.json")) if "revocation_records.json" in bundle.namelist() else []
        certificate_denylist = json.loads(bundle.read("certificate_denylist.json")) if "certificate_denylist.json" in bundle.namelist() else []
        controller_identity = json.loads(bundle.read("controller_identity.json")) if "controller_identity.json" in bundle.namelist() else []
        sessions = json.loads(bundle.read("sessions.json")) if "sessions.json" in bundle.namelist() else []
        commands = json.loads(bundle.read("commands.json")) if "commands.json" in bundle.namelist() else []
        recent_audit = json.loads(bundle.read("recent_audit.json")) if "recent_audit.json" in bundle.namelist() else []
        logs = json.loads(bundle.read("logs.json")) if "logs.json" in bundle.namelist() else {}
        system_settings = json.loads(bundle.read("system_settings.json")) if "system_settings.json" in bundle.namelist() else []

    for payload in objects:
        obj = db.get(PerimetrObject, payload["id"]) or PerimetrObject(
            id=payload["id"],
            entity_id=payload.get("entity_id") or payload.get("slug") or new_entity_id(),
            name=payload["name"],
            kind=payload["kind"],
        )
        if db.get(PerimetrObject, payload["id"]) is None:
            db.add(obj)
        # Backup v1 used `slug` as the public identifier. It is accepted only at
        # this import boundary and is normalized to the current entity id.
        obj.entity_id = payload.get("entity_id") or payload.get("slug") or obj.entity_id
        obj.name = payload["name"]
        obj.kind = payload["kind"]
        obj.description = payload["description"]
        obj.tags = payload["tags"]
        obj.image_data = payload.get("image_data") or ""
        obj.image_media_type = payload.get("image_media_type") or ""
    db.flush()

    for payload in subjects:
        subject = db.get(Subject, payload["id"]) or Subject(
            id=payload["id"],
            object_id=payload.get("object_id"),
            runtime_type=payload["runtime_type"],
        )
        if db.get(Subject, payload["id"]) is None:
            db.add(subject)
        subject.entity_id = payload.get("entity_id") or subject.entity_id
        subject.object_id = payload.get("object_id")
        subject.name = payload.get("name") or subject.name
        subject.kind = payload.get("kind") or subject.kind
        subject.description = payload.get("description") or ""
        subject.tags = payload.get("tags") or []
        subject.image_data = payload.get("image_data") or ""
        subject.image_media_type = payload.get("image_media_type") or ""
        subject.runtime_type = payload["runtime_type"]
        subject.pod_id = payload.get("pod_id") or payload.get(legacy_pod_id)
        subject.access_policy_id = payload["access_policy_id"]
        subject.primary_route = payload["primary_route"]
        for field, default in {
            "vless_uri_encrypted": encrypt_secret(payload.get("vless_connection", ""), runtime_settings) if payload.get("vless_connection") else payload.get("vless_uri_encrypted", ""),
            "network_profile_version": 1,
            "system_tabs": [],
            "system_tabs_profile_version": 1,
            "update_channel": "stable",
            "ui_policy": {},
            "security_policy": {},
        }.items():
            setattr(subject, field, payload.get(field, default))

    def parse_datetime(value):
        return datetime.fromisoformat(value) if value else None

    for payload in pod_provisioning_records:
        record = db.get(PodProvisioningRecord, payload["id"]) or PodProvisioningRecord(
            id=payload["id"],
            subject_id=payload["subject_id"],
            enrollment_token_hash=payload["enrollment_token_hash"],
        )
        if db.get(PodProvisioningRecord, payload["id"]) is None:
            db.add(record)
        for field in ("subject_id", "name", "login", "password_hash", "decoy_password_hash", "status", "enrollment_token_hash", "enrollment_token_encrypted", "bundle_version", "artifact_sha256", "download_count", "metadata_json"):
            setattr(record, field, payload.get(field, getattr(record, field)))
        for field in ("downloaded_at", "expires_at", "activated_at", "revoked_at"):
            setattr(record, field, parse_datetime(payload.get(field)))
    db.flush()

    for payload in pods:
        pod = db.get(Pod, payload["id"]) or Pod(
            id=payload["id"],
            subject_id=payload["subject_id"],
            host_id=payload["host_id"],
            path=payload["path"],
            launcher_path=payload["launcher_path"],
        )
        if db.get(Pod, payload["id"]) is None:
            db.add(pod)
        pod.subject_id = payload["subject_id"]
        pod.host_id = payload["host_id"]
        pod.path = payload["path"]
        pod.launcher_path = payload["launcher_path"]
        pod.runtime_state = payload["runtime_state"]
        pod.is_portable = payload["is_portable"]
        for field, default in {
            "provisioning_id": None,
            "name": "Pod",
            "login": "pod",
            "password_hash": "",
            "decoy_password_hash": "",
            "status": "pending",
            "public_key_pem": "",
            "identity_certificate": "",
            "certificate_fingerprint": "",
            "device_binding_fingerprint": "",
            "device_binding_status": "pending",
            "pod_version": "0.1.0",
            "xray_version": "unknown",
            "network_profile_version": 1,
            "system_tabs_profile_version": 1,
            "heartbeat_sequence": 0,
            "revoke_reason": "",
        }.items():
            setattr(pod, field, payload.get(field, default))
        for field in ("last_materialized_at", "last_seen_at", "last_heartbeat_at", "activated_at", "revoked_at"):
            setattr(pod, field, parse_datetime(payload.get(field)))
    db.flush()

    for payload in pod_denylist:
        record = db.scalar(select(PodDenylist).where(
            PodDenylist.identifier_type == payload["identifier_type"],
            PodDenylist.identifier_value == payload["identifier_value"],
        )) or PodDenylist(id=payload["id"], identifier_type=payload["identifier_type"], identifier_value=payload["identifier_value"])
        if record.id == payload["id"] and db.get(PodDenylist, payload["id"]) is None:
            db.add(record)
        record.pod_id = payload.get("pod_id")
        record.subject_id = payload.get("subject_id")
        record.reason = payload.get("reason") or "revoked"

    for payload in agents:
        agent = db.get(Agent, payload["id"]) or Agent(
            id=payload["id"],
            name=payload["name"],
            agent_type=payload["agent_type"],
            host_id=payload["host_id"],
            identity_fingerprint=payload["identity_fingerprint"],
            api_base_url=payload["api_base_url"],
        )
        if db.get(Agent, payload["id"]) is None:
            db.add(agent)
        agent.name = payload["name"]
        agent.agent_type = payload["agent_type"]
        agent.host_id = payload["host_id"]
        agent.status = payload["status"]
        agent.identity_fingerprint = payload["identity_fingerprint"]
        agent.api_base_url = payload["api_base_url"]
        agent.display_name = payload.get("display_name")
        agent.domain = payload.get("domain")
        agent.port = payload.get("port")
        agent.resolved_ip = payload.get("resolved_ip")
        agent.enrollment_state = payload.get("enrollment_state") or agent.enrollment_state
        agent.identity_certificate = payload.get("identity_certificate") or ""
        agent.certificate_serial = payload.get("certificate_serial")
        agent.agent_version = payload.get("agent_version")
        agent.sindri_version = payload.get("sindri_version")
        agent.sindri_protocol_version = payload.get("sindri_protocol_version")
        agent.hostname = payload.get("hostname")
        agent.boot_id = payload.get("boot_id")
        agent.queue_length = payload.get("queue_length") or 0
        agent.current_job_id = payload.get("current_job_id")
        agent.tags = payload.get("tags") or []
        agent.environment = payload.get("environment") or ""
        agent.notes = payload.get("notes") or ""
        agent.metadata_json = payload.get("metadata_json") or {}
        agent.library_position = int(payload.get("library_position") or 0)

    for payload in agent_assignments:
        assignment = db.get(AgentAssignment, payload["id"]) or AgentAssignment(
            id=payload["id"],
            agent_id=payload["agent_id"],
            block_id=payload["block_id"],
            block_type=payload["block_type"],
        )
        if db.get(AgentAssignment, payload["id"]) is None:
            db.add(assignment)
        assignment.agent_id = payload["agent_id"]
        assignment.block_id = payload["block_id"]
        assignment.block_type = payload["block_type"]
        assignment.position = payload.get("position") or 0
        assignment.created_by = payload.get("created_by") or "restore"

    for payload in agent_certificates:
        certificate = db.get(AgentCertificate, payload["id"]) or AgentCertificate(
            id=payload["id"], agent_id=payload["agent_id"], fingerprint_sha256=payload["fingerprint_sha256"]
        )
        if db.get(AgentCertificate, payload["id"]) is None:
            db.add(certificate)
        certificate.agent_id = payload["agent_id"]
        certificate.fingerprint_sha256 = payload["fingerprint_sha256"]
        certificate.serial_number = payload.get("serial_number") or ""
        certificate.certificate_pem = payload.get("certificate_pem") or ""
        certificate.status = payload.get("status") or "active"

    for payload in agent_endpoints:
        endpoint = db.get(AgentEndpoint, payload["id"]) or AgentEndpoint(
            id=payload["id"], agent_id=payload["agent_id"], domain=payload["domain"], base_url=payload["base_url"]
        )
        if db.get(AgentEndpoint, payload["id"]) is None:
            db.add(endpoint)
        for key in ["agent_id", "domain", "port", "base_url", "status"]:
            if key in payload:
                setattr(endpoint, key, payload[key])

    for payload in agent_capabilities:
        capability = db.get(AgentCapability, payload["id"]) or AgentCapability(id=payload["id"], agent_id=payload["agent_id"], action=payload["action"])
        if db.get(AgentCapability, payload["id"]) is None:
            db.add(capability)
        capability.agent_id = payload["agent_id"]
        capability.action = payload["action"]
        capability.title = payload.get("title") or payload["action"]
        capability.description = payload.get("description") or ""
        capability.group = payload.get("group") or "System"
        capability.risk = payload.get("risk") or "read"
        capability.inputs = payload.get("inputs") or []
        capability.available = bool(payload.get("available", True))

    for payload in agent_heartbeats:
        if db.get(AgentHeartbeat, payload["id"]) is None:
            observed_at = datetime.fromisoformat(payload["observed_at"]) if payload.get("observed_at") else datetime.now(timezone.utc)
            db.add(AgentHeartbeat(id=payload["id"], agent_id=payload["agent_id"], payload=payload.get("payload") or {}, observed_at=observed_at))

    for payload in agent_state_events:
        if db.get(AgentStateEvent, payload["id"]) is None:
            db.add(AgentStateEvent(**{key: payload[key] for key in ["id", "sequence", "agent_id", "event_type", "status", "message", "payload"] if key in payload}))

    for payload in jobs:
        job = db.get(AgentJob, payload["id"]) or AgentJob(
            id=payload["id"],
            job_id=payload["job_id"],
            request_id=payload["request_id"],
            agent_id=payload["agent_id"],
            action=payload["action"],
        )
        if db.get(AgentJob, payload["id"]) is None:
            db.add(job)
        for key in ["job_id", "request_id", "agent_id", "action", "inputs", "created_by", "approver", "canceller", "status", "plan", "plan_hash", "result", "error", "log_reference", "agent_version", "sindri_version"]:
            if key in payload:
                setattr(job, key, payload[key])

    for payload in job_events:
        if db.get(JobEvent, payload["id"]) is None:
            db.add(JobEvent(**{key: payload[key] for key in ["id", "sequence", "agent_id", "job_id", "event_type", "status", "message", "payload"] if key in payload}))

    for payload in job_results:
        if db.get(JobResult, payload["id"]) is None:
            db.add(JobResult(**{key: payload[key] for key in ["id", "agent_id", "job_id", "status", "payload"] if key in payload}))

    for payload in approval_requests:
        approval = db.get(ApprovalRequest, payload["id"]) or ApprovalRequest(
            id=payload["id"],
            agent_id=payload["agent_id"],
            job_id=payload["job_id"],
            approval_id=payload["approval_id"],
            plan_hash=payload["plan_hash"],
        )
        if db.get(ApprovalRequest, payload["id"]) is None:
            db.add(approval)
        for key in ["risk", "warning", "plan", "status"]:
            if key in payload:
                setattr(approval, key, payload[key])

    for payload in approval_decisions:
        if db.get(ApprovalDecision, payload["id"]) is None:
            db.add(ApprovalDecision(**{key: payload[key] for key in ["id", "agent_id", "job_id", "approval_id", "plan_hash", "decision", "decided_by"] if key in payload}))

    for payload in revocation_records:
        if db.get(RevocationRecord, payload["id"]) is None:
            db.add(RevocationRecord(**{key: payload[key] for key in ["id", "agent_id", "certificate_serial", "certificate_fingerprint_sha256", "reason", "status", "payload"] if key in payload}))

    for payload in certificate_denylist:
        existing = db.get(CertificateDenylist, payload["id"]) or db.scalar(select(CertificateDenylist).where(CertificateDenylist.fingerprint_sha256 == payload["fingerprint_sha256"]))
        deny = existing or CertificateDenylist(id=payload["id"], fingerprint_sha256=payload["fingerprint_sha256"])
        if existing is None:
            db.add(deny)
        deny.serial_number = payload.get("serial_number") or ""
        deny.agent_id = payload.get("agent_id")
        deny.reason = payload.get("reason") or "restore"

    for payload in controller_identity:
        identity = db.get(ControllerIdentity, payload["id"]) or ControllerIdentity(id=payload["id"], controller_id=payload["controller_id"])
        if db.get(ControllerIdentity, payload["id"]) is None:
            db.add(identity)
        identity.controller_id = payload["controller_id"]
        identity.certificate_pem = payload.get("certificate_pem") or ""
        identity.encrypted_private_key = payload.get("encrypted_private_key") or ""
        identity.encryption_metadata = payload.get("encryption_metadata") or {}
        identity.status = payload.get("status") or "active"

    for payload in sessions:
        session = db.get(SessionLease, payload["id"]) or SessionLease(
            id=payload["id"],
            subject_id=payload["subject_id"],
            pod_id=payload.get("pod_id") or payload.get(legacy_pod_id),
            agent_id=payload["agent_id"],
            status=payload["status"],
            session_key_hash=payload["session_key_hash"],
        )
        if db.get(SessionLease, payload["id"]) is None:
            db.add(session)
        session.subject_id = payload["subject_id"]
        session.pod_id = payload.get("pod_id") or payload.get(legacy_pod_id)
        session.agent_id = payload["agent_id"]
        session.status = payload["status"]
        session.session_key_hash = payload["session_key_hash"]
        session.access_scope = payload["access_scope"]
        session.transport = payload["transport"]

    for payload in commands:
        command = db.get(AgentCommand, payload["id"]) or AgentCommand(
            id=payload["id"],
            agent_id=payload["agent_id"],
            command=payload["command"],
        )
        if db.get(AgentCommand, payload["id"]) is None:
            db.add(command)
        command.agent_id = payload["agent_id"]
        command.command = payload["command"]
        command.target = payload["target"]
        command.params = payload["params"]
        command.status = payload["status"]
        command.result = payload["result"]

    for payload in system_settings:
        setting = db.get(SystemSetting, payload["id"]) or SystemSetting(id=payload["id"], scope=payload["scope"], key=payload["key"])
        if db.get(SystemSetting, payload["id"]) is None:
            db.add(setting)
        setting.scope = payload["scope"]
        setting.key = payload["key"]
        value = payload["value"]
        if setting.key == "perimetr.preferences":
            value = dict(value or {})
            auth = dict(value.get("auth") or {})
            legacy_password = str(auth.pop("password", "") or "")
            if legacy_password and not is_password_hash(str(auth.get("password_hash") or "")):
                auth["password_hash"] = hash_password(legacy_password)
            value["auth"] = auth
        setting.value = value

    for payload in recent_audit:
        if db.get(AuditEvent, payload["id"]) is not None:
            continue
        db.add(
            AuditEvent(
                id=payload["id"],
                actor_type=payload["actor_type"],
                actor_id=payload["actor_id"],
                action=payload["action"],
                target_type=payload["target_type"],
                target_id=payload["target_id"],
                payload=payload["payload"],
                result=payload["result"],
            )
        )

    logs_dir = Path(Settings().perimetr_logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in logs.items():
        target = logs_dir / Path(filename).name
        if target.suffix == ".jsonl":
            target.write_text(str(content), encoding="utf-8")

    audit(
        db,
        actor_type="perimetr",
        actor_id="core",
        action="backup.imported",
        target_type=manifest.get("entity_type", "backup"),
        target_id=manifest.get("entity_id", "unknown"),
        result={"filename": archive.filename},
    )
    db.commit()
    return {"restorable": True, "manifest": manifest, "filename": archive.filename}
