from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from .kernel_register import apply_register, KernelRegisterError

kernel_url_override: str | None = None
_last_register = None
_register_fields = ("perimetr_repository_url", "perimetr_pod_repository_url", "perimetr_pod_update_manifest_url", "perimetr_sni", "perimetr_service_port", "perimetr_public_url", "kernel_refresh_sec", "kernel_register_revision")


class Settings(BaseSettings):
    perimetr_version: str = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
    perimetr_env: str = "development"
    perimetr_host: str = "0.0.0.0"
    perimetr_repository_url: str = ""
    perimetr_listen_port: int = 18080
    perimetr_service_port: int = 18080
    perimetr_sni: str = "localhost"
    perimetr_database_url: str = "sqlite:///./perimetr.db"
    perimetr_redis_url: str = "redis://localhost:6379/0"
    # Initial seed only. Once imported, the database verifier is authoritative.
    perimetr_access_key: str | None = None
    perimetr_access_key_hash: str = ""
    perimetr_public_url: str = "http://localhost:18080"
    perimetr_cookie_secure: bool = False
    perimetr_session_ttl_sec: int = 3600
    perimetr_logs_dir: str = str(Path(".tmp") / "perimetr_logs")
    perimetr_audit_max_entries: int = 10000
    perimetr_audit_max_bytes: int = 64 * 1024 * 1024
    perimetr_audit_max_event_bytes: int = 16 * 1024
    perimetr_audit_retention_days: int = 30
    perimetr_log_max_file_bytes: int = 5 * 1024 * 1024
    perimetr_logs_max_total_bytes: int = 64 * 1024 * 1024
    perimetr_max_backup_upload_bytes: int = 128 * 1024 * 1024
    perimetr_backup_max_expanded_bytes: int = 256 * 1024 * 1024
    perimetr_backup_max_member_bytes: int = 64 * 1024 * 1024
    perimetr_backup_max_members: int = 64
    perimetr_backup_max_ratio: int = 200
    perimetr_state_dir: str = str(Path(".tmp"))
    perimetr_data_filesystem: str = ""
    perimetr_trusted_proxies: str = "127.0.0.1,::1"
    perimetr_pod_signing_secret: str = "change-this-pod-signing-secret"
    perimetr_pod_bundle_source: str = "/opt/perimetr/pod-runtime"
    perimetr_pod_cache_dir: str = str(Path(".tmp") / "pod-runtime-cache")
    perimetr_pod_version: str = "0.1.3"
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
    kernel_url: str = ""
    kernel_service_token: str = ""
    kernel_cache_path: str = str(Path(".tmp") / "kernel-cache" / "register.snapshot.json")
    kernel_timeout_sec: float = 3.0
    kernel_refresh_sec: int = 60
    kernel_register_revision: str = ""
    kernel_register_stale: bool = False
    perimetr_update_check_timeout_sec: float = 5.0
    updater_socket_path: str = "/run/exocortex/updater.sock"
    updater_head_id: str = "perimetr"
    updater_control_token: str = ""
    neptune_repository_url: str = ""
    neptune_socket_path: str = "/run/neptune/neptuned.sock"
    neptune_project_id: str = "perimetr"
    neptune_control_token_file: str = "/run/secrets/neptune-control.token"
    neptune_export_token_file: str = "/run/secrets/neptune-export.token"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        def literal_dotenv():
            from dotenv import dotenv_values
            source = dotenv_settings.env_file
            files = [source] if isinstance(source, (str, Path)) else (source or [])
            result = {}
            for filename in files:
                if Path(filename).is_file():
                    result.update({key.lower(): value for key, value in dotenv_values(filename, interpolate=False).items() if value is not None})
            return result
        return init_settings, env_settings, literal_dotenv, file_secret_settings


@lru_cache
def get_settings() -> Settings:
    global _last_register
    settings = Settings()
    expected_version = (Path(__file__).resolve().parents[1] / "VERSION").read_text().strip()
    settings.perimetr_version = expected_version
    if kernel_url_override is not None:
        settings.kernel_url = kernel_url_override
    secret = Path(settings.perimetr_state_dir) / "secrets" / "kernel-service-token"
    if secret.is_file():
        settings.kernel_service_token = secret.read_text(encoding="utf-8")
    identity = (settings.kernel_url, settings.kernel_service_token)
    try:
        resolved = apply_register(settings)
    except KernelRegisterError:
        if _last_register and _last_register[0] == identity:
            return settings.model_copy(update={**_last_register[1], "kernel_register_stale": True})
        raise
    if settings.kernel_url:
        _last_register = (identity, {name: getattr(resolved, name) for name in _register_fields})
    return resolved
