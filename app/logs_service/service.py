from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import AuditEvent
from ..settings import Settings


def trim_audit_events(db: Session, settings: Settings) -> None:
    max_entries = max(int(settings.perimetr_audit_max_entries), 1)
    retention_days = max(int(settings.perimetr_audit_retention_days), 1)
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    db.execute(delete(AuditEvent).where(AuditEvent.created_at < cutoff))
    stale_events = db.scalars(
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .offset(max_entries)
    ).all()
    for stale in stale_events:
        db.delete(stale)


def _entity_log_key(event: AuditEvent) -> str:
    return f"{event.target_type}_{event.target_id}"


def write_audit_log(settings: Settings, event: AuditEvent) -> None:
    log_dir = Path(settings.perimetr_logs_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": event.id,
        "actor_type": event.actor_type,
        "actor_id": event.actor_id,
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "payload": event.payload,
        "result": event.result,
        "created_at": event.created_at.isoformat(),
    }
    for path in [log_dir / "audit.jsonl", log_dir / f"{_entity_log_key(event)}.jsonl"]:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        trim_log_file(
            path,
            max_lines=max(int(settings.perimetr_audit_max_entries), 1),
            max_bytes=max(int(settings.perimetr_log_max_file_bytes), 1024),
        )
    trim_log_directory(
        log_dir,
        retention_days=max(int(settings.perimetr_audit_retention_days), 1),
        max_total_bytes=max(int(settings.perimetr_logs_max_total_bytes), 1024),
    )


def trim_log_file(path: Path, *, max_lines: int, max_bytes: int) -> None:
    if not path.exists():
        return
    lines = path.read_bytes().splitlines(keepends=True)
    if len(lines) <= max_lines and sum(len(line) for line in lines) <= max_bytes:
        return
    retained: list[bytes] = []
    retained_bytes = 0
    for line in reversed(lines[-max_lines:]):
        if len(line) > max_bytes:
            continue
        if retained and retained_bytes + len(line) > max_bytes:
            break
        retained.append(line)
        retained_bytes += len(line)
    path.write_bytes(b"".join(reversed(retained)))


def trim_log_directory(log_dir: Path, *, retention_days: int, max_total_bytes: int) -> None:
    if not log_dir.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(retention_days, 1))
    paths = [path for path in log_dir.glob("*.jsonl") if path.is_file()]
    for path in paths:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified < cutoff:
            path.unlink(missing_ok=True)
    paths = [path for path in log_dir.glob("*.jsonl") if path.is_file()]
    total_bytes = sum(path.stat().st_size for path in paths)
    if total_bytes <= max_total_bytes:
        return
    # Keep the aggregate audit stream until entity-specific history has been removed.
    paths.sort(key=lambda path: (path.name == "audit.jsonl", path.stat().st_mtime))
    for path in paths:
        if total_bytes <= max_total_bytes:
            break
        size = path.stat().st_size
        path.unlink(missing_ok=True)
        total_bytes -= size
