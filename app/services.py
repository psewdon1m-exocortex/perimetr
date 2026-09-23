from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
import shutil
import time
import os
from pathlib import Path
from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .enums import LaunchDecision, SessionStatus
from .logs_service.service import trim_audit_events
from .models import AuditEvent, Pod, LaunchAuthorization, PerimetrObject, SessionLease, Subject, SystemSetting
from .settings import Settings
from .operator_settings import ensure_preferences, update_preferences
from .redaction import bounded, text as redact_text
from .security import hash_password, verify_password

T = TypeVar("T")

PERIMETR_SYSTEM_ENTITY_ID = "5f0b6d3d90f548a9a2f1d6e9cb7f3412"
PROCESS_STARTED = time.monotonic()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def json_safe(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def ensure_exists(instance: T | None, entity: str, entity_id: str) -> T:
    if instance is None:
        raise HTTPException(status_code=404, detail=f"{entity} {entity_id} not found")
    return instance


def get_object(db: Session, object_id: str) -> PerimetrObject:
    instance = db.get(PerimetrObject, object_id) or db.scalar(select(PerimetrObject).where(PerimetrObject.entity_id == object_id))
    return ensure_exists(instance, "object", object_id)


def get_subject(db: Session, subject_id: str) -> Subject:
    instance = db.get(Subject, subject_id) or db.scalar(select(Subject).where(Subject.entity_id == subject_id))
    return ensure_exists(instance, "subject", subject_id)


def get_pod(db: Session, pod_id: str) -> Pod:
    return ensure_exists(db.get(Pod, pod_id), "pod", pod_id)


def get_session_lease(db: Session, session_id: str) -> SessionLease:
    return ensure_exists(db.get(SessionLease, session_id), "session", session_id)


def hash_session_key(session_key: str) -> str:
    return sha256(session_key.encode("utf-8")).hexdigest()


def audit(
    db: Session,
    *,
    actor_type: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    payload: dict | None = None,
    result: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_type=redact_text(actor_type)[:64],
        actor_id=redact_text(actor_id)[:128],
        action=redact_text(action)[:128],
        target_type=redact_text(target_type)[:64],
        target_id=redact_text(target_id)[:128],
        payload=bounded(payload or {}, 7000),
        result=bounded(result or {}, 7000),
    )
    db.add(event)
    db.flush()
    settings = Settings()
    trim_audit_events(db, settings)
    db.info.setdefault("audit_file_events", []).append((settings, event))
    return event


def ensure_perimetr_system_settings(db: Session, settings: Settings) -> None:
    ensure_preferences(db, settings)


def get_perimetr_preferences(db: Session, settings: Settings) -> dict:
    ensure_perimetr_system_settings(db, settings)
    db.flush()
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "perimetr.preferences"))
    return dict(setting.value if setting else {})


def update_perimetr_preferences(db: Session, settings: Settings, value: dict) -> dict:
    return update_preferences(db, settings, value)


CORRELATION_STATE_KEY = "perimetr.correlation_map"
OVERVIEW_BLOCKS_STATE_KEY = "perimetr.overview_blocks"
OVERVIEW_BLOCK_DEFAULTS = {
    "human_general": "I as human in general",
    "turkey_global": "Turkey / Global sphere",
    "russia_sphere": "Russia influence sphere",
    "laboratory_block": "Laboratory",
    "perimetr_block": "Perimetr",
}


def _overview_blocks_setting(db: Session) -> SystemSetting:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == OVERVIEW_BLOCKS_STATE_KEY))
    if setting is None:
        setting = SystemSetting(
            scope="perimetr",
            key=OVERVIEW_BLOCKS_STATE_KEY,
            value={"blocks": {}},
        )
        db.add(setting)
        db.flush()
    return setting


def get_overview_blocks(db: Session) -> dict[str, dict[str, str]]:
    setting = _overview_blocks_setting(db)
    stored = dict((setting.value or {}).get("blocks") or {})
    result: dict[str, dict[str, str]] = {}
    for block_id, default_name in OVERVIEW_BLOCK_DEFAULTS.items():
        item = dict(stored.get(block_id) or {})
        result[block_id] = {
            "name": str(item.get("name") or default_name).strip() or default_name,
            "image_data": str(item.get("image_data") or ""),
            "updated_at": str(item.get("updated_at") or setting.updated_at.isoformat()),
        }
    return result


def update_overview_block(
    db: Session,
    block_id: str,
    *,
    name: str | None = None,
    image_data: str | None = None,
) -> dict[str, str]:
    if block_id not in OVERVIEW_BLOCK_DEFAULTS:
        raise HTTPException(status_code=404, detail="overview_block_not_found")
    blocks = get_overview_blocks(db)
    block = dict(blocks[block_id])
    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise HTTPException(status_code=400, detail="overview_block_name_required")
        if len(normalized_name) > 255:
            raise HTTPException(status_code=400, detail="overview_block_name_too_long")
        block["name"] = normalized_name
    if image_data is not None:
        block["image_data"] = image_data
    block["updated_at"] = now_utc().isoformat()
    blocks[block_id] = block
    setting = _overview_blocks_setting(db)
    setting.value = {"blocks": blocks}
    db.flush()
    return block


def default_correlation_state() -> dict:
    return {
        "descriptions_by_block": {},
        "properties_by_block": {},
        "property_library": [],
        "graph_settings": {
            "property_color": "",
            "entity_color": "",
            "node_size": 6,
            "link_thickness": 1,
            "text_threshold": 0.15,
            "center_force": 0.006,
            "repel_force": 1800,
            "link_force": 0.025,
            "link_distance": 150,
            "animate": True,
        },
    }


def get_correlation_state(db: Session) -> dict:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == CORRELATION_STATE_KEY))
    if setting is None:
        value = default_correlation_state()
        setting = SystemSetting(scope="perimetr", key=CORRELATION_STATE_KEY, value=value)
        db.add(setting)
        db.flush()
        return value
    value = {**default_correlation_state(), **dict(setting.value or {})}
    value["graph_settings"] = {**default_correlation_state()["graph_settings"], **dict(value.get("graph_settings") or {})}
    return value


def correlation_percentage(db: Session, value: dict | None = None) -> float:
    state = value or get_correlation_state(db)
    entity_ids = {"human_general", "turkey_global", "russia_sphere", "laboratory_block", "perimetr_block"}
    entity_ids.update(f"object_{item}" for item in db.scalars(select(PerimetrObject.entity_id)).all())
    entity_ids.update(f"subject_{item}" for item in db.scalars(select(Subject.entity_id)).all())
    property_ids = {str(item.get("id")) for item in state.get("property_library", []) if item.get("id")}
    if not property_ids or len(entity_ids) < 2:
        return 0.0
    counts = {property_id: 0 for property_id in property_ids}
    for block_id, items in dict(state.get("properties_by_block") or {}).items():
        if block_id not in entity_ids:
            continue
        for property_id in {str(item.get("id")) for item in items if item.get("id")}:
            if property_id in counts:
                counts[property_id] += 1
    denominator = len(entity_ids) - 1
    score = sum(max(0, count - 1) / denominator for count in counts.values()) / len(property_ids)
    return round(score * 100, 2)


def update_correlation_state(db: Session, value: dict) -> dict:
    if len(value.get("property_library") or []) > 5000 or len(value.get("properties_by_block") or {}) > 10000:
        raise HTTPException(status_code=400, detail="correlation_state_too_large")
    next_value = {**default_correlation_state(), **value}
    next_value["graph_settings"] = {**default_correlation_state()["graph_settings"], **dict(value.get("graph_settings") or {})}
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == CORRELATION_STATE_KEY))
    if setting is None:
        setting = SystemSetting(scope="perimetr", key=CORRELATION_STATE_KEY, value=next_value)
        db.add(setting)
    else:
        setting.value = next_value
    db.flush()
    return {**next_value, "correlation_percentage": correlation_percentage(db, next_value)}


def update_access_key(
    db: Session,
    settings: Settings,
    *,
    current_key: str,
    new_key: str,
    confirm_key: str,
    current_session: SessionLease,
) -> None:
    if new_key == "" or new_key != confirm_key:
        raise HTTPException(status_code=400, detail="Supply the same new Access Key twice")
    preferences = get_perimetr_preferences(db, settings)
    auth = dict(preferences.get("auth") or {})
    stored_hash = str(auth.get("access_key_hash") or "")
    if not verify_password(current_key, stored_hash):
        raise HTTPException(status_code=403, detail="Current Access Key is incorrect")
    auth = {"access_key_hash": hash_password(new_key)}
    preferences["auth"] = auth
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "perimetr.preferences"))
    assert setting is not None
    setting.value = preferences
    now = now_utc()
    for lease in db.scalars(
        select(SessionLease).where(SessionLease.status == SessionStatus.active.value, SessionLease.transport == "direct")
    ).all():
        if lease.id != current_session.id:
            lease.status = SessionStatus.revoked.value
            lease.ended_at = now
    session_key = secrets.token_urlsafe(32)
    current_session.session_key_hash = hash_session_key(session_key)
    current_session.expires_at = now + timedelta(seconds=settings.perimetr_session_ttl_sec)
    setattr(current_session, "_plain_session_key", session_key)
    db.flush()


def normalize_access_target(target: str) -> str:
    value = (target or "perimetr").strip().lower()
    if value != "perimetr":
        raise HTTPException(status_code=400, detail=f"unsupported_target:{value}")
    return value


def verify_direct_login(db: Session, settings: Settings, *, target: str, access_key: str) -> bool:
    normalize_access_target(target)
    preferences = get_perimetr_preferences(db, settings)
    auth = dict(preferences.get("auth") or {})
    return access_key != "" and verify_password(access_key, str(auth.get("access_key_hash") or ""))


def expire_stale_sessions(db: Session) -> None:
    current = now_utc()
    leases = db.scalars(
        select(SessionLease).where(
            SessionLease.status == SessionStatus.active.value,
            SessionLease.expires_at.is_not(None),
        )
    ).all()
    for lease in leases:
        expires_at = normalize_timestamp(lease.expires_at)
        if expires_at and expires_at <= current:
            lease.status = SessionStatus.expired.value
            lease.ended_at = current


def create_direct_session(db: Session, settings: Settings, *, target: str, access_key: str) -> SessionLease:
    target = normalize_access_target(target)
    expire_stale_sessions(db)
    if not verify_direct_login(db, settings, target=target, access_key=access_key):
        raise HTTPException(status_code=403, detail="invalid_credentials")
    session_key = secrets.token_urlsafe(32)
    lease = SessionLease(
        status=SessionStatus.active.value,
        session_key_hash=hash_session_key(session_key),
        access_scope=target,
        transport="direct",
        expires_at=now_utc().replace(microsecond=0) + timedelta(seconds=settings.perimetr_session_ttl_sec),
    )
    db.add(lease)
    db.flush()
    setattr(lease, "_plain_session_key", session_key)
    return lease


def ensure_single_active_subject_lease(db: Session, subject_id: str) -> None:
    active_count = db.scalar(
        select(func.count(SessionLease.id)).where(
            SessionLease.subject_id == subject_id,
            SessionLease.status == SessionStatus.active.value,
        )
    )
    if active_count and active_count > 0:
        raise HTTPException(status_code=409, detail="active lease already exists for subject")


def revoke_subject_access(db: Session, subject: Subject, reason: str) -> LaunchAuthorization | None:
    authorization = db.scalar(
        select(LaunchAuthorization)
        .where(LaunchAuthorization.subject_id == subject.id)
        .order_by(LaunchAuthorization.created_at.desc())
    )
    if authorization:
        authorization.decision = LaunchDecision.revoked.value
        authorization.reason = reason
        authorization.revoked_at = now_utc()
    for lease in db.scalars(
        select(SessionLease).where(
            SessionLease.subject_id == subject.id,
            SessionLease.status == SessionStatus.active.value,
        )
    ).all():
        lease.status = SessionStatus.revoked.value
        lease.ended_at = now_utc()
    return authorization


def build_status_response(db: Session) -> dict:
    return {
        "perimetr_status": "active",
        "database_status": "ok",
        "cache_status": "configured",
    }


def _read_cpu_totals() -> tuple[int, int] | None:
    try:
        first = next(line for line in open("/proc/stat", "r", encoding="utf-8") if line.startswith("cpu "))
    except (OSError, StopIteration):
        return None
    values = [int(value) for value in first.split()[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return idle, total


def _read_cpu_percent() -> float | None:
    first = _read_cpu_totals()
    if first is None:
        return None
    time.sleep(0.05)
    second = _read_cpu_totals()
    if second is None:
        return None
    idle_delta = second[0] - first[0]
    total_delta = second[1] - first[1]
    if total_delta <= 0:
        return None
    return round(max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta))), 1)


def _read_ram() -> tuple[int | None, int | None, float | None]:
    try:
        data = {}
        for line in open("/proc/meminfo", "r", encoding="utf-8"):
            key, raw = line.split(":", 1)
            data[key] = int(raw.strip().split()[0]) * 1024
        total = data.get("MemTotal", 0)
        available = data.get("MemAvailable", 0)
        used = max(0, total - available)
    except (OSError, ValueError):
        return None, None, None
    if not total:
        return None, None, None
    percent = round(used / total * 100.0, 1)
    return used, total, percent


def build_system_metrics() -> dict:
    ram_used, ram_total, ram_percent = _read_ram()
    settings = Settings()
    path = Path(getattr(settings, "perimetr_data_filesystem", "") or settings.perimetr_state_dir).resolve()
    try:
        if hasattr(os, "statvfs"):
            disk = os.statvfs(path)
            total = disk.f_blocks * disk.f_frsize
            used = total - disk.f_bavail * disk.f_frsize
        else:
            disk = shutil.disk_usage(path)
            total, used = disk.total, disk.total - disk.free
        if total <= 0:
            raise ValueError("unavailable disk capacity")
        percent = round(max(0.0, min(100.0, used / total * 100.0)), 1)
    except (OSError, ValueError):
        total = used = percent = None
    return {
        "cpu_percent": _read_cpu_percent(),
        "cpu_cores": os.cpu_count(),
        "ram_used_bytes": ram_used,
        "ram_total_bytes": ram_total,
        "ram_percent": ram_percent,
        "disk_used_bytes": used,
        "disk_total_bytes": total,
        "disk_percent": percent,
        "uptime_seconds": max(0, int(time.monotonic() - PROCESS_STARTED)),
    }


def build_topology_snapshot(db: Session) -> dict:
    settings = Settings()
    objects = db.scalars(select(PerimetrObject).order_by(PerimetrObject.created_at.asc())).all()
    subjects = db.scalars(select(Subject).order_by(Subject.created_at.asc())).all()
    pods = db.scalars(select(Pod).order_by(Pod.created_at.asc())).all()
    recent_audit = db.scalars(
        select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(settings.perimetr_audit_max_entries)
    ).all()

    pods_by_subject = {pod.subject_id: pod for pod in pods}
    object_nodes = []
    for item in objects:
        object_nodes.append(
            {
                "id": item.entity_id,
                "name": item.name,
                "kind": item.kind,
                "description": item.description,
                "tags": item.tags,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
        )

    return {
        "status": build_status_response(db),
        "objects": object_nodes,
        "subjects": [
            {
                "id": subject.entity_id,
                "name": subject.name,
                "kind": subject.kind,
                "description": subject.description,
                "tags": subject.tags,
                "runtime_type": subject.runtime_type,
                "primary_route": subject.primary_route,
                "pod": (
                    {
                        "id": pods_by_subject[subject.id].id,
                        "host_id": pods_by_subject[subject.id].host_id,
                        "path": pods_by_subject[subject.id].path,
                        "launcher_path": pods_by_subject[subject.id].launcher_path,
                        "runtime_state": pods_by_subject[subject.id].runtime_state,
                    }
                    if subject.id in pods_by_subject
                    else None
                ),
            }
            for subject in subjects
        ],
        "recent_audit": [
            {
                "id": event.id,
                "actor_type": event.actor_type,
                "actor_id": event.actor_id,
                "action": event.action,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "payload": event.payload,
                "result": event.result,
                "created_at": event.created_at.isoformat(),
            }
            for event in recent_audit
        ],
        "meta": {
            "object_count": len(objects),
            "subject_count": len(subjects),
        },
        "system": {
            "id": PERIMETR_SYSTEM_ENTITY_ID,
            "preferences": get_perimetr_preferences(db, settings),
            "metrics": build_system_metrics(),
        },
    }
