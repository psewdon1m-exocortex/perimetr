"""Operator recovery and update protocol. All archives are request-local memory."""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import select

from . import updater_client
from .backup_service.snapshot import InvalidBackup, build_snapshot, preflight, restore_snapshot
from .database import get_db
from .settings import get_settings
from .models import SystemSetting


def require_synced_kernel(db):
    record = db.scalar(select(SystemSetting).where(SystemSetting.key == "perimetr.kernel"))
    if record and record.value.get("helper_sync_required"):
        raise HTTPException(409, "Synchronize the host connection with perimetr-install sync-kernel before updating")


def require_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise HTTPException(422, "Invalid operation identifier")
    return value


def call_helper(method, path, payload=None, timeout=35):
    settings = get_settings()
    try:
        return updater_client.request(settings.updater_socket_path, method, path, payload,
                                      timeout=timeout, control_token=settings.updater_control_token)
    except (OSError, RuntimeError) as exc:
        # Helper exceptions can contain URLs or upstream credentials.
        raise HTTPException(503, "Updater unavailable; reconnect and look up the existing request before retrying") from exc


def receipt(data, filename, request_id, version, settings):
    if not settings.updater_control_token:
        raise HTTPException(503, "Updater control credential is not configured")
    fields = {"schema": "exocortex.update-backup.v2", "id": request_id, "head_id": settings.updater_head_id,
              "service": "perimetr", "version": version, "sha256": hashlib.sha256(data).hexdigest(),
              "size": len(data), "filename": filename, "expires": int(time.time()) + 900}
    encoded = base64.urlsafe_b64encode(json.dumps(fields, separators=(",", ":")).encode()).rstrip(b"=")
    signature = base64.urlsafe_b64encode(hmac.new(settings.updater_control_token.encode(), encoded, hashlib.sha256).digest()).rstrip(b"=")
    return (encoded + b"." + signature).decode()


def verify_receipt(token, data, request_id, version, settings):
    try:
        encoded, signed = token.encode().split(b".")
        actual = base64.urlsafe_b64encode(hmac.new(settings.updater_control_token.encode(), encoded, hashlib.sha256).digest()).rstrip(b"=")
        fields = json.loads(base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4)))
        if (not settings.updater_control_token or not hmac.compare_digest(signed, actual) or
            fields["schema"] != "exocortex.update-backup.v2" or fields["head_id"] != settings.updater_head_id or
            fields["service"] != "perimetr" or fields["id"] != request_id or fields["version"] != version or
            not time.time() < fields["expires"] <= time.time() + 901 or fields["size"] != len(data) or
            fields["sha256"] != hashlib.sha256(data).hexdigest()):
            raise ValueError()
        return fields
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise HTTPException(409, "Saved backup receipt is invalid, expired or belongs to another update") from exc


async def archive_body(request):
    maximum = get_settings().perimetr_max_backup_upload_bytes
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > maximum:
            raise HTTPException(413, "Backup exceeds upload limit")
        content.extend(chunk)
    if not content.startswith(b"PK"):
        raise HTTPException(400, "Expected the original ZIP bytes")
    return bytes(content)


def register(app, require_access):
    router = APIRouter(dependencies=[Depends(require_access)])

    @app.exception_handler(InvalidBackup)
    async def invalid_backup(_, exc):
        return JSONResponse({"error": {"message": str(exc)}}, status_code=400)

    @router.post("/v1/backups")
    def download_backup(db: Session = Depends(get_db)):
        data = build_snapshot(db, get_settings()).getvalue()
        return Response(data, media_type="application/zip", headers={
            "Content-Disposition": 'attachment; filename="perimetr-full-backup.zip"',
            "X-Backup-Sha256": hashlib.sha256(data).hexdigest()})

    @router.get("/v1/backups")
    def backup_history():
        return []  # Deliberately no retained server archive or download link.

    @router.post("/v1/backups/preflight")
    async def inspect_backup(request: Request):
        return preflight(await archive_body(request), get_settings())

    @router.post("/v1/backups/import")
    async def import_backup(request: Request, x_backup_sha256: str = Header(), x_confirm_replace: str = Header(), db: Session = Depends(get_db)):
        data = await archive_body(request)
        if x_confirm_replace != "true" or not hmac.compare_digest(x_backup_sha256, hashlib.sha256(data).hexdigest()):
            raise HTTPException(409, "Review and confirm the exact snapshot before replacing current data")
        result = restore_snapshot(data, db, get_settings())
        db.commit()
        from .kernel_connection import apply_connection
        apply_connection(get_settings(), db, require_helper_sync=True)
        db.commit()
        return result

    @router.get("/v1/updater/status")
    def updater_status():
        result = updater_client.status(get_settings().updater_socket_path)
        result["compatible"] = result.get("update_protocol") == 2 and result.get("backup_policy") == "operator-copy"
        return result

    @router.post("/v1/updater/check")
    def check_update(component: str = Query("perimetr", pattern="^(perimetr|updater)$"), db: Session = Depends(get_db)):
        require_synced_kernel(db)
        return call_helper("POST", "/v2/check", {"head_id": get_settings().updater_head_id, "component": component})

    @router.post("/v1/updater/prepare")
    def prepare(payload: dict, db: Session = Depends(get_db)):
        request_id = require_id(str(payload.get("request_id", "")))
        version = str(payload.get("version", ""))
        if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version) or version == "0.0.0":
            raise HTTPException(422, "Select a stable published release")
        candidate = check_update("perimetr", db)
        if not candidate.get("update_available") or candidate.get("available_version") != version:
            raise HTTPException(409, "Refresh the current upgrade candidate")
        settings = get_settings()
        data = build_snapshot(db, settings).getvalue()
        filename = f"perimetr-before-{version}-{request_id}.zip"
        return Response(data, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Backup-Receipt": receipt(data, filename, request_id, version, settings),
            "X-Backup-Sha256": hashlib.sha256(data).hexdigest(), "X-Backup-Filename": filename})

    @router.get("/v1/updater/jobs")
    def jobs(request_id: str | None = None):
        result = call_helper("GET", "/v1/jobs?head_id=" + quote(get_settings().updater_head_id, safe=""))
        if request_id:
            require_id(request_id)
            result["jobs"] = [job for job in result.get("jobs", []) if job.get("request_id") == request_id]
        return result

    @router.post("/v1/updater/install")
    async def install(request: Request, request_id: str, version: str, x_backup_receipt: str = Header(), x_operator_saved: str = Header(), db: Session = Depends(get_db)):
        require_synced_kernel(db)
        require_id(request_id)
        data = await archive_body(request)
        if x_operator_saved != "true":
            raise HTTPException(409, "Save the ZIP and explicitly acknowledge the operator copy first")
        fields = verify_receipt(x_backup_receipt, data, request_id, version, get_settings())
        existing = jobs(request_id).get("jobs", [])
        if existing:
            if any(job.get("head_id") != get_settings().updater_head_id or job.get("service") != "perimetr" or job.get("version") != version for job in existing):
                raise HTTPException(409, "Operation identifier already belongs to another update")
            return JSONResponse(existing[0], status_code=202)
        job = call_helper("POST", "/v2/updates", {"request_id": request_id, "head_id": get_settings().updater_head_id,
                          "service": "perimetr", "version": version, "operator_saved": True, "backup_receipt": x_backup_receipt,
                          "backup": {"filename": fields["filename"], "sha256": fields["sha256"],
                                     "data_base64": base64.b64encode(data).decode()}}, timeout=60)
        return JSONResponse(job, status_code=202)

    @router.get("/v1/updater/jobs/{job_id}")
    def job_status(job_id: str):
        job = call_helper("GET", f"/v1/jobs/{require_id(job_id)}")
        if job.get("head_id") != get_settings().updater_head_id:
            raise HTTPException(404, "Job not found")
        return job

    @router.post("/v1/updater/component")
    def update_helper(payload: dict, db: Session = Depends(get_db)):
        require_synced_kernel(db)
        request_id = require_id(str(payload.get("request_id", "")))
        version = str(payload.get("version", ""))
        if payload.get("component") != "updater":
            raise HTTPException(422, "Unsupported Perimetr component")
        return JSONResponse(call_helper("POST", "/v2/components/updater/updates", {
            "head_id": get_settings().updater_head_id, "version": version, "request_id": request_id}), status_code=202)

    @router.post("/v1/updater/jobs/{job_id}/rollback")
    async def rollback(job_id: str, request: Request, x_backup_filename: str = Header()):
        job = job_status(job_id)
        data = await archive_body(request)
        checksum = hashlib.sha256(data).hexdigest()
        if checksum != job.get("backup_sha256") or x_backup_filename != job.get("backup_filename"):
            raise HTTPException(409, "Select the original saved ZIP for this job")
        return JSONResponse(call_helper("POST", f"/v2/jobs/{require_id(job_id)}/rollback", {
            "filename": x_backup_filename, "sha256": checksum, "data_base64": base64.b64encode(data).decode()}), status_code=202)

    app.include_router(router)

    @app.post("/v1/internal/updater/restore")
    async def internal_restore(request: Request, x_updater_token: str = Header(), db: Session = Depends(get_db)):
        expected = get_settings().updater_control_token
        if not expected or not hmac.compare_digest(expected, x_updater_token):
            raise HTTPException(403, "Updater authentication required")
        # The helper sends one multipart member. Parse in bounded memory, never UploadFile's disk spool.
        from email.parser import BytesParser
        from email.policy import default
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > get_settings().perimetr_max_backup_upload_bytes + 65536:
                raise HTTPException(413, "Backup exceeds upload limit")
            data.extend(chunk)
        message = BytesParser(policy=default).parsebytes(b"Content-Type: " + request.headers.get("content-type", "").encode() + b"\r\n\r\n" + data)
        parts = list(message.iter_parts()) if message.is_multipart() else []
        if len(parts) != 1 or parts[0].get_param("name", header="content-disposition") != "archive":
            raise HTTPException(400, "Expected one archive")
        result = restore_snapshot(parts[0].get_payload(decode=True), db, get_settings())
        db.commit()
        from .kernel_connection import apply_connection
        apply_connection(get_settings(), db, require_helper_sync=True)
        db.commit()
        return result
