from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from .kernel_register import apply_register


class Settings(BaseSettings):
    perimetr_version: str = "1.2.0"
    perimetr_env: str = "development"
    perimetr_host: str = "0.0.0.0"
    perimetr_repository_url: str = ""
    perimetr_listen_port: int = 18080
    perimetr_service_port: int = 18080
    perimetr_sni: str = "localhost"
    perimetr_database_url: str = "sqlite:///./perimetr.db"
    perimetr_redis_url: str = "redis://localhost:6379/0"
    perimetr_direct_auth_enabled: bool = True
    perimetr_direct_username: str = "admin"
    perimetr_entry_password: str = "perimetr-entry-password"
    perimetr_public_url: str = "http://localhost:18080"
    perimetr_cookie_secure: bool = False
    perimetr_session_ttl_sec: int = 3600
    perimetr_logs_dir: str = str(Path(".tmp") / "perimetr_logs")
    perimetr_audit_max_entries: int = 240
    perimetr_audit_retention_days: int = 30
    perimetr_log_max_file_bytes: int = 5 * 1024 * 1024
    perimetr_logs_max_total_bytes: int = 64 * 1024 * 1024
    perimetr_max_backup_upload_bytes: int = 128 * 1024 * 1024
    perimetr_pod_signing_secret: str = "change-this-pod-signing-secret"
    perimetr_pod_bundle_source: str = "/opt/perimetr/pod-runtime"
    perimetr_pod_cache_dir: str = str(Path(".tmp") / "pod-runtime-cache")
    perimetr_pod_version: str = "0.1.2"
    perimetr_pod_update_public_key_path: str = "/opt/perimetr/pod-runtime/pod-update-public-key.pem"
    perimetr_pod_refresh_sec: int = 900
    perimetr_pod_download_timeout_sec: float = 120.0
    perimetr_pod_max_artifact_bytes: int = 320 * 1024 * 1024
    perimetr_pod_enrollment_ttl_sec: int = 86400
    perimetr_pod_offline_after_sec: int = 90
    perimetr_pod_repository_url: str = ""
    perimetr_pod_update_manifest_url: str = ""
    perimetr_xray_version: str = ""
    perimetr_xray_source_url: str = ""
    perimetr_xray_sha256: str = ""
    perimetr_xray_dns_url: str = ""
    perimetr_proxy_verification_url: str = ""
    perimetr_default_pod_url: str = "about:blank"
    perimetr_agent_request_timeout_sec: float = 10.0
    kernel_url: str = ""
    kernel_service_token: str = ""
    kernel_cache_path: str = str(Path(".tmp") / "kernel-cache" / "register.snapshot.json")
    kernel_timeout_sec: float = 3.0
    kernel_refresh_sec: int = 60
    kernel_register_revision: str = ""
    perimetr_update_check_timeout_sec: float = 5.0
    updater_socket_path: str = "/run/exocortex/updater.sock"
    updater_head_id: str = "perimetr"
    updater_control_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return apply_register(Settings())
