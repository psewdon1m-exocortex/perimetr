"""Shared bounded redaction, before persistence and when reading older logs."""
import json
import re
import logging
from urllib.parse import urlsplit, urlunsplit

PRIVATE = re.compile(r"password|passwd|access.?key|secret|token|authorization|cookie|private.?key|credential|vless|data_base64|enrollment", re.I)
URL = re.compile(r"(?:https?|vless|ss|trojan)://[^\s<>\"']+", re.I)
INLINE = re.compile(r"(?i)\b(?:bearer\s+\S+|(?:password|access[_ -]?key|token|secret|authorization|cookie)\s*[:=]\s*[^\s,;]+)")


def text(value: str) -> str:
    def url(match):
        try:
            parsed = urlsplit(match.group())
            if parsed.scheme not in {"http", "https"}:
                return parsed.scheme + "://[REDACTED]"
            host = parsed.hostname or ""
            if ":" in host:
                host = "[" + host + "]"
            if parsed.port:
                host += ":" + str(parsed.port)
            return urlunsplit((parsed.scheme, host, parsed.path, "[REDACTED]" if parsed.query else "", ""))
        except ValueError:
            return "[REDACTED URL]"
    value = URL.sub(url, value)
    value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|$)", "[REDACTED KEY]", value)
    return INLINE.sub("[REDACTED]", value)[:4096]


def redact(value, depth=0):
    if depth > 8:
        return "[DEPTH LIMIT]"
    if isinstance(value, dict):
        return {str(key)[:128]: "[REDACTED]" if PRIVATE.search(str(key)) else redact(item, depth + 1)
                for key, item in list(value.items())[:128]}
    if isinstance(value, (list, tuple)):
        return [redact(item, depth + 1) for item in value[:128]]
    if isinstance(value, str):
        return text(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return text(str(value))


def bounded(value, limit=16384):
    result = redact(value)
    if len(json.dumps(result, ensure_ascii=True).encode()) <= limit:
        return result
    return {"truncated": True, "reason": "event_size_limit"}


class SafeLogFilter(logging.Filter):
    """Operational streams must not dump SQL parameters or exception locals."""
    def filter(self, record):
        record.msg = text(record.getMessage())
        if record.exc_info:
            record.msg += " [" + record.exc_info[0].__name__ + ": exception detail suppressed]"
        record.args = ()
        record.exc_info = record.exc_text = record.stack_info = None
        return True


def protect_operational_logs():
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "alembic"):
        for handler in logging.getLogger(name).handlers:
            if not any(isinstance(item, SafeLogFilter) for item in handler.filters):
                handler.addFilter(SafeLogFilter())
