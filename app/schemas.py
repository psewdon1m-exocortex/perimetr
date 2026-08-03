from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .enums import AgentType, ObjectKind, RuntimeType


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorPayload


class HealthResponse(BaseModel):
    status: str
    service: str


class DirectLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)
    target: str = "perimetr"


class DirectLoginRead(BaseModel):
    approved: bool
    target: str
    transport: str
    renderer_url: str


class StatusResponse(BaseModel):
    perimetr_status: str
    database_status: str
    cache_status: str
    agent_count: int


class SystemMetricsRead(BaseModel):
    cpu_percent: float
    ram_used_bytes: int
    ram_total_bytes: int
    ram_percent: float
    disk_used_bytes: int
    disk_total_bytes: int
    disk_percent: float
    uptime_seconds: int


class OverviewBlockUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OverviewBlockRead(BaseModel):
    id: str
    name: str
    image_url: str | None = None
    updated_at: str


class ObjectCreate(BaseModel):
    name: str
    kind: ObjectKind = ObjectKind.workspace
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class ObjectUpdate(BaseModel):
    name: str | None = None
    kind: ObjectKind | None = None
    description: str | None = None
    tags: list[str] | None = None


class ObjectRead(BaseModel):
    id: str = Field(validation_alias="entity_id")
    name: str
    kind: str
    description: str
    tags: list[str]
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PolicyCreate(BaseModel):
    scope_type: str
    scope_id: str
    rules: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class PolicyUpdate(BaseModel):
    rules: dict[str, Any] | None = None
    status: str | None = None


class PolicyRead(BaseModel):
    id: str
    scope_type: str
    scope_id: str
    rules: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PodSpec(BaseModel):
    host_id: str
    path: str
    launcher_path: str
    is_portable: bool = True


class SubjectCreate(BaseModel):
    object_id: str
    runtime_type: RuntimeType = RuntimeType.web
    access_policy_id: str | None = None
    pod_spec: PodSpec | None = None


class SubjectUpdate(BaseModel):
    name: str | None = None
    access_policy_id: str | None = None
    primary_route: str | None = None


class SystemTab(BaseModel):
    id: str
    title: str
    url: str
    required: bool = True
    position: int = 0


class SubjectPodConfigUpdate(BaseModel):
    vless_connection: str | None = None
    system_tabs: list[SystemTab] | None = None
    update_channel: str | None = None
    ui_policy: dict[str, Any] | None = None
    security_policy: dict[str, Any] | None = None


class SubjectRead(BaseModel):
    id: str = Field(validation_alias="entity_id")
    name: str
    kind: str
    description: str
    tags: list[str]
    image_url: str | None = None
    runtime_type: str
    pod_id: str | None
    access_policy_id: str | None
    primary_route: str | None
    network_configured: bool = False
    network_profile_version: int = 1
    system_tabs: list[dict[str, Any]] = Field(default_factory=list)
    system_tabs_profile_version: int = 1
    update_channel: str = "stable"
    ui_policy: dict[str, Any] = Field(default_factory=dict)
    security_policy: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PodRead(BaseModel):
    id: str
    subject_id: str
    host_id: str
    path: str
    launcher_path: str
    runtime_state: dict[str, Any]
    is_portable: bool
    last_materialized_at: datetime | None
    name: str = "Pod"
    login: str = "pod"
    status: str = "pending"
    certificate_fingerprint: str = ""
    device_binding_fingerprint: str = ""
    device_binding_status: str = "pending"
    pod_version: str = "0.1.0"
    xray_version: str = "unknown"
    network_profile_version: int = 1
    system_tabs_profile_version: int = 1
    last_seen_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    activated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterializeResponse(BaseModel):
    pod_id: str
    launcher_path: str
    state_path: str
    primary_route: str


class LaunchAuthorizationRead(BaseModel):
    id: str
    subject_id: str
    pod_id: str
    decision: str
    reason: str
    issued_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PodHeartbeatRequest(BaseModel):
    status: str
    runtime_state: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime


class PodProvisioningCreate(BaseModel):
    login: str
    password: str
    confirm_password: str


class PodProvisioningRead(BaseModel):
    id: str
    subject_id: str
    name: str
    login: str
    status: str
    bundle_version: str
    artifact_sha256: str = ""
    runtime_source: str = ""
    runtime_warning: str = ""
    download_count: int
    downloaded_at: datetime | None
    expires_at: datetime | None
    activated_at: datetime | None
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime


class PodEnrollRequest(BaseModel):
    provisioning_id: str | None = None
    enrollment_token: str | None = None
    clone_from_pod_id: str | None = None
    username: str
    password: str
    name: str = "Pod"
    public_key_pem: str
    certificate_fingerprint: str
    device_binding_fingerprint: str
    host_id: str = ""
    pod_version: str = "0.1.0"


class PodEnrollRead(BaseModel):
    pod_id: str
    subject_id: str
    identity_certificate: str
    status: str
    next_heartbeat_sequence: int = 1
    config: dict[str, Any]


class PodSignedHeartbeatRequest(BaseModel):
    certificate_fingerprint: str
    sequence: int
    timestamp: datetime
    pod_version: str
    device_binding_fingerprint: str
    device_binding_status: str = "valid"
    proxy_engine: str = "xray-core"
    xray_version: str = "unknown"
    network_status: str = "unknown"
    temporary_tabs_count: int = 0
    signature: str


class PodRenameRequest(BaseModel):
    name: str


class PodPasswordUpdate(BaseModel):
    new_password: str
    confirm_password: str


class AgentRegisterRequest(BaseModel):
    name: str
    agent_type: AgentType
    host_id: str
    api_base_url: str
    identity_fingerprint: str
    capabilities: list[str] = Field(default_factory=list)


class AgentHeartbeatRequest(BaseModel):
    status: str
    reachable: bool
    load: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime


class AgentRead(BaseModel):
    id: str
    name: str
    agent_type: str
    host_id: str
    status: str
    identity_fingerprint: str
    api_base_url: str
    last_heartbeat_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentEnrollRequest(BaseModel):
    agent_id: str
    display_name: str
    domain: str
    port: int = Field(default=7443, ge=1024, le=65535)
    identity_fingerprint: str
    enrollment_token: str | None = None
    identity_certificate: str = ""
    certificate_serial: str | None = None
    api_base_url: str | None = None
    agent_version: str | None = None
    sindri_version: str | None = None
    sindri_protocol_version: str = "1"
    capabilities: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    environment: str = ""
    notes: str = ""


class AgentUpdateRequest(BaseModel):
    display_name: str | None = None
    tags: list[str] | None = None
    environment: str | None = None
    notes: str | None = None


class AgentControlRead(BaseModel):
    id: str
    display_name: str
    status: str
    agent_id: str
    domain: str | None
    port: int | None
    resolved_ip: str | None
    hostname: str | None
    assignment_count: int
    assignments: list[dict[str, str]] = Field(default_factory=list)
    identity_fingerprint: str
    certificate_serial: str | None
    agent_version: str | None
    sindri_version: str | None
    sindri_protocol_version: str | None
    last_heartbeat_at: datetime | None
    tags: list[str]
    environment: str
    notes: str


class AgentAssignmentCreate(BaseModel):
    agent_id: str
    created_by: str = "operator"


class AgentAssignmentRead(BaseModel):
    id: str
    agent_id: str
    block_id: str
    block_type: str
    position: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    agent: AgentControlRead | None = None

    model_config = {"from_attributes": True}


class AgentReorderRequest(BaseModel):
    ordered_agent_ids: list[str]


class AgentControlHeartbeatRequest(BaseModel):
    protocol_version: str = "1"
    agent_id: str
    timestamp: datetime
    sequence: int = 0
    status: str
    agent_version: str | None = None
    sindri_version: str | None = None
    sindri_protocol_version: str | None = None
    hostname: str | None = None
    boot_id: str | None = None
    uptime_seconds: int | None = None
    queue_length: int = 0
    current_job_id: str | None = None
    last_job: dict[str, Any] | None = None
    resources: dict[str, Any] = Field(default_factory=dict)
    listener: dict[str, Any] = Field(default_factory=dict)


class AgentJobCreate(BaseModel):
    action: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    created_by: str = "operator"
    expires_at: datetime | None = None


class AgentJobRead(BaseModel):
    id: str
    job_id: str
    request_id: str
    agent_id: str
    action: str
    inputs: dict[str, Any]
    created_by: str
    approver: str | None
    canceller: str | None
    expires_at: datetime | None
    status: str
    plan: list[dict[str, Any]]
    plan_hash: str | None
    result: dict[str, Any]
    error: dict[str, Any]
    log_reference: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobEventRead(BaseModel):
    id: str
    sequence: int
    agent_id: str
    job_id: str
    event_type: str
    status: str
    message: str
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalDecisionRequest(BaseModel):
    approval_id: str
    plan_hash: str
    decided_by: str = "operator"
    confirmation_phrase: str = ""
    hostname_confirmation: str = ""


class ApprovalRequestRead(BaseModel):
    id: str
    agent_id: str
    job_id: str
    approval_id: str
    plan_hash: str
    risk: str
    warning: str
    plan: list[dict[str, Any]]
    expires_at: datetime | None
    status: str
    action: str = ""
    hostname: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentCommandCreate(BaseModel):
    command: str
    target: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class AgentCommandStatusUpdate(BaseModel):
    status: str
    result: dict[str, Any] = Field(default_factory=dict)


class AgentCommandRead(BaseModel):
    id: str
    agent_id: str
    command: str
    target: dict[str, Any]
    params: dict[str, Any]
    status: str
    result: dict[str, Any]
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CorrelationStateUpdate(BaseModel):
    descriptions_by_block: dict[str, str] = Field(default_factory=dict)
    properties_by_block: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    property_library: list[dict[str, Any]] = Field(default_factory=list)
    graph_settings: dict[str, Any] = Field(default_factory=dict)


class AuditRead(BaseModel):
    id: str
    actor_type: str
    actor_id: str
    action: str
    target_type: str
    target_id: str
    payload: dict[str, Any]
    result: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class BackupRead(BaseModel):
    id: str
    filename: str
    entity_type: str
    entity_id: str
    created_at: str
