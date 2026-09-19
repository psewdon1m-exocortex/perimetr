"""Bounded cursor pagination and streamed diagnostic export."""
import base64
from datetime import datetime, timezone
import io
import json
from tempfile import SpooledTemporaryFile
from zipfile import ZipFile, ZIP_DEFLATED

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from .database import get_db
from .logs_service.service import serialize
from .models import AuditEvent
from .settings import get_settings
from .services import audit


def cursor(event):
    return base64.urlsafe_b64encode(json.dumps([event.created_at.isoformat(), event.id]).encode()).decode()


def position(value):
    try:
        stamp, identifier = json.loads(base64.urlsafe_b64decode(value))
        if not isinstance(identifier, str) or len(identifier) != 32:
            raise ValueError()
        return datetime.fromisoformat(stamp), identifier
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, "Invalid log cursor") from exc


def register(app, require_access):
    router = APIRouter(dependencies=[Depends(require_access)])

    @router.post("/v1/audit/ui")
    def record_ui(payload: dict, db: Session = Depends(get_db)):
        if not isinstance(payload.get("payload", {}), dict) or not isinstance(payload.get("result", {}), dict):
            raise HTTPException(422, "Invalid audit context")
        audit(db, actor_type="browser_ui", actor_id="operator", action=str(payload.get("action", "ui.action")),
              target_type=str(payload.get("target_type", "ui")), target_id=str(payload.get("target_id", "perimetr")),
              payload=payload.get("payload", {}), result=payload.get("result", {}))
        db.commit()
        return {"recorded": True}

    @router.get("/v1/logs/audit")
    def read(limit: int = Query(200, ge=1, le=1000), before: str | None = None,
             after: str | None = None, db: Session = Depends(get_db)):
        if before and after:
            raise HTTPException(422, "Select one cursor direction")
        query = select(AuditEvent)
        key = tuple_(AuditEvent.created_at, AuditEvent.id)
        if before:
            query = query.where(key < tuple_( *position(before)))
        if after:
            query = query.where(key > tuple_( *position(after)))
        query = query.order_by(AuditEvent.created_at.asc() if after else AuditEvent.created_at.desc(),
                               AuditEvent.id.asc() if after else AuditEvent.id.desc())
        events = list(db.scalars(query.limit(limit + 1)))
        more = len(events) > limit
        events = events[:limit]
        if after:
            events.reverse()
        return {"entries": [serialize(e) for e in events], "has_more": more,
                "older_cursor": cursor(events[-1]) if events else before,
                "live_cursor": cursor(events[0]) if events else after}

    @router.get("/v1/logs/download")
    def download(db: Session = Depends(get_db)):
        output = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
        count = errors = 0
        # Both files are written incrementally. No raw files or exception dumps
        # bypass the same redaction used for the operator viewer.
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            for filename, errors_only in [("audit-events.jsonl", False), ("errors.jsonl", True)]:
                with archive.open(filename, "w") as member:
                    for event in db.scalars(select(AuditEvent).order_by(AuditEvent.created_at, AuditEvent.id).execution_options(yield_per=200)):
                        outcome = (event.result or {}).get("outcome", (event.result or {}).get("status"))
                        if errors_only and outcome not in {"error", "failed", "denied", "rejected"}:
                            continue
                        member.write((json.dumps(serialize(event), ensure_ascii=True) + "\n").encode())
                        if errors_only:
                            errors += 1
                        else:
                            count += 1
            archive.writestr("manifest.json", json.dumps({"schema": "perimetr.logs.export.v2", "service": "perimetr",
                "version": get_settings().perimetr_version, "generated_at": datetime.now(timezone.utc).isoformat(),
                "event_count": count, "error_count": errors,
                "files": ["audit-events.jsonl", "errors.jsonl", "README.txt"], "redacted": True,
                "retention": {"max_total_bytes": get_settings().perimetr_logs_max_total_bytes}}))
            archive.writestr("README.txt", "Perimetr diagnostic export. Errors use explicit outcomes, not message keywords.\nCredentials are redacted. This archive cannot restore application data.\n")
        output.seek(0)
        def chunks():
            try:
                while chunk := output.read(65536):
                    yield chunk
            finally:
                output.close()
        return StreamingResponse(chunks(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="perimetr-logs.zip"'})

    app.include_router(router)
