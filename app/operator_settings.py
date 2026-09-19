"""Single-operator state. Read APIs expose only an explicit public projection."""
from __future__ import annotations

from copy import deepcopy
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import SystemSetting
from .security import hash_password, is_password_hash
from .settings import Settings

PREFERENCES_KEY = "perimetr.preferences"
DEFAULT_PRESENTATION = {
    "theme": {"accent": "#00A8FF"},
    "sidebar": {"auto_hide": False},
    "layout": {"navigation": [], "dashboard": [], "settings": []},
    "backup": {"include_audit": True, "include_sessions": False},
    "presentation_initialized": False,
    "revision": 1,
}


def ensure_preferences(db: Session, settings: Settings) -> SystemSetting:
    record = db.scalar(select(SystemSetting).where(SystemSetting.key == PREFERENCES_KEY))
    current = deepcopy(record.value or {}) if record else {}
    original = deepcopy(current)
    auth = dict(current.get("auth") or {})
    stored_hash = auth.get("access_key_hash") or auth.get("password_hash")
    # Legacy database verifiers are migrated unchanged: the previous password
    # becomes the exact Access Key. No legacy username is accepted by the API.
    if not is_password_hash(stored_hash):
        if "access_key_hash" in auth or "password_hash" in auth:
            raise RuntimeError("Stored operator verifier is invalid; recover the database instead of reseeding it")
        legacy = auth.get("password")
        seed = legacy if isinstance(legacy, str) and legacy != "" else settings.perimetr_access_key
        if is_password_hash(settings.perimetr_access_key_hash):
            stored_hash = settings.perimetr_access_key_hash
        elif isinstance(seed, str) and seed != "":
            stored_hash = hash_password(seed)
        else:
            raise RuntimeError("PERIMETR_ACCESS_KEY is required for an uninitialized installation")
    current["auth"] = {"access_key_hash": stored_hash}
    for key, value in DEFAULT_PRESENTATION.items():
        current.setdefault(key, deepcopy(value))
    current["theme"] = {"accent": current.get("theme", {}).get("accent", "#00A8FF")}
    current["backup"] = {"include_audit": True, "include_sessions": False}
    if record is None:
        record = SystemSetting(scope="perimetr", key=PREFERENCES_KEY, value=current)
        db.add(record)
    elif current != original:
        record.value = current
    db.flush()
    return record


def public_preferences(record: SystemSetting) -> dict:
    return {key: deepcopy(record.value[key]) for key in DEFAULT_PRESENTATION}


def validate_accent(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise HTTPException(422, "Accent must use #RRGGBB")
    channels = [int(value[n:n + 2], 16) / 255 for n in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
    luminance = sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    if (luminance + 0.05) / 0.05 < 4.5:
        raise HTTPException(422, "Accent needs at least 4.5:1 contrast against black")
    return value.upper()


def update_preferences(db: Session, settings: Settings, payload: dict) -> dict:
    ensure_preferences(db, settings)
    record = db.scalar(select(SystemSetting).where(SystemSetting.key == PREFERENCES_KEY).with_for_update())
    assert record is not None
    current = deepcopy(record.value)
    if type(payload.get("expected_revision")) is not int or payload["expected_revision"] != current["revision"]:
        raise HTTPException(409, "Settings changed in another session; reload and review your change")
    if set(payload) - {"expected_revision", "theme", "sidebar", "layout", "presentation_initialized"}:
        raise HTTPException(422, "Unsupported setting")
    if "theme" in payload:
        theme = payload["theme"]
        if not isinstance(theme, dict) or set(theme) != {"accent"}:
            raise HTTPException(422, "Only accent is editable")
        current["theme"] = {"accent": validate_accent(theme["accent"])}
    if "sidebar" in payload:
        sidebar = payload["sidebar"]
        if not isinstance(sidebar, dict) or set(sidebar) != {"auto_hide"} or type(sidebar["auto_hide"]) is not bool:
            raise HTTPException(422, "Invalid sidebar mode")
        current["sidebar"] = sidebar
    if "layout" in payload:
        layout = payload["layout"]
        if not isinstance(layout, dict) or set(layout) - {"navigation", "dashboard", "settings"}:
            raise HTTPException(422, "Invalid layout scope")
        for name, values in layout.items():
            if (not isinstance(values, list) or len(values) > 32 or
                any(not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", item) for item in values) or
                len(set(values)) != len(values)):
                raise HTTPException(422, "Invalid layout order")
        current["layout"] = {**current["layout"], **layout}
    if "presentation_initialized" in payload and payload["presentation_initialized"] is not True:
        raise HTTPException(422, "Presentation migration cannot be reset")
    current["presentation_initialized"] = True
    current["revision"] += 1
    record.value = current
    db.flush()
    return public_preferences(record)
