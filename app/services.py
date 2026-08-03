from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
import shutil
import time
from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .enums import CommandStatus, LaunchDecision, SessionStatus
from .logs_service.service import trim_audit_events, write_audit_log
from .models import (
    Agent,
    AgentAssignment,
    AgentCapability,
    AgentHeartbeat,
    AgentJob,
    AgentStateEvent,
    AgentCommand,
    ApprovalDecision,
    ApprovalRequest,
    AuditEvent,
    CertificateDenylist,
    Pod,
    JobEvent,
    JobResult,
    LaunchAuthorization,
    PerimetrObject,
    RevocationRecord,
    SessionLease,
    Subject,
    SystemSetting,
)
from .settings import Settings
from .security import (
    constant_time_text_equal,
    hash_password,
    is_password_hash,
    verify_password,
)

T = TypeVar("T")

PERIMETR_SYSTEM_ENTITY_ID = "5f0b6d3d90f548a9a2f1d6e9cb7f3412"


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


def get_agent(db: Session, agent_id: str) -> Agent:
    return ensure_exists(db.get(Agent, agent_id), "agent", agent_id)


def find_agent(db: Session, agent_id: str) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None:
        agent = db.scalar(select(Agent).where(Agent.id == agent_id))
    return ensure_exists(agent, "agent", agent_id)


def get_agent_job(db: Session, agent_id: str, job_id: str) -> AgentJob:
    job = db.scalar(select(AgentJob).where(AgentJob.agent_id == agent_id, AgentJob.job_id == job_id))
    return ensure_exists(job, "job", job_id)


def get_session_lease(db: Session, session_id: str) -> SessionLease:
    return ensure_exists(db.get(SessionLease, session_id), "session", session_id)


def get_command(db: Session, command_id: str) -> AgentCommand:
    return ensure_exists(db.get(AgentCommand, command_id), "command", command_id)


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
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload or {},
        result=result or {},
    )
    db.add(event)
    db.flush()
    settings = Settings()
    trim_audit_events(db, settings)
    write_audit_log(settings, event)
    return event


def ensure_perimetr_system_settings(db: Session, settings: Settings) -> None:
    defaults = {
        "theme": {"dark": "#000000", "light": "#ffffff", "accent": "#00a8ff"},
        "sidebar": {"auto_hide": True},
        "backup": {"include_audit": True, "include_sessions": True},
        "auth": {
            "username": settings.perimetr_direct_username,
            "direct_enabled": settings.perimetr_direct_auth_enabled,
        },
    }
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "perimetr.preferences"))
    if setting is None:
        defaults["auth"]["password_hash"] = hash_password(settings.perimetr_entry_password)
        db.add(SystemSetting(scope="perimetr", key="perimetr.preferences", value=defaults))
        db.flush()
        return
    current = dict(setting.value or {})
    current.setdefault("auth", defaults["auth"])
    auth = dict(current["auth"])
    auth.setdefault("username", defaults["auth"]["username"])
    legacy_password = str(auth.pop("password", "") or "")
    stored_hash = str(auth.get("password_hash", "") or "")
    if not is_password_hash(stored_hash):
        auth["password_hash"] = hash_password(
            legacy_password or settings.perimetr_entry_password
        )
    auth["direct_enabled"] = True
    current["auth"] = auth
    current.setdefault("theme", defaults["theme"])
    current.setdefault("sidebar", defaults["sidebar"])
    current.setdefault("backup", defaults["backup"])
    setting.value = current


def get_perimetr_preferences(db: Session, settings: Settings) -> dict:
    ensure_perimetr_system_settings(db, settings)
    db.flush()
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "perimetr.preferences"))
    return dict(setting.value if setting else {})


def update_perimetr_preferences(db: Session, settings: Settings, value: dict) -> dict:
    current = get_perimetr_preferences(db, settings)
    next_value = {
        **current,
        **{key: val for key, val in value.items() if key in {"theme", "sidebar", "backup"}},
    }
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "perimetr.preferences"))
    assert setting is not None
    setting.value = next_value
    db.flush()
    return dict(setting.value)


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


def update_direct_password(
    db: Session,
    settings: Settings,
    *,
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> None:
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="new_password_confirmation_mismatch")
    if len(new_password) < 12:
        raise HTTPException(status_code=400, detail="new_password_too_short")
    preferences = get_perimetr_preferences(db, settings)
    auth = dict(preferences.get("auth") or {})
    stored_hash = str(auth.get("password_hash") or "")
    if not verify_password(current_password, stored_hash):
        raise HTTPException(status_code=403, detail="current_password_invalid")
    auth.pop("password", None)
    auth["password_hash"] = hash_password(new_password)
    auth["direct_enabled"] = True
    preferences["auth"] = auth
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "perimetr.preferences"))
    assert setting is not None
    setting.value = preferences
    now = now_utc()
    for lease in db.scalars(
        select(SessionLease).where(SessionLease.status == SessionStatus.active.value)
    ).all():
        lease.status = SessionStatus.revoked.value
        lease.ended_at = now
    db.flush()


def normalize_access_target(target: str) -> str:
    value = (target or "perimetr").strip().lower()
    if value != "perimetr":
        raise HTTPException(status_code=400, detail=f"unsupported_target:{value}")
    return value


def verify_direct_login(db: Session, settings: Settings, *, target: str, username: str, password: str) -> bool:
    normalize_access_target(target)
    preferences = get_perimetr_preferences(db, settings)
    auth = dict(preferences.get("auth") or {})
    if not bool(auth.get("direct_enabled", settings.perimetr_direct_auth_enabled)):
        return False
    if not constant_time_text_equal(
        username,
        str(auth.get("username", settings.perimetr_direct_username)),
    ):
        return False
    return verify_password(password, str(auth.get("password_hash") or ""))


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


def create_direct_session(db: Session, settings: Settings, *, target: str, username: str, password: str) -> SessionLease:
    target = normalize_access_target(target)
    expire_stale_sessions(db)
    if not verify_direct_login(db, settings, target=target, username=username, password=password):
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
    agent_count = db.scalar(select(func.count(Agent.id))) or 0
    return {
        "perimetr_status": "active",
        "database_status": "ok",
        "cache_status": "configured",
        "agent_count": agent_count,
    }


AGENT_BLOCK_TYPES = {"laboratory", "perimetr", "subject"}
SINGLE_AGENT_BLOCK_TYPES = {"laboratory", "perimetr"}
BLOCK_TYPE_ALIASES = {"lab": "laboratory", "laboratory": "laboratory", "perimetr": "perimetr", "subject": "subject"}
BLOCKED_JOB_STATES = {"OFFLINE", "UNREACHABLE", "REVOKED", "ERROR", "DETACHED", "RESTORING"}


DEFAULT_AGENT_CAPABILITIES = [
    {"action": "system.info", "title": "System info", "group": "System", "risk": "read", "inputs": []},
    {"action": "system.doctor", "title": "Doctor", "group": "System", "risk": "read", "inputs": []},
    {"action": "system.make_ready", "title": "Make ready", "group": "System", "risk": "change", "inputs": []},
    {"action": "firewall.status", "title": "Firewall status", "group": "Firewall", "risk": "read", "inputs": []},
    {"action": "firewall.open", "title": "Open firewall port", "group": "Firewall", "risk": "change", "inputs": [{"name": "port", "type": "integer"}, {"name": "protocol", "type": "choice"}]},
    {"action": "docker.info", "title": "Docker info", "group": "Docker", "risk": "read", "inputs": []},
    {"action": "docker.logs", "title": "Docker logs", "group": "Docker", "risk": "read", "inputs": [{"name": "lines", "type": "integer"}]},
]


def normalize_agent_block_type(block_type: str) -> str:
    value = BLOCK_TYPE_ALIASES.get((block_type or "").strip().lower())
    if value not in AGENT_BLOCK_TYPES:
        raise HTTPException(status_code=400, detail="AGENT_BLOCK_UNSUPPORTED")
    return value


def ensure_agent_block_exists(db: Session, block_type: str, block_id: str) -> None:
    if block_type == "subject":
        get_subject(db, block_id)
    elif block_type == "laboratory" and block_id != "laboratory":
        raise HTTPException(status_code=404, detail="laboratory block not found")
    elif block_type == "perimetr" and block_id != PERIMETR_SYSTEM_ENTITY_ID:
        raise HTTPException(status_code=404, detail="perimetr block not found")


def agent_assignment_count(db: Session, agent_id: str) -> int:
    return db.scalar(select(func.count(AgentAssignment.id)).where(AgentAssignment.agent_id == agent_id)) or 0


def agent_assignment_targets(db: Session, agent_id: str) -> list[dict[str, str]]:
    assignments = db.scalars(
        select(AgentAssignment)
        .where(AgentAssignment.agent_id == agent_id)
        .order_by(AgentAssignment.position.asc(), AgentAssignment.created_at.asc())
    ).all()
    subject_ids = [item.block_id for item in assignments if item.block_type == "subject"]
    subjects = db.scalars(select(Subject).where(Subject.entity_id.in_(subject_ids))).all() if subject_ids else []
    subject_names = {item.entity_id: item.name for item in subjects}
    labels = {
        "laboratory": "Laboratory",
        "perimetr": "Perimetr",
    }
    return [
        {
            "block_type": item.block_type,
            "block_id": item.block_id,
            "name": subject_names.get(item.block_id) or labels.get(item.block_type) or item.block_id,
        }
        for item in assignments
    ]


def summarize_agent(db: Session, agent: Agent) -> dict:
    count = agent_assignment_count(db, agent.id)
    return {
        "id": agent.id,
        "display_name": agent.display_name or agent.name,
        "status": visible_agent_status(agent, count),
        "agent_id": agent.id,
        "domain": agent.domain,
        "port": agent.port,
        "resolved_ip": agent.resolved_ip,
        "hostname": agent.hostname,
        "assignment_count": count,
        "assignments": agent_assignment_targets(db, agent.id),
        "identity_fingerprint": agent.identity_fingerprint,
        "certificate_serial": agent.certificate_serial,
        "agent_version": agent.agent_version,
        "sindri_version": agent.sindri_version,
        "sindri_protocol_version": agent.sindri_protocol_version,
        "last_heartbeat_at": agent.last_heartbeat_at,
        "tags": agent.tags or [],
        "environment": agent.environment or "",
        "notes": agent.notes or "",
    }


def visible_agent_status(agent: Agent, assignment_count: int | None = None) -> str:
    count = assignment_count if assignment_count is not None else 1
    if agent.enrollment_state == "revoked":
        return "REVOKED"
    if count == 0:
        return "DETACHED"
    if agent.status in {"APPROVAL REQUIRED", "ERROR", "REVOKED", "OFFLINE", "UNREACHABLE", "DEGRADED"}:
        return agent.status
    last = normalize_timestamp(agent.last_heartbeat_at)
    if last is None:
        return "OFFLINE"
    if now_utc() - last > timedelta(seconds=90):
        return "OFFLINE"
    return agent.status if agent.status in {"ONLINE", "BUSY"} else "ONLINE"


def upsert_agent_capabilities(db: Session, agent_id: str, capabilities: list[dict]) -> None:
    values = capabilities or DEFAULT_AGENT_CAPABILITIES
    for item in values:
        action = str(item.get("action") or "").strip()
        if not action:
            continue
        capability = db.scalar(select(AgentCapability).where(AgentCapability.agent_id == agent_id, AgentCapability.action == action))
        if capability is None:
            capability = AgentCapability(agent_id=agent_id, action=action)
            db.add(capability)
        capability.title = str(item.get("title") or action)
        capability.description = str(item.get("description") or "")
        capability.group = str(item.get("group") or _capability_group(action))
        capability.risk = str(item.get("risk") or "read")
        capability.inputs = list(item.get("inputs") or [])
        capability.available = bool(item.get("available", True))


def _capability_group(action: str) -> str:
    prefix = action.split(".", 1)[0]
    return {"system": "System", "firewall": "Firewall", "docker": "Docker", "user": "Users", "cert": "Certificates"}.get(prefix, "Agent Node")


def ensure_agent_capability(db: Session, agent_id: str, action: str) -> AgentCapability:
    capability = db.scalar(select(AgentCapability).where(AgentCapability.agent_id == agent_id, AgentCapability.action == action, AgentCapability.available.is_(True)))
    if capability is None:
        raise HTTPException(status_code=400, detail="CAPABILITY_NOT_AVAILABLE")
    return capability


def redact_agent_inputs(capability: AgentCapability, inputs: dict) -> dict:
    secret_names = {
        str(item.get("name") or "")
        for item in (capability.inputs or [])
        if item.get("secret") or item.get("type") == "secret"
    }
    return {
        key: "[redacted]" if key in secret_names else value
        for key, value in (inputs or {}).items()
    }


def assign_agent_to_block(db: Session, *, agent_id: str, block_type: str, block_id: str, created_by: str = "operator") -> AgentAssignment:
    block_type = normalize_agent_block_type(block_type)
    ensure_agent_block_exists(db, block_type, block_id)
    agent = find_agent(db, agent_id)
    existing = db.scalar(
        select(AgentAssignment).where(
            AgentAssignment.agent_id == agent.id,
            AgentAssignment.block_id == block_id,
            AgentAssignment.block_type == block_type,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="AGENT_ALREADY_ASSIGNED")
    if block_type in SINGLE_AGENT_BLOCK_TYPES:
        count = db.scalar(select(func.count(AgentAssignment.id)).where(AgentAssignment.block_id == block_id, AgentAssignment.block_type == block_type)) or 0
        if count >= 1:
            raise HTTPException(status_code=409, detail="AGENT_LIMIT_REACHED")
    position = db.scalar(select(func.count(AgentAssignment.id)).where(AgentAssignment.block_id == block_id, AgentAssignment.block_type == block_type)) or 0
    assignment = AgentAssignment(agent_id=agent.id, block_id=block_id, block_type=block_type, position=position, created_by=created_by)
    db.add(assignment)
    agent.enrollment_state = "enrolled"
    if agent.status == "DETACHED":
        agent.status = "ONLINE" if agent.last_heartbeat_at else "OFFLINE"
    db.flush()
    return assignment


def unassign_agent_from_block(db: Session, *, agent_id: str, block_type: str, block_id: str) -> AgentAssignment:
    block_type = normalize_agent_block_type(block_type)
    assignment = db.scalar(
        select(AgentAssignment).where(
            AgentAssignment.agent_id == agent_id,
            AgentAssignment.block_id == block_id,
            AgentAssignment.block_type == block_type,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="ASSIGNMENT_NOT_FOUND")
    db.delete(assignment)
    db.flush()
    return assignment


def reorder_block_agents(db: Session, *, block_type: str, block_id: str, ordered_agent_ids: list[str]) -> None:
    block_type = normalize_agent_block_type(block_type)
    assignments = db.scalars(
        select(AgentAssignment).where(AgentAssignment.block_id == block_id, AgentAssignment.block_type == block_type)
    ).all()
    by_agent = {item.agent_id: item for item in assignments}
    if set(by_agent) != set(ordered_agent_ids):
        raise HTTPException(status_code=400, detail="INVALID_AGENT_ORDER")
    for position, agent_id in enumerate(ordered_agent_ids):
        by_agent[agent_id].position = position


def record_job_event(
    db: Session,
    *,
    agent_id: str,
    job_id: str,
    event_type: str,
    status: str = "",
    message: str = "",
    payload: dict | None = None,
) -> JobEvent:
    sequence = db.scalar(select(func.count(JobEvent.id)).where(JobEvent.agent_id == agent_id, JobEvent.job_id == job_id)) or 0
    event = JobEvent(
        sequence=sequence + 1,
        agent_id=agent_id,
        job_id=job_id,
        event_type=event_type,
        status=status,
        message=message,
        payload=payload or {},
    )
    db.add(event)
    db.flush()
    return event


def create_agent_job(db: Session, *, agent: Agent, action: str, inputs: dict, created_by: str, expires_at: datetime | None) -> AgentJob:
    if visible_agent_status(agent) in BLOCKED_JOB_STATES:
        raise HTTPException(status_code=409, detail=f"AGENT_{visible_agent_status(agent)}")
    capability = ensure_agent_capability(db, agent.id, action)
    current_pending = db.scalar(
        select(func.count(AgentJob.id)).where(
            AgentJob.agent_id == agent.id,
            AgentJob.status.in_(["QUEUED", "RUNNING", "INPUT_REQUIRED", "APPROVAL_REQUIRED"]),
        )
    ) or 0
    if current_pending >= 100:
        raise HTTPException(status_code=409, detail="JOB_QUEUE_FULL")
    job_id = f"job-{secrets.token_hex(8)}"
    request_id = f"req-{secrets.token_hex(8)}"
    job = AgentJob(
        job_id=job_id,
        request_id=request_id,
        agent_id=agent.id,
        action=action,
        inputs=redact_agent_inputs(capability, inputs),
        created_by=created_by,
        expires_at=expires_at or (now_utc() + timedelta(minutes=15)),
        status="QUEUED",
        agent_version=agent.agent_version,
        sindri_version=agent.sindri_version,
    )
    db.add(job)
    db.flush()
    record_job_event(db, agent_id=agent.id, job_id=job.job_id, event_type="job.created", status=job.status, payload={"action": action})
    return job


def apply_agent_job_event(db: Session, *, agent_id: str, job_id: str, payload: dict) -> JobEvent:
    job = get_agent_job(db, agent_id, job_id)
    event_type = str(payload.get("type") or payload.get("event_type") or "job.event")
    status = str(payload.get("status") or job.status)
    event = record_job_event(
        db,
        agent_id=agent_id,
        job_id=job_id,
        event_type=event_type,
        status=status,
        message=str(payload.get("message") or ""),
        payload=payload,
    )
    if event_type == "job.approval_required":
        job.status = "APPROVAL_REQUIRED"
        approval_payload = dict(payload.get("approval") or payload)
        approval = ApprovalRequest(
            agent_id=agent_id,
            job_id=job_id,
            approval_id=str(approval_payload.get("approval_id") or ""),
            plan_hash=str(approval_payload.get("plan_hash") or ""),
            risk=str(approval_payload.get("risk") or "dangerous"),
            warning=str(approval_payload.get("warning") or ""),
            plan=list(approval_payload.get("plan") or []),
            status="PENDING",
        )
        expires = approval_payload.get("expires_at")
        if isinstance(expires, datetime):
            approval.expires_at = expires
        db.add(approval)
    elif event_type == "job.input_required":
        job.status = "INPUT_REQUIRED"
    elif event_type in {"job.completed", "result"} or status.lower() == "success":
        job.status = "SUCCESS"
        job.result = payload
        db.add(JobResult(agent_id=agent_id, job_id=job_id, status="SUCCESS", payload=payload))
    elif event_type == "job.failed" or status.lower() == "failed":
        job.status = "FAILED"
        job.error = payload
        db.add(JobResult(agent_id=agent_id, job_id=job_id, status="FAILED", payload=payload))
    return event


def decide_approval(db: Session, *, agent_id: str, job_id: str, approval_id: str, plan_hash: str, decision: str, actor: str) -> ApprovalDecision:
    approval = db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.agent_id == agent_id,
            ApprovalRequest.job_id == job_id,
            ApprovalRequest.approval_id == approval_id,
            ApprovalRequest.plan_hash == plan_hash,
        )
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="APPROVAL_NOT_FOUND")
    if approval.status != "PENDING":
        raise HTTPException(status_code=409, detail="APPROVAL_REPLAY")
    expires_at = normalize_timestamp(approval.expires_at)
    if expires_at and expires_at < now_utc():
        approval.status = "EXPIRED"
        raise HTTPException(status_code=409, detail="APPROVAL_EXPIRED")
    approval.status = "APPROVED" if decision == "approved" else "REJECTED"
    record = ApprovalDecision(
        agent_id=agent_id,
        job_id=job_id,
        approval_id=approval_id,
        plan_hash=plan_hash,
        decision=decision,
        decided_by=actor,
    )
    db.add(record)
    job = get_agent_job(db, agent_id, job_id)
    if decision == "approved":
        job.approver = actor
        record_job_event(db, agent_id=agent_id, job_id=job_id, event_type="job.approved", status="APPROVED")
    else:
        job.status = "FAILED"
        record_job_event(db, agent_id=agent_id, job_id=job_id, event_type="job.rejected", status="REJECTED")
    return record


def apply_agent_heartbeat(db: Session, *, agent: Agent, payload: dict) -> AgentHeartbeat:
    observed_at = now_utc()
    agent.last_heartbeat_at = observed_at
    agent.status = str(payload.get("status") or "ONLINE").upper()
    if agent.status == "HEALTHY":
        agent.status = "ONLINE"
    agent.agent_version = payload.get("agent_version") or agent.agent_version
    agent.sindri_version = payload.get("sindri_version") or agent.sindri_version
    agent.sindri_protocol_version = payload.get("sindri_protocol_version") or agent.sindri_protocol_version
    agent.hostname = payload.get("hostname") or agent.hostname
    agent.boot_id = payload.get("boot_id") or agent.boot_id
    agent.queue_length = int(payload.get("queue_length") or 0)
    agent.current_job_id = payload.get("current_job_id")
    agent.metadata_json = {**(agent.metadata_json or {}), "resources": payload.get("resources") or {}, "listener": payload.get("listener") or {}}
    safe_payload = json_safe(payload)
    heartbeat = AgentHeartbeat(agent_id=agent.id, payload=safe_payload, observed_at=observed_at)
    db.add(heartbeat)
    db.add(
        AgentStateEvent(
            agent_id=agent.id,
            sequence=(db.scalar(select(func.count(AgentStateEvent.id)).where(AgentStateEvent.agent_id == agent.id)) or 0) + 1,
            event_type="agent.heartbeat",
            status=agent.status,
            payload=safe_payload,
        )
    )
    return heartbeat


def _read_cpu_totals() -> tuple[int, int] | None:
    try:
        first = next(line for line in open("/proc/stat", "r", encoding="utf-8") if line.startswith("cpu "))
    except (OSError, StopIteration):
        return None
    values = [int(value) for value in first.split()[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return idle, total


def _read_cpu_percent() -> float:
    first = _read_cpu_totals()
    if first is None:
        return 0.0
    time.sleep(0.05)
    second = _read_cpu_totals()
    if second is None:
        return 0.0
    idle_delta = second[0] - first[0]
    total_delta = second[1] - first[1]
    if total_delta <= 0:
        return 0.0
    return round(max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta))), 1)


def _read_ram() -> tuple[int, int, float]:
    try:
        data = {}
        for line in open("/proc/meminfo", "r", encoding="utf-8"):
            key, raw = line.split(":", 1)
            data[key] = int(raw.strip().split()[0]) * 1024
        total = data.get("MemTotal", 0)
        available = data.get("MemAvailable", 0)
        used = max(0, total - available)
    except OSError:
        total = used = 0
    percent = round((used / total * 100.0) if total else 0.0, 1)
    return used, total, percent


def build_system_metrics() -> dict:
    ram_used, ram_total, ram_percent = _read_ram()
    disk = shutil.disk_usage("/")
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as uptime_file:
            uptime_seconds = int(float(uptime_file.read().split()[0]))
    except (OSError, ValueError, IndexError):
        uptime_seconds = int(time.monotonic())
    return {
        "cpu_percent": _read_cpu_percent(),
        "ram_used_bytes": ram_used,
        "ram_total_bytes": ram_total,
        "ram_percent": ram_percent,
        "disk_used_bytes": disk.used,
        "disk_total_bytes": disk.total,
        "disk_percent": round(disk.used / disk.total * 100.0, 1) if disk.total else 0.0,
        "uptime_seconds": max(0, uptime_seconds),
    }


def build_topology_snapshot(db: Session) -> dict:
    settings = Settings()
    objects = db.scalars(select(PerimetrObject).order_by(PerimetrObject.created_at.asc())).all()
    subjects = db.scalars(select(Subject).order_by(Subject.created_at.asc())).all()
    pods = db.scalars(select(Pod).order_by(Pod.created_at.asc())).all()
    agents = db.scalars(select(Agent).order_by(Agent.created_at.asc())).all()
    assignments = db.scalars(select(AgentAssignment).order_by(AgentAssignment.block_type.asc(), AgentAssignment.block_id.asc(), AgentAssignment.position.asc())).all()
    capabilities = db.scalars(select(AgentCapability).order_by(AgentCapability.agent_id.asc(), AgentCapability.action.asc())).all()
    commands = db.scalars(select(AgentCommand).order_by(AgentCommand.created_at.desc())).all()
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
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "display_name": agent.display_name or agent.name,
                "agent_type": agent.agent_type,
                "host_id": agent.host_id,
                "status": visible_agent_status(agent, agent_assignment_count(db, agent.id)),
                "api_base_url": agent.api_base_url,
                "domain": agent.domain,
                "port": agent.port,
                "resolved_ip": agent.resolved_ip,
                "assignment_count": agent_assignment_count(db, agent.id),
                "identity_fingerprint": agent.identity_fingerprint,
                "certificate_serial": agent.certificate_serial,
                "agent_version": agent.agent_version,
                "sindri_version": agent.sindri_version,
                "sindri_protocol_version": agent.sindri_protocol_version,
                "last_heartbeat_at": agent.last_heartbeat_at.isoformat() if agent.last_heartbeat_at else None,
            }
            for agent in agents
        ],
        "agent_assignments": [
            {
                "id": item.id,
                "agent_id": item.agent_id,
                "block_id": item.block_id,
                "block_type": item.block_type,
                "position": item.position,
                "created_by": item.created_by,
                "created_at": item.created_at.isoformat(),
            }
            for item in assignments
        ],
        "agent_capabilities": [
            {
                "agent_id": item.agent_id,
                "action": item.action,
                "title": item.title,
                "group": item.group,
                "risk": item.risk,
                "inputs": item.inputs,
                "available": item.available,
            }
            for item in capabilities
        ],
        "commands": [
            {
                "id": command.id,
                "agent_id": command.agent_id,
                "command": command.command,
                "status": command.status,
                "target": command.target,
                "params": command.params,
                "result": command.result,
                "created_at": command.created_at.isoformat(),
                "finished_at": command.finished_at.isoformat() if command.finished_at else None,
            }
            for command in commands[:60]
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


ALLOWED_AGENT_COMMANDS = {"status", "logs", "restart", "stop"}


def ensure_allowed_agent_command(command: str) -> None:
    if command not in ALLOWED_AGENT_COMMANDS:
        raise HTTPException(status_code=400, detail=f"unsupported command: {command}")


def list_pending_agent_commands(db: Session, agent_id: str) -> list[AgentCommand]:
    return db.scalars(
        select(AgentCommand)
        .where(
            AgentCommand.agent_id == agent_id,
            AgentCommand.status == CommandStatus.accepted.value,
        )
        .order_by(AgentCommand.created_at.asc())
    ).all()


def update_agent_command_status(
    db: Session,
    command: AgentCommand,
    *,
    status: str,
    result: dict | None = None,
) -> AgentCommand:
    if status == CommandStatus.running.value:
        if command.status != CommandStatus.accepted.value:
            raise HTTPException(status_code=409, detail="command is not pending")
        command.status = CommandStatus.running.value
        command.started_at = now_utc()
        command.result = result or {}
        return command

    if status == CommandStatus.succeeded.value:
        if command.status not in {CommandStatus.accepted.value, CommandStatus.running.value}:
            raise HTTPException(status_code=409, detail="command cannot be completed")
        command.status = CommandStatus.succeeded.value
        command.finished_at = now_utc()
        command.result = result or {}
        return command

    if status == CommandStatus.failed.value:
        if command.status not in {CommandStatus.accepted.value, CommandStatus.running.value}:
            raise HTTPException(status_code=409, detail="command cannot be completed")
        command.status = CommandStatus.failed.value
        command.finished_at = now_utc()
        command.result = result or {}
        return command

    raise HTTPException(status_code=400, detail=f"unsupported command status: {status}")
