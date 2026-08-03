from datetime import datetime, timezone
import secrets
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


ENTITY_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ123456789"


def new_entity_id() -> str:
    return "".join(secrets.choice(ENTITY_ID_ALPHABET) for _ in range(16))


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class PerimetrObject(Base, TimestampMixin):
    __tablename__ = "objects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    entity_id: Mapped[str] = mapped_column(String(16), unique=True, index=True, default=new_entity_id)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    image_data: Mapped[str] = mapped_column(Text, default="")
    image_media_type: Mapped[str] = mapped_column(String(64), default="")

    subjects: Mapped[list["Subject"]] = relationship(back_populates="object")

    @property
    def image_url(self) -> str | None:
        return f"/v1/objects/{self.entity_id}/image?v={int(self.updated_at.timestamp() * 1_000_000)}" if self.image_data else None


class AccessPolicy(Base, TimestampMixin):
    __tablename__ = "access_policies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    scope_type: Mapped[str] = mapped_column(String(64), index=True)
    scope_id: Mapped[str] = mapped_column(String(32), index=True)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    scope: Mapped[str] = mapped_column(String(64), index=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    entity_id: Mapped[str] = mapped_column(String(16), unique=True, index=True, default=new_entity_id)
    object_id: Mapped[str | None] = mapped_column(ForeignKey("objects.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="Subject")
    kind: Mapped[str] = mapped_column(String(32), default="workspace", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    image_data: Mapped[str] = mapped_column(Text, default="")
    image_media_type: Mapped[str] = mapped_column(String(64), default="")
    runtime_type: Mapped[str] = mapped_column(String(32), index=True)
    pod_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    access_policy_id: Mapped[str | None] = mapped_column(ForeignKey("access_policies.id"), nullable=True)
    primary_route: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vless_uri_encrypted: Mapped[str] = mapped_column(Text, default="")
    network_profile_version: Mapped[int] = mapped_column(Integer, default=1)
    system_tabs: Mapped[list[dict]] = mapped_column(JSON, default=list)
    system_tabs_profile_version: Mapped[int] = mapped_column(Integer, default=1)
    update_channel: Mapped[str] = mapped_column(String(32), default="stable")
    ui_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    security_policy: Mapped[dict] = mapped_column(JSON, default=dict)

    object: Mapped[PerimetrObject | None] = relationship(back_populates="subjects")
    pods: Mapped[list["Pod"]] = relationship(back_populates="subject")
    access_policy: Mapped["AccessPolicy | None"] = relationship()

    @property
    def network_configured(self) -> bool:
        return bool(self.vless_uri_encrypted)

    @property
    def image_url(self) -> str | None:
        return f"/v1/subjects/{self.entity_id}/image?v={int(self.updated_at.timestamp() * 1_000_000)}" if self.image_data else None


class Pod(Base, TimestampMixin):
    __tablename__ = "pods"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    provisioning_id: Mapped[str | None] = mapped_column(ForeignKey("pod_provisioning_records.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="Pod")
    login: Mapped[str] = mapped_column(String(255), default="pod", index=True)
    password_hash: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    host_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    path: Mapped[str] = mapped_column(String(1024), default="")
    launcher_path: Mapped[str] = mapped_column(String(1024), default="")
    runtime_state: Mapped[dict] = mapped_column(JSON, default=dict)
    is_portable: Mapped[bool] = mapped_column(Boolean, default=True)
    last_materialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    public_key_pem: Mapped[str] = mapped_column(Text, default="")
    identity_certificate: Mapped[str] = mapped_column(Text, default="")
    certificate_fingerprint: Mapped[str] = mapped_column(String(255), default="", index=True)
    device_binding_fingerprint: Mapped[str] = mapped_column(String(255), default="", index=True)
    device_binding_status: Mapped[str] = mapped_column(String(32), default="pending")
    pod_version: Mapped[str] = mapped_column(String(64), default="0.1.0")
    xray_version: Mapped[str] = mapped_column(String(64), default="unknown")
    network_profile_version: Mapped[int] = mapped_column(Integer, default=1)
    system_tabs_profile_version: Mapped[int] = mapped_column(Integer, default=1)
    heartbeat_sequence: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str] = mapped_column(Text, default="")

    subject: Mapped[Subject] = relationship(back_populates="pods")
    provisioning: Mapped["PodProvisioningRecord | None"] = relationship(back_populates="instances")


class PodProvisioningRecord(Base, TimestampMixin):
    __tablename__ = "pod_provisioning_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), default="New Pod Bundle")
    login: Mapped[str] = mapped_column(String(255), default="pod", index=True)
    password_hash: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    enrollment_token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    enrollment_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    bundle_version: Mapped[str] = mapped_column(String(64), default="0.1.0")
    artifact_sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    instances: Mapped[list[Pod]] = relationship(back_populates="provisioning")


class PodDenylist(Base, TimestampMixin):
    __tablename__ = "pod_denylist"
    __table_args__ = (UniqueConstraint("identifier_type", "identifier_value", name="uq_pod_denylist_identifier"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    pod_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    subject_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    identifier_type: Mapped[str] = mapped_column(String(64), index=True)
    identifier_value: Mapped[str] = mapped_column(String(512), index=True)
    reason: Mapped[str] = mapped_column(String(255), default="revoked")


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255))
    agent_type: Mapped[str] = mapped_column(String(32), index=True)
    host_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="registered", index=True)
    identity_fingerprint: Mapped[str] = mapped_column(String(255), index=True)
    api_base_url: Mapped[str] = mapped_column(String(1024))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_ip: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enrollment_state: Mapped[str] = mapped_column(String(32), default="enrolled", index=True)
    identity_certificate: Mapped[str] = mapped_column(Text, default="")
    certificate_serial: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    certificate_valid_not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    certificate_valid_not_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sindri_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sindri_protocol_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    boot_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    queue_length: Mapped[int] = mapped_column(Integer, default=0)
    current_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    environment: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    library_position: Mapped[int] = mapped_column(Integer, default=0, index=True)

    assignments: Mapped[list["AgentAssignment"]] = relationship(back_populates="agent", cascade="all, delete-orphan")
    jobs: Mapped[list["AgentJob"]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class AgentAssignment(Base, TimestampMixin):
    __tablename__ = "agent_assignments"
    __table_args__ = (UniqueConstraint("agent_id", "block_id", "block_type", name="uq_agent_block_assignment"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    block_id: Mapped[str] = mapped_column(String(128), index=True)
    block_type: Mapped[str] = mapped_column(String(32), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String(128), default="operator")

    agent: Mapped[Agent] = relationship(back_populates="assignments")


class AgentEndpoint(Base, TimestampMixin):
    __tablename__ = "agent_endpoints"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    port: Mapped[int] = mapped_column(Integer, default=7443)
    base_url: Mapped[str] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)


class AgentCertificate(Base, TimestampMixin):
    __tablename__ = "agent_certificates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    fingerprint_sha256: Mapped[str] = mapped_column(String(255), index=True)
    serial_number: Mapped[str] = mapped_column(String(255), default="", index=True)
    certificate_pem: Mapped[str] = mapped_column(Text, default="")
    valid_not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_not_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)


class AgentCapability(Base, TimestampMixin):
    __tablename__ = "agent_capabilities"
    __table_args__ = (UniqueConstraint("agent_id", "action", name="uq_agent_capability_action"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    group: Mapped[str] = mapped_column(String(64), default="System", index=True)
    risk: Mapped[str] = mapped_column(String(32), default="read", index=True)
    inputs: Mapped[list[dict]] = mapped_column(JSON, default=list)
    available: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentHeartbeat(Base):
    __tablename__ = "agent_heartbeats"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AgentStateEvent(Base):
    __tablename__ = "agent_state_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    sequence: Mapped[int] = mapped_column(Integer, default=0, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AgentJob(Base, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("agent_id", "job_id", name="uq_agent_job_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(String(128), index=True)
    request_id: Mapped[str] = mapped_column(String(128), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(128), default="operator")
    approver: Mapped[str | None] = mapped_column(String(128), nullable=True)
    canceller: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    plan: Mapped[list[dict]] = mapped_column(JSON, default=list)
    plan_hash: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[dict] = mapped_column(JSON, default=dict)
    log_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sindri_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    agent: Mapped[Agent] = relationship(back_populates="jobs")


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    sequence: Mapped[int] = mapped_column(Integer, default=0, index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    job_id: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class JobResult(Base, TimestampMixin):
    __tablename__ = "job_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    job_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    job_id: Mapped[str] = mapped_column(String(128), index=True)
    approval_id: Mapped[str] = mapped_column(String(128), index=True)
    plan_hash: Mapped[str] = mapped_column(String(255), index=True)
    risk: Mapped[str] = mapped_column(String(32), default="dangerous")
    warning: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[list[dict]] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)


class ApprovalDecision(Base, TimestampMixin):
    __tablename__ = "approval_decisions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    job_id: Mapped[str] = mapped_column(String(128), index=True)
    approval_id: Mapped[str] = mapped_column(String(128), index=True)
    plan_hash: Mapped[str] = mapped_column(String(255), index=True)
    decision: Mapped[str] = mapped_column(String(32), index=True)
    decided_by: Mapped[str] = mapped_column(String(128), default="operator")


class RevocationRecord(Base, TimestampMixin):
    __tablename__ = "revocation_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    certificate_serial: Mapped[str] = mapped_column(String(255), default="")
    certificate_fingerprint_sha256: Mapped[str] = mapped_column(String(255), index=True)
    reason: Mapped[str] = mapped_column(String(255), default="controller_requested")
    status: Mapped[str] = mapped_column(String(32), default="prepared", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class CertificateDenylist(Base, TimestampMixin):
    __tablename__ = "certificate_denylist"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    fingerprint_sha256: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    serial_number: Mapped[str] = mapped_column(String(255), default="")
    reason: Mapped[str] = mapped_column(String(255), default="revoked")


class ControllerIdentity(Base, TimestampMixin):
    __tablename__ = "controller_identity"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    controller_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    certificate_pem: Mapped[str] = mapped_column(Text, default="")
    encrypted_private_key: Mapped[str] = mapped_column(Text, default="")
    encryption_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)


class BackupManifest(Base, TimestampMixin):
    __tablename__ = "backup_manifests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    backup_id: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class LaunchAuthorization(Base, TimestampMixin):
    __tablename__ = "launch_authorizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    pod_id: Mapped[str] = mapped_column(ForeignKey("pods.id"), index=True)
    decision: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SessionLease(Base, TimestampMixin):
    __tablename__ = "session_leases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id"), nullable=True, index=True)
    pod_id: Mapped[str | None] = mapped_column(ForeignKey("pods.id"), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    session_key_hash: Mapped[str] = mapped_column(String(255))
    access_scope: Mapped[str] = mapped_column(String(64), default="perimetr", index=True)
    transport: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentCommand(Base, TimestampMixin):
    __tablename__ = "agent_commands"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    command: Mapped[str] = mapped_column(String(64))
    target: Mapped[dict] = mapped_column(JSON, default=dict)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="accepted", index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    actor_type: Mapped[str] = mapped_column(String(64), index=True)
    actor_id: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    target_type: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
