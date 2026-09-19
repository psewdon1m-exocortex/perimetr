"""Bounded, authenticated full snapshots. Archives never persist on the server.

Every logical row is encrypted using the separately escrowed Pod recovery secret.
This also protects operator-entered secrets inside free-form domain properties.
Runtime caches, deployment credentials and live leases are never exported.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import stat
from datetime import datetime, timezone
from zipfile import BadZipFile, ZIP_STORED, ZipFile

from cryptography.fernet import InvalidToken
from sqlalchemy import DateTime, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import Base
from ..models import SessionLease, SystemSetting
from ..pod_service import _fernet
from ..security import is_password_hash
from ..settings import Settings

SCHEMA = "perimetr.full-backup.v3"
EXCLUDED = {"session_leases", "backup_manifests"}
TABLE_NAMES = frozenset({
    "objects", "subjects", "access_policies", "system_settings", "pods",
    "pod_provisioning_records", "pod_denylist", "agents", "agent_assignments",
    "agent_endpoints", "agent_certificates", "agent_capabilities", "agent_heartbeats",
    "agent_state_events", "jobs", "job_events", "job_results", "approval_requests",
    "approval_decisions", "revocation_records", "certificate_denylist",
    "controller_identity", "launch_authorizations", "agent_commands", "audit_events",
})
MAX_ROW = 12 * 1024 * 1024


class InvalidBackup(ValueError):
    pass


def tables():
    # A new authoritative model must have an explicit recovery decision.
    if set(Base.metadata.tables) != TABLE_NAMES | EXCLUDED:
        raise RuntimeError("Backup schema must be updated for the current data model")
    return [table for table in Base.metadata.sorted_tables if table.name in TABLE_NAMES]


def encoded(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
                      default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item)).encode("utf-8")


def signature(manifest: dict, settings: Settings) -> str:
    key = hashlib.sha256(("perimetr.backup.v3\0" + settings.perimetr_pod_signing_secret).encode()).digest()
    return hmac.new(key, encoded(manifest), hashlib.sha256).hexdigest()


def build_snapshot(db: Session, settings: Settings) -> io.BytesIO:
    db.flush()
    cipher = _fernet(settings)
    output = io.BytesIO()
    manifest = {"schema": SCHEMA, "service": "perimetr", "version": settings.perimetr_version,
                "database_revision": "0006", "mode": "full-replace", "created_at": datetime.now(timezone.utc).isoformat(),
                "encryption": "fernet-row-v1", "recovery_dependency": "PERIMETR_POD_SIGNING_SECRET (separate escrow)",
                "excluded": sorted(EXCLUDED), "members": {}}
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for table in tables():
            name = f"data/{table.name}.jsonl"
            digest, size, count = hashlib.sha256(), 0, 0
            with archive.open(name, "w") as member:
                for row in db.execute(select(table).order_by(*table.primary_key.columns).execution_options(yield_per=100)).mappings():
                    raw = encoded(dict(row))
                    if len(raw) > MAX_ROW:
                        raise InvalidBackup("A data row exceeds the snapshot limit")
                    line = cipher.encrypt(raw) + b"\n"
                    size += len(line)
                    if size > settings.perimetr_backup_max_member_bytes or output.tell() + len(line) > settings.perimetr_max_backup_upload_bytes - 65536:
                        raise InvalidBackup("Snapshot exceeds the supported recovery budget")
                    member.write(line)
                    digest.update(line)
                    count += 1
            manifest["members"][name] = {"size": size, "sha256": digest.hexdigest(), "rows": count}
        manifest["authentication"] = signature(manifest, settings)
        archive.writestr("manifest.json", encoded(manifest))
    output.seek(0)
    return output


def _json(raw: bytes):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InvalidBackup("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=lambda _: (_ for _ in ()).throw(InvalidBackup("Invalid JSON number")))


def _rows(archive, table, settings):
    cipher = _fernet(settings)
    with archive.open(f"data/{table.name}.jsonl") as member:
        while line := member.readline(MAX_ROW * 2 + 1):
            if len(line) > MAX_ROW * 2 or not line.endswith(b"\n"):
                raise InvalidBackup("Invalid row size or framing")
            row = _json(cipher.decrypt(line.strip()))
            if not isinstance(row, dict) or set(row) != set(table.columns.keys()):
                raise InvalidBackup(f"Invalid columns in {table.name}")
            for column in table.columns:
                value = row[column.name]
                if value is None and not column.nullable:
                    raise InvalidBackup(f"Missing required value in {table.name}")
                if value is not None and isinstance(column.type, DateTime):
                    row[column.name] = datetime.fromisoformat(value)
                elif value is not None:
                    expected = column.type.python_type
                    if expected is int and type(value) is not int or expected is bool and type(value) is not bool:
                        raise InvalidBackup("Invalid field type")
                    if expected is str and not isinstance(value, str):
                        raise InvalidBackup("Invalid field type")
                    length = getattr(column.type, "length", None)
                    if length and isinstance(value, str) and len(value) > length:
                        raise InvalidBackup("Field exceeds schema limit")
            yield row


def preflight(data: bytes, settings: Settings) -> dict:
    if len(data) > settings.perimetr_max_backup_upload_bytes:
        raise InvalidBackup("Archive exceeds upload limit")
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            allowed = {"manifest.json", *(f"data/{name}.jsonl" for name in TABLE_NAMES)}
            names = [item.filename for item in members]
            if len(members) > settings.perimetr_backup_max_members or len(set(names)) != len(names) or set(names) != allowed:
                raise InvalidBackup("Missing, duplicate or unsupported archive member; legacy archives require offline migration")
            total = 0
            for item in members:
                mode = item.external_attr >> 16
                if stat.S_ISLNK(mode) or item.flag_bits & 1 or item.is_dir():
                    raise InvalidBackup("Links, directories and ZIP encryption are unsupported")
                total += item.file_size
                if item.file_size > settings.perimetr_backup_max_member_bytes or item.file_size > max(1, item.compress_size) * settings.perimetr_backup_max_ratio:
                    raise InvalidBackup("Archive member exceeds size or compression ratio limit")
            if total > settings.perimetr_backup_max_expanded_bytes or archive.getinfo("manifest.json").file_size > 65536:
                raise InvalidBackup("Archive exceeds expanded size limit")
            manifest = _json(archive.read("manifest.json"))
            if manifest.get("schema") != SCHEMA or manifest.get("mode") != "full-replace" or manifest.get("service") != "perimetr":
                raise InvalidBackup("Unsupported backup schema or mode")
            if manifest.get("database_revision") != "0006" or manifest.get("encryption") != "fernet-row-v1":
                raise InvalidBackup("Unsupported database revision or encryption format")
            claimed = manifest.pop("authentication", "")
            if not isinstance(claimed, str) or not hmac.compare_digest(claimed, signature(manifest, settings)):
                raise InvalidBackup("Backup authentication failed; verify the separate recovery secret")
            if set(manifest.get("members", {})) != allowed - {"manifest.json"}:
                raise InvalidBackup("Invalid manifest members")
            identities, foreign_keys = {}, []
            verifier_found = False
            for table in tables():
                name = f"data/{table.name}.jsonl"
                info = manifest["members"][name]
                digest = hashlib.sha256()
                with archive.open(name) as member:
                    while chunk := member.read(65536):
                        digest.update(chunk)
                if info["size"] != archive.getinfo(name).file_size or info["sha256"] != digest.hexdigest():
                    raise InvalidBackup("Snapshot integrity mismatch")
                ids, count = set(), 0
                for row in _rows(archive, table, settings):
                    if row["id"] in ids:
                        raise InvalidBackup("Duplicate record identity")
                    ids.add(row["id"])
                    count += 1
                    for column in table.columns:
                        for fk in column.foreign_keys:
                            if row[column.name] is not None:
                                foreign_keys.append((fk.column.table.name, row[column.name]))
                    if table.name == "system_settings" and row["key"] == "perimetr.preferences":
                        verifier_found = is_password_hash(row["value"].get("auth", {}).get("access_key_hash"))
                if count != info["rows"]:
                    raise InvalidBackup("Snapshot record count mismatch")
                identities[table.name] = ids
            if not verifier_found or any(value not in identities.get(table, ()) for table, value in foreign_keys):
                raise InvalidBackup("Missing operator identity or broken data relationship")
            return {**manifest, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                    "warnings": ["All current data will be replaced. All sessions will be revoked. The saved Access Key becomes authoritative."]}
    except InvalidBackup:
        raise
    except (BadZipFile, KeyError, TypeError, ValueError, AttributeError, InvalidToken, RuntimeError) as exc:
        raise InvalidBackup("Invalid or incompatible snapshot") from exc


def restore_snapshot(data: bytes, db: Session, settings: Settings) -> dict:
    summary = preflight(data, settings)
    # Caller holds the application write barrier. No file mutations occur here.
    # The savepoint also rolls back constraints failures on SQLite with FK checks disabled.
    try:
        with db.begin_nested():
            db.execute(SessionLease.__table__.delete())
            db.execute(Base.metadata.tables["backup_manifests"].delete())
            for table in reversed(tables()):
                db.execute(table.delete())
            with ZipFile(io.BytesIO(data)) as archive:
                for table in tables():
                    batch = []
                    for row in _rows(archive, table, settings):
                        if table.name == "launch_authorizations":
                            row.update(decision="revoked", revoked_at=datetime.now(timezone.utc))
                        batch.append(row)
                        if len(batch) == 100:
                            db.execute(table.insert(), batch)
                            batch.clear()
                    if batch:
                        db.execute(table.insert(), batch)
            db.flush()
        db.expire_all()
        return {"restored": True, "sha256": summary["sha256"], "sessions_revoked": True}
    except (SQLAlchemyError, InvalidBackup) as exc:
        raise InvalidBackup("Restore rejected; existing data retained") from exc
