from enum import Enum


class ObjectKind(str, Enum):
    workspace = "workspace"
    service = "service"
    website = "website"
    module = "module"


class RuntimeType(str, Enum):
    web = "web"




class LaunchDecision(str, Enum):
    approved = "approved"
    revoked = "revoked"
    pending = "pending"


class SessionStatus(str, Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"
