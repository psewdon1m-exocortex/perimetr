from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .enums import ObjectKind, RuntimeType


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorPayload


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str | None = None


class DirectLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    access_key: str
    target: str = "perimetr"


class DirectLoginRead(BaseModel):
    approved: bool
    target: str
    transport: str
    renderer_url: str
    csrf_token: str


class PodLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    username: str
    password: str


class AccessKeyChange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    current_key: str
    new_key: str
    confirm_key: str


class StatusResponse(BaseModel):
    perimetr_status: str
    database_status: str
    cache_status: str


class SystemMetricsRead(BaseModel):
    cpu_percent: float | None
    cpu_cores: int | None
    ram_used_bytes: int | None
    ram_total_bytes: int | None
    ram_percent: float | None
    disk_used_bytes: int | None
    disk_total_bytes: int | None
    disk_percent: float | None
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
    decoy_password: str | None = None
    confirm_decoy_password: str | None = None


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
    access_mode: Literal["primary", "decoy"] = "primary"
    access_grant: str
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
    access_mode: Literal["primary", "decoy"] = "primary"
    access_grant: str = ""
    temporary_tabs_count: int = 0
    signature: str


class PodRenameRequest(BaseModel):
    name: str


class PodPasswordUpdate(BaseModel):
    new_password: str
    confirm_password: str


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
