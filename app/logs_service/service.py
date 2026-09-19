from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import String, LargeBinary, cast, delete, func, select
from sqlalchemy.orm import Session

from ..models import AuditEvent
from ..redaction import bounded
from ..settings import Settings

_file_lock = threading.Lock()


def trim_audit_events(db: Session, settings: Settings) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(settings.perimetr_audit_retention_days, 1))
    db.execute(delete(AuditEvent).where(AuditEvent.created_at < cutoff))
    payload = cast(AuditEvent.payload, String)
    result = cast(AuditEvent.result, String)
    byte_length = (lambda value: func.octet_length(value)) if db.bind.dialect.name == "postgresql" else (lambda value: func.length(cast(value, LargeBinary)))
    size = byte_length(payload) + byte_length(result) + 4096
    used, count, stale = 0, 0, []
    for event_id, length in db.execute(select(AuditEvent.id, size).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).execution_options(yield_per=200)):
        count += 1
        used += length
        if count > settings.perimetr_audit_max_entries or used > settings.perimetr_audit_max_bytes:
            stale.append(event_id)
    for start in range(0, len(stale), 200):
        db.execute(delete(AuditEvent).where(AuditEvent.id.in_(stale[start:start + 200])))


def serialize(event: AuditEvent) -> dict:
    return bounded({"id": event.id, "created_at": event.created_at.isoformat(),
                    "actor": f"{event.actor_type}:{event.actor_id}", "action": event.action,
                    "target": f"{event.target_type}:{event.target_id}",
                    "payload": event.payload, "result": event.result})


def write_audit_log(settings: Settings, event: AuditEvent) -> None:
    log_dir = Path(settings.perimetr_logs_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(serialize(event), ensure_ascii=True) + "\n").encode()
    path = log_dir / "audit.jsonl"
    with _file_lock:
        if path.exists() and path.stat().st_size + len(line) > settings.perimetr_log_max_file_bytes:
            path.replace(log_dir / f"audit-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}.jsonl")
        with path.open("ab") as handle:
            handle.write(line)
        trim_log_directory(log_dir, retention_days=settings.perimetr_audit_retention_days,
                           max_total_bytes=settings.perimetr_logs_max_total_bytes)


def trim_log_file(path: Path, *, max_lines: int, max_bytes: int) -> None:
    from collections import deque
    retained, total = deque(), 0
    with path.open("rb") as handle:
        for line in handle:
            if len(line) > max_bytes:
                continue
            retained.append(line)
            total += len(line)
            while len(retained) > max_lines or total > max_bytes:
                total -= len(retained.popleft())
    path.write_bytes(b"".join(retained))


def trim_log_directory(log_dir: Path, *, retention_days: int, max_total_bytes: int) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(retention_days, 1))).timestamp()
    files = sorted((p for p in log_dir.glob("*.jsonl") if p.is_file() and not p.is_symlink()), key=lambda p: (p.name == "audit.jsonl", p.stat().st_mtime))
    total = sum(p.stat().st_size for p in files)
    for path in files:
        info = path.stat()
        if info.st_mtime < cutoff or total > max_total_bytes:
            path.unlink(missing_ok=True)
            total -= info.st_size
