"""Kernel URL is database-owned; the machine token has separate secret storage."""
from __future__ import annotations

import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .kernel_register import load_snapshot, apply_register, KernelRegisterError
from .models import SystemSetting
from .operator_settings import ensure_preferences
from .security import verify_password
from .settings import Settings, get_settings
from .request_policy import client_identity
from .services import audit

KEY = "perimetr.kernel"


def token_path(settings):
    return Path(settings.perimetr_state_dir) / "secrets" / "kernel-service-token"


def apply_connection(settings, db, *, require_helper_sync=False):
    record = db.scalar(select(SystemSetting).where(SystemSetting.key == KEY))
    if record is None:
        record = SystemSetting(scope="perimetr", key=KEY, value={"url": settings.kernel_url, "helper_sync_required": False})
        db.add(record); db.flush()
    if require_helper_sync:
        record.value = {**record.value, "helper_sync_required": True}
    from . import settings as settings_module
    settings_module.kernel_url_override = str(record.value.get("url", ""))
    get_settings.cache_clear()


def valid_url(value, settings):
    if not isinstance(value, str):
        raise HTTPException(422, "Supply a Kernel origin")
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError as exc:
        raise HTTPException(422, "Invalid Kernel origin") from exc
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or
        parsed.path not in {"", "/"} or (parsed.scheme != "https" and not
        (settings.perimetr_env == "development" and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}))):
        raise HTTPException(422, "Kernel URL must be an HTTPS origin without credentials")
    return value.rstrip("/")


def probe(url, token, settings):
    if not token:
        raise HTTPException(409, "Configure the Kernel service token first")
    try:
        snapshot = load_snapshot(kernel_url=url, service_token=token, cache_path=settings.kernel_cache_path,
                                 timeout_seconds=settings.kernel_timeout_sec, require_fresh=True, persist_cache=False)
        apply_register(settings.model_copy(update={"kernel_url": url, "kernel_service_token": token}), snapshot=snapshot)
        return snapshot.get("revision")
    except KernelRegisterError as exc:
        raise HTTPException(502, "Kernel authentication or Register validation failed; previous configuration retained") from exc


def register(app, require_access):
    router = APIRouter(dependencies=[Depends(require_access)])

    @router.get("/v1/settings/kernel")
    def read(db: Session = Depends(get_db)):
        settings = get_settings()
        record = db.scalar(select(SystemSetting).where(SystemSetting.key == KEY))
        return {"url": record.value["url"] if record else settings.kernel_url,
                "token_configured": bool(settings.kernel_service_token),
                "register_stale": settings.kernel_register_stale,
                "helper_sync_required": bool(record and record.value.get("helper_sync_required"))}

    @router.post("/v1/settings/kernel/check")
    def check():
        settings = get_settings()
        return {"reachable": True, "revision": probe(settings.kernel_url, settings.kernel_service_token, settings)}

    @router.patch("/v1/settings/kernel")
    def save(payload: dict, db: Session = Depends(get_db)):
        settings = get_settings()
        if set(payload) != {"url"}:
            raise HTTPException(422, "Only the Kernel origin belongs to this setting")
        url = valid_url(payload["url"], settings)
        probe(url, settings.kernel_service_token, settings)
        record = db.scalar(select(SystemSetting).where(SystemSetting.key == KEY))
        if record is None:
            record = SystemSetting(scope="perimetr", key=KEY, value={}); db.add(record)
        record.value = {"url": url, "helper_sync_required": True}
        audit(db, actor_type="operator", actor_id="core", action="kernel.origin.changed", target_type="settings", target_id="kernel", result={"outcome": "success"})
        db.commit(); apply_connection(settings, db); db.commit()
        return read(db)

    @router.post("/v1/settings/kernel/token")
    def rotate(payload: dict, request: Request, db: Session = Depends(get_db)):
        settings = get_settings()
        if set(payload) != {"current_key", "token"} or not all(isinstance(payload[key], str) for key in payload):
            raise HTTPException(422, "Supply the current Access Key and replacement machine token")
        auth = ensure_preferences(db, settings).value["auth"]
        identity = "kernel-rotation:" + client_identity(request, settings.perimetr_trusted_proxies)
        limiter = request.app.state.login_rate_limiter
        if not limiter.check(identity).allowed:
            raise HTTPException(429, "Too many unsuccessful key checks")
        if not verify_password(payload["current_key"], auth["access_key_hash"]):
            limiter.fail(identity)
            raise HTTPException(403, "Current Access Key is incorrect")
        limiter.success(identity)
        token = payload["token"]
        if not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise HTTPException(422, "Invalid machine token transport encoding")
        probe(settings.kernel_url, token, settings)
        path = token_path(settings)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = path.with_name(".kernel-" + secrets.token_hex(8))
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                stream.write(token); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        record = db.scalar(select(SystemSetting).where(SystemSetting.key == KEY))
        if record is None:
            record = SystemSetting(scope="perimetr", key=KEY, value={"url": settings.kernel_url}); db.add(record)
        record.value = {**record.value, "helper_sync_required": True}
        audit(db, actor_type="operator", actor_id="core", action="kernel.credential.changed", target_type="settings", target_id="kernel", result={"outcome": "success"})
        db.commit(); get_settings.cache_clear()
        return {"changed": True, "helper_sync_required": True}

    app.include_router(router)


def main():
    """Installer-only pipe. Never call this export from a web route."""
    import json
    import sys
    from .database import SessionLocal
    with SessionLocal() as db:
        record = db.scalar(select(SystemSetting).where(SystemSetting.key == KEY))
        if len(sys.argv) == 2 and sys.argv[1] == "synced":
            if record:
                record.value = {**record.value, "helper_sync_required": False}; db.commit()
            return
        if len(sys.argv) != 2 or sys.argv[1] != "export-for-installer":
            raise SystemExit("This command is reserved for perimetr-install sync-kernel")
        settings = Settings()
        secret = token_path(settings)
        if secret.is_file():
            settings.kernel_service_token = secret.read_text(encoding="utf-8")
        sys.stdout.write(json.dumps({"KERNEL_URL": record.value["url"] if record else settings.kernel_url,
                                     "KERNEL_SERVICE_TOKEN": settings.kernel_service_token}))


if __name__ == "__main__":
    main()
