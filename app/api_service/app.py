from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import base64
import html
import io
import json
import logging
from pathlib import Path
import re
import secrets
import hashlib
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import Cookie, Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from .. import core_ui
from ..agent_client import (
    AgentTransportError,
    cancel_job as cancel_remote_agent_job,
    decide_job as decide_remote_agent_job,
    dispatch_job as dispatch_remote_agent_job,
    enroll as enroll_remote_agent,
)
from ..agent_request_security import (
    AgentRequestAuthError,
    AgentRequestReplayCache,
    has_signature_headers,
    request_target,
    verify_agent_request,
)
from ..controller_identity import ensure_controller_signing_material
from ..backup_service.service import build_backup_payload, build_backup_zip, import_backup_bundle
from ..database import SessionLocal, get_db
from ..database_migrations import upgrade_database
from ..enums import LaunchDecision, SessionStatus
from ..models import (
    AccessPolicy,
    Agent,
    AgentAssignment,
    AgentCapability,
    AgentCertificate,
    AgentCommand,
    AgentEndpoint,
    AgentHeartbeat,
    AgentJob,
    AgentStateEvent,
    ApprovalDecision,
    ApprovalRequest,
    AuditEvent,
    CertificateDenylist,
    Pod,
    PodDenylist,
    PodProvisioningRecord,
    JobEvent,
    JobResult,
    LaunchAuthorization,
    PerimetrObject,
    RevocationRecord,
    SessionLease,
    Subject,
    SystemSetting,
    new_entity_id,
)
from ..schemas import (
    AgentAssignmentCreate,
    AgentAssignmentRead,
    AgentControlHeartbeatRequest,
    AgentControlRead,
    AgentCommandCreate,
    AgentCommandRead,
    AgentCommandStatusUpdate,
    AgentEnrollRequest,
    AgentHeartbeatRequest,
    AgentJobCreate,
    AgentJobRead,
    AgentRead,
    AgentRegisterRequest,
    AgentReorderRequest,
    AgentUpdateRequest,
    ApprovalDecisionRequest,
    ApprovalRequestRead,
    AuditRead,
    BackupRead,
    PodHeartbeatRequest,
    PodEnrollRead,
    PodEnrollRequest,
    PodProvisioningCreate,
    PodProvisioningRead,
    PodPasswordUpdate,
    PodRenameRequest,
    PodSignedHeartbeatRequest,
    PodRead,
    CorrelationStateUpdate,
    DirectLoginRead,
    DirectLoginRequest,
    ErrorPayload,
    ErrorResponse,
    HealthResponse,
    JobEventRead,
    LaunchAuthorizationRead,
    MaterializeResponse,
    ObjectCreate,
    ObjectRead,
    ObjectUpdate,
    OverviewBlockRead,
    OverviewBlockUpdate,
    PolicyCreate,
    PolicyRead,
    PolicyUpdate,
    StatusResponse,
    SubjectCreate,
    SubjectRead,
    SubjectPodConfigUpdate,
    SubjectUpdate,
    SystemMetricsRead,
)
from ..pod_service import (
    build_pod_bundle,
    decrypt_secret,
    encrypt_secret,
    hash_token,
    hash_pod_password,
    heartbeat_signing_bytes,
    issue_enrollment_token,
    issue_identity_certificate,
    issue_pod_access_grant,
    pod_access_mode,
    pod_config_for_access,
    pod_payload,
    pod_executable_name,
    provisioning_expiry,
    provisioning_payload,
    public_key_fingerprint,
    subject_pod_config,
    validate_subject_pod_config,
    validate_vless_uri,
    verify_heartbeat_signature,
    verify_pod_access_grant,
)
from ..pod_artifacts import (
    PodArtifactError,
    ensure_latest_pod_artifact,
    resolve_pinned_pod_artifact,
)
from ..services import (
    PERIMETR_SYSTEM_ENTITY_ID,
    audit,
    build_status_response,
    build_system_metrics,
    build_topology_snapshot,
    create_direct_session,
    ensure_allowed_agent_command,
    ensure_perimetr_system_settings,
    expire_stale_sessions,
    get_correlation_state,
    get_agent,
    apply_agent_heartbeat,
    apply_agent_job_event,
    assign_agent_to_block,
    get_command,
    get_pod,
    create_agent_job,
    decide_approval,
    get_object,
    get_overview_blocks,
    get_agent_job,
    find_agent,
    get_session_lease,
    get_subject,
    hash_session_key,
    normalize_agent_block_type,
    normalize_timestamp,
    list_pending_agent_commands,
    normalize_access_target,
    now_utc,
    record_job_event,
    revoke_subject_access,
    reorder_block_agents,
    summarize_agent,
    unassign_agent_from_block,
    upsert_agent_capabilities,
    update_direct_password,
    update_overview_block,
    verify_direct_login,
    update_agent_command_status,
    update_correlation_state,
    visible_agent_status,
    correlation_percentage,
)
from ..settings import get_settings
from ..security import LoginRateLimiter, validate_runtime_settings
from ..updater import check_github_release
from .. import updater_client


ROBOTS_POLICY = (Path(__file__).resolve().parents[1] / "robots.txt").read_text(
    encoding="utf-8"
)
PROXY_IDENTITY_HEADERS = (
    "forwarded",
    "x-forwarded-for",
    "x-real-ip",
    "cf-connecting-ip",
)
BLOCKED_PROBE_PATH = re.compile(
    r"(?:^|/)\.|\.(?:env|ini|log|sql|bak|backup|old|swp|zip|tar|gz)$",
    re.IGNORECASE,
)

PERIMETR_SESSION_ID_COOKIE = "perimetr_session_id"
PERIMETR_SESSION_KEY_COOKIE = "perimetr_session_key"
MAX_ENTITY_IMAGE_BYTES = 4 * 1024 * 1024
logger = logging.getLogger(__name__)








def _remove_correlation_block(db: Session, block_key: str) -> None:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "perimetr.correlation_map"))
    if setting is None:
        return
    value = dict(setting.value or {})
    for field in ("descriptions_by_block", "properties_by_block"):
        blocks = dict(value.get(field) or {})
        blocks.pop(block_key, None)
        value[field] = blocks
    setting.value = value


async def _read_entity_image(image: UploadFile) -> str:
    content = await image.read(MAX_ENTITY_IMAGE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="entity_image_required")
    if len(content) > MAX_ENTITY_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="entity_image_too_large")
    if image.content_type != "image/png" or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="entity_image_must_be_png")
    return base64.b64encode(content).decode("ascii")


def _entity_image_response(entity: PerimetrObject | Subject) -> Response:
    return _stored_png_response(entity.image_data, entity.image_media_type or "image/png")


def _stored_png_response(image_data: str, media_type: str = "image/png") -> Response:
    if not image_data:
        raise HTTPException(status_code=404, detail="entity_image_not_found")
    try:
        content = base64.b64decode(image_data, validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="entity_image_corrupted") from exc
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "private, max-age=31536000, immutable"})


def _overview_block_payload(block_id: str, block: dict[str, str]) -> OverviewBlockRead:
    image_data = block.get("image_data") or ""
    version = hashlib.sha256(image_data.encode("ascii")).hexdigest()[:12] if image_data else ""
    return OverviewBlockRead(
        id=block_id,
        name=block["name"],
        image_url=f"/v1/overview-blocks/{block_id}/image?v={version}" if image_data else None,
        updated_at=block["updated_at"],
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    validate_runtime_settings(settings)
    await asyncio.to_thread(upgrade_database, settings.perimetr_database_url)
    with SessionLocal() as db:
        ensure_perimetr_system_settings(db, settings)
        db.commit()
    async def refresh_kernel_settings() -> None:
        while True:
            current = get_settings()
            await asyncio.sleep(current.kernel_refresh_sec)
            previous_revision = current.kernel_register_revision
            try:
                get_settings.cache_clear()
                refreshed = await asyncio.to_thread(get_settings)
                if refreshed.kernel_register_revision != previous_revision:
                    logger.info(
                        "Kernel Register refreshed: %s -> %s",
                        previous_revision or "none",
                        refreshed.kernel_register_revision or "none",
                    )
            except Exception:
                logger.exception("Kernel Register refresh failed; keeping last-known-good settings")

    async def refresh_pod_runtime() -> None:
        while True:
            current = get_settings()
            try:
                artifact = await asyncio.to_thread(
                    ensure_latest_pod_artifact,
                    current,
                    force=True,
                )
                if artifact.refresh_error:
                    logger.warning(
                        "Pod release refresh failed; using %s %s: %s",
                        artifact.source,
                        artifact.version,
                        artifact.refresh_error,
                    )
                else:
                    logger.info(
                        "Pod runtime ready: version=%s sha256=%s source=%s",
                        artifact.version,
                        artifact.sha256,
                        artifact.source,
                    )
            except Exception:
                logger.exception("No verified Pod runtime is currently available")
            await asyncio.sleep(max(60, current.perimetr_pod_refresh_sec))

    refresh_task = asyncio.create_task(refresh_kernel_settings())
    pod_refresh_task = asyncio.create_task(refresh_pod_runtime())
    try:
        yield
    finally:
        for task in (refresh_task, pod_refresh_task):
            task.cancel()
        for task in (refresh_task, pod_refresh_task):
            try:
                await task
            except asyncio.CancelledError:
                pass


def build_direct_login_html(*, error: str | None = None) -> str:
    friendly_errors = {
        "invalid_credentials": "Login or password is incorrect.",
        "login_failed": "Unable to sign in.",
    }
    error_message = friendly_errors.get(error or "", (error or "").replace("_", " ").capitalize())
    error_html = f'<div id="loginError" class="error">{html.escape(error_message)}</div>' if error else '<div id="loginError" class="error" hidden></div>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex,nofollow,noarchive,nosnippet" />
  <title>perimetr</title>
  <style>
    :root {{
      --dark: #000000;
      --light: #ffffff;
      --accent: #00a8ff;
      --line: color-mix(in srgb, var(--light) 50%, transparent);
      --line-mid: color-mix(in srgb, var(--light) 75%, transparent);
      --line-outer: var(--light);
      --danger: #ff4d4d;
      --ok: #2dff9a;
    }}
    * {{ box-sizing: border-box; }}
    html {{
      background: var(--dark);
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      background: var(--dark);
      color: var(--light);
      font-family: Consolas, "Cascadia Mono", "Segoe UI Mono", monospace;
    }}
    main {{
      width: min(560px, 100%);
      border: 1px solid var(--line-outer);
      background: var(--dark);
    }}
    .login-header {{
      min-height: 194px;
      display: grid;
      align-content: center;
      justify-items: start;
      padding: 24px 18px;
    }}
    h1 {{
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin: 0;
      color: var(--accent);
      font-size: clamp(48px, 14vw, 80px);
      font-weight: 900;
      line-height: .82;
    }}
    form {{ display: grid; gap: 14px; padding: 24px 18px; }}
    .field {{ display: block; margin: 0; }}
    .visually-hidden {{
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
      clip-path: inset(50%);
    }}
    input {{
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      background: var(--dark);
      color: var(--light);
      padding: 8px 10px;
      font: inherit;
      transition: background-color .16s ease, border-color .16s ease, color .16s ease;
    }}
    input::placeholder {{ color: color-mix(in srgb, var(--light) 55%, var(--dark)); opacity: 1; }}
    input:hover {{ border-color: var(--light); }}
    input:focus {{ border-color: var(--accent); color: var(--light); outline: none; }}
    button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 50%;
      min-height: 36px;
      border: 1px solid var(--accent);
      background: var(--dark);
      color: var(--accent);
      padding: 8px 12px;
      cursor: pointer;
      font: inherit;
      transform-origin: center;
      transition: background-color .16s ease, border-color .16s ease, color .16s ease, transform .16s ease;
    }}
    button:hover:not(:disabled) {{
      background: color-mix(in srgb, var(--dark) 90%, var(--light) 10%);
      border-color: var(--accent);
      color: var(--accent);
      transform: scale(1.02);
    }}
    button:active:not(:disabled) {{ transform: scale(.985); transition-duration: 60ms; }}
    button:focus-visible, input:focus-visible {{ outline: 1px solid var(--accent); outline-offset: 2px; }}
    button:disabled {{ opacity: .45; cursor: wait; transform: none; }}
    .actions {{ display: flex; align-items: center; margin-top: 2px; }}
    .error {{ color: var(--danger); min-height: 16px; font-size: 11px; line-height: 1.4; }}
    .error[hidden] {{ display: none; }}
    .access-status {{
      display: inline-flex;
      align-items: center;
      gap: 9px;
      margin-top: 30px;
      color: var(--ok);
      font-size: 10px;
      font-weight: 700;
    }}
    .access-status.unavailable {{ color: var(--danger); }}
    .status-spinner {{ width: 12px; height: 12px; border: 1px solid color-mix(in srgb, var(--ok) 35%, transparent); border-top-color: var(--ok); border-radius: 50%; animation: spin .8s linear infinite; }}
    .access-status.unavailable .status-spinner {{ display: none; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  </style>
</head>
<body>
  <main>
    <header class="login-header">
      <h1 aria-label="PERIMETR"><span aria-hidden="true">P</span><span aria-hidden="true">E</span><span aria-hidden="true">R</span><span aria-hidden="true">I</span><span aria-hidden="true">M</span><span aria-hidden="true">E</span><span aria-hidden="true">T</span><span aria-hidden="true">R</span></h1>
      <div id="accessIndicator" class="access-status" role="status" aria-live="polite"><span id="accessStatus">AVAILABLE</span></div>
    </header>
    <form id="loginForm">
      <input name="target" type="hidden" value="perimetr" />
      <label class="field"><span class="visually-hidden">Login</span><input name="username" autocomplete="username" placeholder="Login" aria-label="Login" autofocus /></label>
      <label class="field"><span class="visually-hidden">Password</span><input name="password" type="password" autocomplete="current-password" placeholder="Password" aria-label="Password" /></label>
      {error_html}
      <div class="actions">
        <button id="signInButton" type="submit" disabled>Sign in</button>
      </div>
    </form>
  </main>
  <script>
    function applyStoredTheme() {{
      let theme = null;
      try {{
        theme = JSON.parse(localStorage.getItem("perimetr.theme") || "null");
      }} catch (_) {{
        theme = null;
      }}
      if (!theme) {{
        const match = document.cookie.match(/(?:^|; )perimetr_theme=([^;]+)/);
        if (match) {{
          try {{
            theme = JSON.parse(decodeURIComponent(match[1]));
          }} catch (_) {{
            theme = null;
          }}
        }}
      }}
      if (!theme) return;
      if (theme.dark) document.documentElement.style.setProperty("--dark", theme.dark);
      if (theme.light) document.documentElement.style.setProperty("--light", theme.light);
      if (theme.accent) document.documentElement.style.setProperty("--accent", theme.accent);
    }}
    applyStoredTheme();
    const loginForm = document.getElementById("loginForm");
    const signInButton = document.getElementById("signInButton");
    const usernameInput = loginForm.elements.username;
    const passwordInput = loginForm.elements.password;
    let pending = false;
    function syncSubmitState() {{
      signInButton.disabled = pending || !String(usernameInput.value || "").trim() || !String(passwordInput.value || "");
    }}
    loginForm.addEventListener("input", syncSubmitState);
    loginForm.addEventListener("keydown", event => {{
      if (event.key === "Enter" && !event.isComposing && !signInButton.disabled) {{
        event.preventDefault();
        loginForm.requestSubmit(signInButton);
      }}
    }});
    loginForm.addEventListener("submit", async (event) => {{
      event.preventDefault();
      const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
      const notice = document.getElementById("loginError");
      const showError = message => {{
        const labels = {{ invalid_credentials: "Login or password is incorrect.", login_failed: "Unable to sign in." }};
        notice.textContent = labels[message] || String(message || "Unable to sign in.").replaceAll("_", " ");
        notice.hidden = false;
      }};
      if (!String(payload.username || "").trim() || !String(payload.password || "")) {{
        showError("Enter login and password.");
        return;
      }}
      pending = true;
      signInButton.textContent = "Signing in...";
      syncSubmitState();
      try {{
        const response = await fetch("/v1/auth/direct", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        const text = await response.text();
        let body = null;
        try {{ body = text ? JSON.parse(text) : null; }} catch (_) {{ body = null; }}
        if (!response.ok) {{
          showError(body?.error?.message || body?.detail || "login_failed");
          return;
        }}
        notice.hidden = true;
        window.location = "/";
      }} catch (_) {{
        showError("Perimetr is unavailable.");
      }} finally {{
        pending = false;
        signInButton.textContent = "Sign in";
        syncSubmitState();
      }}
    }});
    syncSubmitState();
  </script>
</body>
</html>"""


def _backup_dir() -> Path:
    path = Path(".tmp") / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _backup_meta_path(backup_id: str) -> Path:
    return _backup_dir() / f"{backup_id}.json"


def _backup_zip_path(backup_id: str) -> Path:
    return _backup_dir() / f"{backup_id}.zip"


async def _validate_backup_upload(archive: UploadFile) -> None:
    maximum = max(get_settings().perimetr_max_backup_upload_bytes, 1024 * 1024)
    content = await archive.read(maximum + 1)
    if len(content) > maximum:
        raise HTTPException(status_code=413, detail="backup_archive_too_large")
    await archive.seek(0)


def create_app() -> FastAPI:
    app = FastAPI(
        title="perimetr",
        version=get_settings().perimetr_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.login_rate_limiter = LoginRateLimiter()
    app.state.agent_request_replay_cache = AgentRequestReplayCache()

    @app.middleware("http")
    async def anti_indexing_headers(request: Request, call_next):
        if BLOCKED_PROBE_PATH.search(request.url.path):
            response = JSONResponse(status_code=404, content={"error": "Not found"})
        else:
            response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorPayload(code=str(exc.status_code), message=str(exc.detail), details={})
            ).model_dump(),
            headers=exc.headers,
        )

    @app.get("/robots.txt", include_in_schema=False)
    def robots_txt() -> Response:
        return Response(content=ROBOTS_POLICY, media_type="text/plain")

    @app.get("/", response_class=HTMLResponse)
    def index(
        error: str | None = None,
        perimetr_session_id: str | None = Cookie(None, alias=PERIMETR_SESSION_ID_COOKIE),
        perimetr_session_key: str | None = Cookie(None, alias=PERIMETR_SESSION_KEY_COOKIE),
        db: Session = Depends(get_db),
    ) -> str:
        expire_stale_sessions(db)
        db.commit()
        if perimetr_session_id and perimetr_session_key:
            try:
                lease = get_session_lease(db, perimetr_session_id)
                if lease.status == SessionStatus.active.value and secrets.compare_digest(
                    lease.session_key_hash,
                    hash_session_key(perimetr_session_key),
                ):
                    return core_ui.build_core_index_html()
            except HTTPException:
                pass
        return build_direct_login_html(error=error)

    @app.post("/v1/auth/direct", response_model=DirectLoginRead)
    async def direct_login(
        payload: DirectLoginRequest,
        response: Response,
        request: Request,
        db: Session = Depends(get_db),
    ) -> DirectLoginRead:
        settings = get_settings()
        target = normalize_access_target(payload.target)
        source_ip = (
            request.headers.get("x-real-ip")
            or (request.client.host if request.client else "")
            or "unknown"
        )
        limiter: LoginRateLimiter = app.state.login_rate_limiter
        decision = limiter.check(source_ip)
        if not decision.allowed:
            audit(
                db,
                actor_type="anonymous",
                actor_id=source_ip,
                action="direct.session.denied",
                target_type="system",
                target_id=PERIMETR_SYSTEM_ENTITY_ID,
                payload={"target": target},
                result={"reason": "rate_limit"},
            )
            db.commit()
            raise HTTPException(
                status_code=429,
                detail="too_many_login_attempts",
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )
        if decision.delay_seconds:
            await asyncio.sleep(decision.delay_seconds)
        try:
            lease = create_direct_session(
                db,
                settings,
                target=target,
                username=payload.username,
                password=payload.password,
            )
        except HTTPException:
            limiter.fail(source_ip)
            audit(
                db,
                actor_type="anonymous",
                actor_id=source_ip,
                action="direct.session.denied",
                target_type="system",
                target_id=PERIMETR_SYSTEM_ENTITY_ID,
                payload={"target": target},
                result={"reason": "invalid_credentials"},
            )
            db.commit()
            raise HTTPException(status_code=401, detail="invalid_credentials") from None
        limiter.success(source_ip)
        session_key = getattr(lease, "_plain_session_key")
        audit(
            db,
            actor_type="direct_browser",
            actor_id=payload.username,
            action="direct.session.created",
            target_type="system",
            target_id=PERIMETR_SYSTEM_ENTITY_ID,
            payload={"target": target},
            result={"lease_id": lease.id, "transport": "direct"},
        )
        db.commit()
        response.set_cookie(
            PERIMETR_SESSION_ID_COOKIE,
            lease.id,
            httponly=True,
            secure=settings.perimetr_cookie_secure,
            samesite="lax",
            max_age=settings.perimetr_session_ttl_sec,
        )
        response.set_cookie(
            PERIMETR_SESSION_KEY_COOKIE,
            session_key,
            httponly=True,
            secure=settings.perimetr_cookie_secure,
            samesite="lax",
            max_age=settings.perimetr_session_ttl_sec,
        )
        return DirectLoginRead(
            approved=True,
            target=target,
            transport="direct",
            renderer_url=settings.perimetr_public_url,
        )

    @app.post("/v1/auth/logout")
    def direct_logout() -> RedirectResponse:
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(PERIMETR_SESSION_ID_COOKIE)
        response.delete_cookie(PERIMETR_SESSION_KEY_COOKIE)
        return response

    def require_core_access(
        perimetr_session_id: str | None = Cookie(None, alias=PERIMETR_SESSION_ID_COOKIE),
        perimetr_session_key: str | None = Cookie(None, alias=PERIMETR_SESSION_KEY_COOKIE),
        db: Session = Depends(get_db),
    ) -> SessionLease:
        expire_stale_sessions(db)
        db.commit()
        session_id = perimetr_session_id
        session_key = perimetr_session_key
        if not session_id or not session_key:
            raise HTTPException(status_code=403, detail="perimetr_access_required")
        lease = get_session_lease(db, session_id)
        if lease.status != SessionStatus.active.value:
            raise HTTPException(status_code=403, detail="perimetr_session_inactive")
        if not secrets.compare_digest(lease.session_key_hash, hash_session_key(session_key)):
            raise HTTPException(status_code=403, detail="perimetr_session_invalid")
        return lease

    async def require_agent_callback_authentication(
        request: Request,
        agent: Agent,
    ) -> None:
        metadata = dict(agent.metadata_json or {})
        if not metadata.get("remote_enrolled"):
            return
        headers = request.headers
        if not has_signature_headers(headers):
            if metadata.get("request_signing_required"):
                raise HTTPException(status_code=403, detail="AGENT_SIGNATURE_REQUIRED")
            if not secrets.compare_digest(
                headers.get("x-agent-fingerprint") or "",
                agent.identity_fingerprint,
            ):
                raise HTTPException(status_code=403, detail="AGENT_IDENTITY_MISMATCH")
            return
        try:
            verify_agent_request(
                certificate_pem=agent.identity_certificate,
                expected_fingerprint=agent.identity_fingerprint,
                method=request.method,
                target=request_target(request.url.path, request.url.query),
                body=await request.body(),
                headers=headers,
                replay_cache=app.state.agent_request_replay_cache,
            )
        except AgentRequestAuthError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        agent.metadata_json = {**metadata, "request_signing_required": True}

    @app.get("/v1/health", response_model=HealthResponse, include_in_schema=False)
    def health(request: Request) -> HealthResponse:
        if any(request.headers.get(name) for name in PROXY_IDENTITY_HEADERS):
            raise HTTPException(status_code=404, detail="not_found")
        return HealthResponse(status="ok", service="perimetr")

    @app.get("/v1/public/status", response_model=StatusResponse, include_in_schema=False)
    def public_status(request: Request, db: Session = Depends(get_db)) -> StatusResponse:
        if any(request.headers.get(name) for name in PROXY_IDENTITY_HEADERS):
            raise HTTPException(status_code=404, detail="not_found")
        return StatusResponse(**build_status_response(db))

    @app.get("/v1/status", response_model=StatusResponse)
    def status(_: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> StatusResponse:
        return StatusResponse(**build_status_response(db))

    @app.get("/v1/system/metrics", response_model=SystemMetricsRead)
    def system_metrics(_: SessionLease = Depends(require_core_access)) -> SystemMetricsRead:
        return SystemMetricsRead(**build_system_metrics())

    @app.get("/v1/overview-blocks", response_model=list[OverviewBlockRead])
    def list_overview_blocks(
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> list[OverviewBlockRead]:
        blocks = get_overview_blocks(db)
        result = [_overview_block_payload(block_id, block) for block_id, block in blocks.items()]
        db.commit()
        return result

    @app.patch("/v1/overview-blocks/{block_id}", response_model=OverviewBlockRead)
    def rename_overview_block(
        block_id: str,
        payload: OverviewBlockUpdate,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> OverviewBlockRead:
        block = update_overview_block(db, block_id, name=payload.name)
        audit(
            db,
            actor_type="browser_ui",
            actor_id="operator",
            action="overview_block.renamed",
            target_type="overview_block",
            target_id=block_id,
            payload={"name": block["name"]},
        )
        db.commit()
        return _overview_block_payload(block_id, block)

    @app.get("/v1/overview-blocks/{block_id}/image")
    def read_overview_block_image(
        block_id: str,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> Response:
        block = get_overview_blocks(db).get(block_id)
        if block is None:
            raise HTTPException(status_code=404, detail="overview_block_not_found")
        return _stored_png_response(block["image_data"])

    @app.put("/v1/overview-blocks/{block_id}/image", response_model=OverviewBlockRead)
    async def upload_overview_block_image(
        block_id: str,
        image: UploadFile = File(...),
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> OverviewBlockRead:
        image_data = await _read_entity_image(image)
        block = update_overview_block(db, block_id, image_data=image_data)
        audit(
            db,
            actor_type="browser_ui",
            actor_id="operator",
            action="overview_block.image.updated",
            target_type="overview_block",
            target_id=block_id,
            result={"bytes": len(base64.b64decode(image_data))},
        )
        db.commit()
        return _overview_block_payload(block_id, block)

    @app.delete("/v1/overview-blocks/{block_id}/image", response_model=OverviewBlockRead)
    def delete_overview_block_image(
        block_id: str,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> OverviewBlockRead:
        block = update_overview_block(db, block_id, image_data="")
        audit(
            db,
            actor_type="browser_ui",
            actor_id="operator",
            action="overview_block.image.removed",
            target_type="overview_block",
            target_id=block_id,
        )
        db.commit()
        return _overview_block_payload(block_id, block)

    @app.get("/v1/settings/runtime")
    def runtime_settings(_: SessionLease = Depends(require_core_access)) -> dict:
        settings = get_settings()
        return {
            "version": settings.perimetr_version,
            "kernel_register_revision": settings.kernel_register_revision,
            "audit_limits": {
                "max_entries": settings.perimetr_audit_max_entries,
                "retention_days": settings.perimetr_audit_retention_days,
                "max_file_bytes": settings.perimetr_log_max_file_bytes,
                "max_total_bytes": settings.perimetr_logs_max_total_bytes,
            },
        }

    @app.post("/v1/updater/check")
    def check_for_updates(
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        try:
            # An explicit operator check also refreshes the last-known-good
            # Register snapshot before resolving the repository URL.
            get_settings.cache_clear()
            settings = get_settings()
            result = check_github_release(
                repository_url=settings.perimetr_repository_url,
                service="perimetr",
                current_version=settings.perimetr_version,
                timeout_seconds=settings.perimetr_update_check_timeout_sec,
            )
            audit(
                db,
                actor_type="perimetr",
                actor_id="core",
                action="updater.check",
                target_type="system",
                target_id=PERIMETR_SYSTEM_ENTITY_ID,
                result={
                    "installed_version": result["installed_version"],
                    "available_version": result["available_version"],
                    "update_available": result["update_available"],
                    "repository_url": result["repository_url"],
                },
            )
            db.commit()
            return result
        except Exception as exc:
            audit(
                db,
                actor_type="perimetr",
                actor_id="core",
                action="updater.check",
                target_type="system",
                target_id=PERIMETR_SYSTEM_ENTITY_ID,
                result={"error": str(exc)},
            )
            db.commit()
            raise HTTPException(status_code=502, detail=f"UPDATE_CHECK_FAILED: {exc}") from exc

    @app.get("/v1/updater/status")
    def updater_status(_: SessionLease = Depends(require_core_access)) -> dict:
        return updater_client.status(get_settings().updater_socket_path)

    @app.post("/v1/updater/install")
    def install_update(
        payload: dict,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        version = str(payload.get("version") or "").strip()
        backup_id = str(payload.get("backup_id") or "").strip()
        if not version:
            raise HTTPException(status_code=400, detail="Select a published Perimetr release")
        if not re.fullmatch(r"\d{14}-[0-9a-f]{8}", backup_id):
            raise HTTPException(status_code=400, detail="Download a fresh Perimetr backup before installing")
        meta_path = _backup_meta_path(backup_id)
        zip_path = _backup_zip_path(backup_id)
        if not meta_path.exists() or not zip_path.exists():
            raise HTTPException(status_code=409, detail="The staged Perimetr backup is unavailable")
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        if metadata.get("entity_type") != "system":
            raise HTTPException(status_code=400, detail="A complete system backup is required")
        try:
            backup_created_at = datetime.fromisoformat(str(metadata["created_at"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Backup metadata is invalid") from exc
        if datetime.now(timezone.utc) - backup_created_at > timedelta(minutes=15):
            raise HTTPException(status_code=409, detail="The staged Perimetr backup is older than 15 minutes")
        backup_bytes = zip_path.read_bytes()
        filename = str(metadata.get("filename") or f"perimetr-pre-update-{backup_id}.zip")
        checksum = hashlib.sha256(backup_bytes).hexdigest()
        try:
            job = updater_client.request(
                get_settings().updater_socket_path,
                "POST",
                "/v1/updates",
                {
                    "request_id": f"perimetr-{secrets.token_hex(16)}",
                    "head_id": get_settings().updater_head_id,
                    "service": "perimetr",
                    "version": version,
                    "backup": {
                        "filename": filename,
                        "sha256": checksum,
                        "data_base64": base64.b64encode(backup_bytes).decode("ascii"),
                    },
                },
                timeout=30,
                control_token=get_settings().updater_control_token,
            )
        except updater_client.UpdaterUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        audit(
            db,
            actor_type="perimetr",
            actor_id="core",
            action="updater.install.requested",
            target_type="system",
            target_id=PERIMETR_SYSTEM_ENTITY_ID,
            result={"job_id": job.get("id"), "version": version, "backup_id": backup_id},
        )
        db.commit()
        return JSONResponse(job, status_code=202)

    @app.get("/v1/updater/jobs/{job_id}")
    def updater_job(job_id: str, _: SessionLease = Depends(require_core_access)) -> dict:
        try:
            return updater_client.request(
                get_settings().updater_socket_path,
                "GET",
                f"/v1/jobs/{job_id}",
            )
        except updater_client.UpdaterUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/v1/updater/jobs/{job_id}/rollback")
    def rollback_updater_job(job_id: str, _: SessionLease = Depends(require_core_access)) -> dict:
        try:
            return JSONResponse(
                updater_client.request(
                    get_settings().updater_socket_path,
                    "POST",
                    f"/v1/jobs/{job_id}/rollback",
                    control_token=get_settings().updater_control_token,
                ),
                status_code=202,
            )
        except updater_client.UpdaterUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/v1/topology")
    def topology(_: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        return build_topology_snapshot(db)

    @app.get("/v1/logs/{entity_type}/{entity_id}")
    def read_entity_logs(
        entity_type: str,
        entity_id: str,
        _: SessionLease = Depends(require_core_access),
    ) -> dict:
        log_path = Path(get_settings().perimetr_logs_dir) / f"{entity_type}_{entity_id}.jsonl"
        if not log_path.exists():
            return {"entries": [], "path": str(log_path)}
        entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return {"entries": entries[-get_settings().perimetr_audit_max_entries :], "path": str(log_path)}

    @app.get("/v1/logs/audit")
    def read_audit_log(_: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        events = db.scalars(
            select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(get_settings().perimetr_audit_max_entries)
        ).all()
        return {
            "entries": [
                {
                    "created_at": event.created_at.isoformat(),
                    "actor": f"{event.actor_type}:{event.actor_id}",
                    "action": event.action,
                    "target": f"{event.target_type}:{event.target_id}",
                    "payload": event.payload,
                    "result": event.result,
                }
                for event in events
            ]
        }

    @app.get("/v1/logs/download")
    def download_logs(
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> StreamingResponse:
        logs_dir = Path(get_settings().perimetr_logs_dir)
        settings = get_settings()
        events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.asc())).all()
        serialized_events = [
            {
                "id": event.id,
                "created_at": event.created_at.isoformat(),
                "actor": {"type": event.actor_type, "id": event.actor_id},
                "action": event.action,
                "target": {"type": event.target_type, "id": event.target_id},
                "payload": event.payload or {},
                "result": event.result or {},
            }
            for event in events
        ]

        def detailed_error(event: AuditEvent) -> dict | None:
            payload = event.payload or {}
            result = event.result or {}
            searchable = " ".join(
                str(value)
                for value in (
                    event.action,
                    result.get("status"),
                    result.get("error"),
                    result.get("detail"),
                    result.get("exception"),
                    result.get("message"),
                )
                if value is not None
            ).lower()
            if not re.search(r"\b(error|failed|failure|denied|rejected|exception)\b", searchable):
                return None
            message = next(
                (
                    str(value)
                    for value in (
                        result.get("message"),
                        result.get("error"),
                        result.get("detail"),
                        result.get("exception"),
                        payload.get("message"),
                        payload.get("error"),
                        payload.get("detail"),
                    )
                    if value
                ),
                f"{event.action} failed for {event.target_type}:{event.target_id}",
            )
            return {
                "event_id": event.id,
                "occurred_at": event.created_at.isoformat(),
                "actor": {"type": event.actor_type, "id": event.actor_id},
                "action": event.action,
                "target": {"type": event.target_type, "id": event.target_id},
                "summary": f"{event.action}: {message}",
                "message": message,
                "error_type": result.get("error_type") or result.get("type"),
                "code": result.get("code") or payload.get("code"),
                "cause": result.get("cause"),
                "stack_trace": result.get("stack_trace") or result.get("traceback"),
                "request_id": result.get("request_id") or payload.get("request_id"),
                "method": result.get("method") or payload.get("method"),
                "context": {"payload": payload, "result": result},
            }

        errors = [item for event in events if (item := detailed_error(event)) is not None]
        generated_at = datetime.now(timezone.utc)
        manifest = {
            "schema": "perimetr.logs.export.v1",
            "service": "perimetr",
            "version": settings.perimetr_version,
            "generated_at": generated_at.isoformat(),
            "event_count": len(serialized_events),
            "error_count": len(errors),
            "retention": {
                "max_entries": settings.perimetr_audit_max_entries,
                "retention_days": settings.perimetr_audit_retention_days,
                "max_file_bytes": settings.perimetr_log_max_file_bytes,
                "max_total_bytes": settings.perimetr_logs_max_total_bytes,
            },
            "files": ["manifest.json", "audit-events.json", "errors.json", "README.txt", "raw/*.jsonl"],
        }
        buffer = io.BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            archive.writestr("audit-events.json", json.dumps(serialized_events, indent=2, ensure_ascii=False))
            archive.writestr("errors.json", json.dumps(errors, indent=2, ensure_ascii=False))
            archive.writestr(
                "README.txt",
                "PERIMETR LOG EXPORT\n\n"
                "manifest.json describes this archive and the active retention limits.\n"
                "audit-events.json contains complete structured audit events.\n"
                "errors.json contains expanded diagnostics for events classified as errors, "
                "including the original payload and result context. Missing values are null.\n"
                "raw/ contains the retained JSONL files exactly as stored on disk.\n",
            )
            if logs_dir.exists():
                for path in sorted(logs_dir.glob("*.jsonl")):
                    archive.write(path, arcname=f"raw/{path.name}")
        buffer.seek(0)
        filename = f"perimetr-logs-{generated_at.strftime('%Y%m%d%H%M%S')}.zip"
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/v1/audit/ui")
    def record_ui_action(
        payload: dict,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        action = str(payload.get("action") or "ui.action")
        target_type = str(payload.get("target_type") or "ui")
        target_id = str(payload.get("target_id") or PERIMETR_SYSTEM_ENTITY_ID)
        audit(
            db,
            actor_type="browser_ui",
            actor_id="operator",
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=dict(payload.get("payload") or {}),
            result=dict(payload.get("result") or {}),
        )
        db.commit()
        return {"recorded": True}

    @app.post("/v1/settings/password")
    def change_password(
        payload: dict,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        update_direct_password(
            db,
            get_settings(),
            current_password=str(payload.get("current_password") or ""),
            new_password=str(payload.get("new_password") or ""),
            confirm_password=str(payload.get("confirm_password") or ""),
        )
        audit(
            db,
            actor_type="perimetr",
            actor_id="core",
            action="auth.password.updated",
            target_type="system",
            target_id=PERIMETR_SYSTEM_ENTITY_ID,
            result={"direct_login": True},
        )
        db.commit()
        return {"changed": True}

    @app.get("/v1/correlation")
    def read_correlation_state(
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        value = get_correlation_state(db)
        result = {**value, "correlation_percentage": correlation_percentage(db, value)}
        db.commit()
        return result

    @app.put("/v1/correlation")
    def write_correlation_state(
        payload: CorrelationStateUpdate,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        result = update_correlation_state(db, payload.model_dump(mode="json"))
        audit(
            db,
            actor_type="browser_ui",
            actor_id="operator",
            action="correlation.state.updated",
            target_type="correlation_map",
            target_id=PERIMETR_SYSTEM_ENTITY_ID,
            result={"correlation_percentage": result["correlation_percentage"]},
        )
        db.commit()
        return result

    @app.post("/v1/backups", response_model=BackupRead, status_code=201)
    def create_backup(
        payload: dict | None = None,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> BackupRead:
        payload = payload or {}
        entity_type = str(payload.get("entity_type") or "system")
        entity_id = str(payload.get("entity_id") or PERIMETR_SYSTEM_ENTITY_ID)
        backup_payload = build_backup_payload(entity_type=entity_type, entity_id=entity_id, db=db)
        archive = build_backup_zip(backup_payload)
        created_at = datetime.now(timezone.utc)
        backup_id = f"{created_at.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"
        filename = f"perimetr-backup-{entity_type}-{backup_id}.zip"
        _backup_zip_path(backup_id).write_bytes(archive.getvalue())
        metadata = {
            "id": backup_id,
            "filename": filename,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "created_at": created_at.isoformat(),
        }
        _backup_meta_path(backup_id).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        audit(
            db,
            actor_type="perimetr",
            actor_id="core",
            action="backup.created",
            target_type=entity_type,
            target_id=entity_id,
            result={"backup_id": backup_id, "filename": filename},
        )
        db.commit()
        return BackupRead(**metadata)

    @app.get("/v1/backups", response_model=list[BackupRead])
    def list_backups(_: SessionLease = Depends(require_core_access)) -> list[BackupRead]:
        items = []
        for path in sorted(_backup_dir().glob("*.json"), reverse=True):
            items.append(BackupRead(**json.loads(path.read_text(encoding="utf-8"))))
        return items

    @app.get("/v1/backups/{backup_id}")
    def download_backup(backup_id: str, _: SessionLease = Depends(require_core_access)) -> StreamingResponse:
        meta_path = _backup_meta_path(backup_id)
        zip_path = _backup_zip_path(backup_id)
        if not meta_path.exists() or not zip_path.exists():
            raise HTTPException(status_code=404, detail="backup not found")
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        return StreamingResponse(
            zip_path.open("rb"),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{metadata["filename"]}"'},
        )

    @app.post("/v1/backups/import")
    async def import_backup(
        archive: UploadFile = File(...),
        db: Session = Depends(get_db),
        _: SessionLease = Depends(require_core_access),
    ) -> dict:
        await _validate_backup_upload(archive)
        try:
            return await import_backup_bundle(archive=archive, db=db)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"INVALID_BACKUP: {exc}") from exc

    @app.post("/v1/internal/updater/restore")
    async def restore_backup_from_updater(
        archive: UploadFile = File(...),
        x_updater_token: str | None = Header(default=None),
        db: Session = Depends(get_db),
    ) -> dict:
        expected = get_settings().updater_control_token
        if (
            not expected
            or not x_updater_token
            or not secrets.compare_digest(x_updater_token, expected)
        ):
            raise HTTPException(status_code=403, detail="Updater authentication required")
        await _validate_backup_upload(archive)
        try:
            return await import_backup_bundle(archive=archive, db=db)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"INVALID_BACKUP: {exc}") from exc

    @app.get("/v1/objects", response_model=list[ObjectRead])
    def list_objects(_: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> list[PerimetrObject]:
        return db.scalars(select(PerimetrObject).order_by(PerimetrObject.created_at.desc())).all()

    @app.post("/v1/objects", response_model=ObjectRead, status_code=201)
    def create_object(payload: ObjectCreate, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> PerimetrObject:
        entity_id = new_entity_id()
        while db.scalar(select(PerimetrObject).where(PerimetrObject.entity_id == entity_id)) or db.scalar(select(Subject).where(Subject.entity_id == entity_id)):
            entity_id = new_entity_id()
        obj = PerimetrObject(**payload.model_dump(), entity_id=entity_id)
        db.add(obj)
        db.flush()
        audit(db, actor_type="perimetr", actor_id="core", action="object.created", target_type="object", target_id=obj.entity_id, payload=payload.model_dump(mode="json"), result={"name": obj.name})
        db.commit()
        db.refresh(obj)
        return obj

    @app.get("/v1/objects/{object_id}", response_model=ObjectRead)
    def read_object(object_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> PerimetrObject:
        return get_object(db, object_id)

    @app.patch("/v1/objects/{object_id}", response_model=ObjectRead)
    def update_object(object_id: str, payload: ObjectUpdate, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> PerimetrObject:
        obj = get_object(db, object_id)
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(obj, key, value.value if hasattr(value, "value") else value)
        audit(db, actor_type="perimetr", actor_id="core", action="object.updated", target_type="object", target_id=obj.entity_id, payload=payload.model_dump(exclude_none=True, mode="json"), result={"name": obj.name})
        db.commit()
        db.refresh(obj)
        return obj

    @app.put("/v1/objects/{object_id}/image", response_model=ObjectRead)
    async def update_object_image(
        object_id: str,
        image: UploadFile = File(...),
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> PerimetrObject:
        obj = get_object(db, object_id)
        obj.image_data = await _read_entity_image(image)
        obj.image_media_type = "image/png"
        audit(db, actor_type="perimetr", actor_id="core", action="object.image.updated", target_type="object", target_id=obj.entity_id)
        db.commit()
        db.refresh(obj)
        return obj

    @app.get("/v1/objects/{object_id}/image")
    def read_object_image(object_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> Response:
        return _entity_image_response(get_object(db, object_id))

    @app.delete("/v1/objects/{object_id}/image", response_model=ObjectRead)
    def delete_object_image(object_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> PerimetrObject:
        obj = get_object(db, object_id)
        obj.image_data = ""
        obj.image_media_type = ""
        audit(db, actor_type="perimetr", actor_id="core", action="object.image.deleted", target_type="object", target_id=obj.entity_id)
        db.commit()
        db.refresh(obj)
        return obj

    @app.delete("/v1/objects/{object_id}")
    def delete_object(object_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        obj = get_object(db, object_id)
        public_id = obj.entity_id
        for linked_subject in list(obj.subjects):
            linked_subject.object_id = None
        db.execute(delete(AgentAssignment).where(AgentAssignment.block_type == "object", AgentAssignment.block_id == public_id))
        _remove_correlation_block(db, f"object_{public_id}")
        db.delete(obj)
        audit(db, actor_type="perimetr", actor_id="core", action="object.deleted", target_type="object", target_id=public_id)
        db.commit()
        return {"deleted": True, "id": public_id}

    @app.get("/v1/subjects", response_model=list[SubjectRead])
    def list_subjects(_: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> list[Subject]:
        return db.scalars(select(Subject).order_by(Subject.created_at.desc())).all()

    @app.post("/v1/subjects", response_model=SubjectRead, status_code=201)
    def create_subject(payload: SubjectCreate, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> Subject:
        try:
            obj = get_object(db, payload.object_id)
        except HTTPException as exc:
            existing = db.get(Subject, payload.object_id) or db.scalar(
                select(Subject).where(Subject.entity_id == payload.object_id)
            )
            if existing is not None:
                return existing
            raise exc
        legacy_subjects = db.scalars(select(Subject).where(Subject.object_id == obj.id)).all()
        for legacy in legacy_subjects:
            legacy.object_id = None
            legacy.name = legacy.name or obj.name
            legacy.kind = legacy.kind or obj.kind
            legacy.description = legacy.description or obj.description
            legacy.tags = legacy.tags or obj.tags
        db.flush()
        subject = Subject(
            id=obj.id,
            entity_id=obj.entity_id,
            object_id=None,
            name=obj.name,
            kind=obj.kind,
            description=obj.description,
            tags=obj.tags,
            image_data=obj.image_data,
            image_media_type=obj.image_media_type,
            runtime_type=payload.runtime_type.value,
            access_policy_id=payload.access_policy_id,
        )
        db.add(subject)
        db.flush()
        spec = payload.pod_spec
        if spec is not None:
            pod = Pod(
                subject_id=subject.id,
                host_id=spec.host_id,
                path=spec.path,
                launcher_path=spec.launcher_path,
                is_portable=spec.is_portable,
                runtime_state={"materialized": False},
            )
            db.add(pod)
            db.flush()
            subject.pod_id = pod.id
        setting = db.scalar(select(SystemSetting).where(SystemSetting.key == "perimetr.correlation_map"))
        if setting:
            value = dict(setting.value or {})
            for key in ("descriptions_by_block", "properties_by_block"):
                blocks = dict(value.get(key) or {})
                source_key = f"object_{subject.entity_id}"
                target_key = f"subject_{subject.entity_id}"
                if source_key in blocks:
                    blocks[target_key] = blocks.pop(source_key)
                value[key] = blocks
            setting.value = value
        db.delete(obj)
        audit(db, actor_type="perimetr", actor_id="core", action="object.transformed_to_subject", target_type="subject", target_id=subject.entity_id, payload=payload.model_dump(mode="json"), result={"name": subject.name})
        db.commit()
        db.refresh(subject)
        return subject

    @app.get("/v1/subjects/{subject_id}", response_model=SubjectRead)
    def read_subject(subject_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> Subject:
        return get_subject(db, subject_id)

    @app.patch("/v1/subjects/{subject_id}", response_model=SubjectRead)
    def update_subject(subject_id: str, payload: SubjectUpdate, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> Subject:
        subject = get_subject(db, subject_id)
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(subject, key, value.value if hasattr(value, "value") else value)
        audit(db, actor_type="perimetr", actor_id="core", action="subject.updated", target_type="subject", target_id=subject.entity_id, payload=payload.model_dump(exclude_none=True, mode="json"), result={"name": subject.name})
        db.commit()
        db.refresh(subject)
        return subject

    @app.put("/v1/subjects/{subject_id}/image", response_model=SubjectRead)
    async def update_subject_image(
        subject_id: str,
        image: UploadFile = File(...),
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> Subject:
        subject = get_subject(db, subject_id)
        subject.image_data = await _read_entity_image(image)
        subject.image_media_type = "image/png"
        audit(db, actor_type="perimetr", actor_id="core", action="subject.image.updated", target_type="subject", target_id=subject.entity_id)
        db.commit()
        db.refresh(subject)
        return subject

    @app.get("/v1/subjects/{subject_id}/image")
    def read_subject_image(subject_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> Response:
        return _entity_image_response(get_subject(db, subject_id))

    @app.delete("/v1/subjects/{subject_id}/image", response_model=SubjectRead)
    def delete_subject_image(subject_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> Subject:
        subject = get_subject(db, subject_id)
        subject.image_data = ""
        subject.image_media_type = ""
        audit(db, actor_type="perimetr", actor_id="core", action="subject.image.deleted", target_type="subject", target_id=subject.entity_id)
        db.commit()
        db.refresh(subject)
        return subject

    @app.get("/v1/subjects/{subject_id}/pod-config")
    def read_subject_pod_config(
        subject_id: str,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        subject = get_subject(db, subject_id)
        return subject_pod_config(subject, get_settings())

    @app.put("/v1/subjects/{subject_id}/pod-config")
    def update_subject_pod_config(
        subject_id: str,
        payload: SubjectPodConfigUpdate,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        subject = get_subject(db, subject_id)
        changes = payload.model_dump(exclude_none=True, mode="json")
        if "vless_connection" in changes:
            vless = validate_vless_uri(changes.pop("vless_connection"))
            encrypted = encrypt_secret(vless, get_settings())
            if encrypted != subject.vless_uri_encrypted:
                subject.vless_uri_encrypted = encrypted
                subject.network_profile_version += 1
        if "system_tabs" in changes:
            tabs = changes.pop("system_tabs")
            tab_ids = [tab["id"] for tab in tabs]
            if len(tab_ids) != len(set(tab_ids)):
                raise HTTPException(status_code=400, detail="duplicate_system_tab_id")
            if tabs != (subject.system_tabs or []):
                subject.system_tabs = tabs
                subject.system_tabs_profile_version += 1
        for key, value in changes.items():
            setattr(subject, key, value)
        audit(
            db,
            actor_type="perimetr",
            actor_id="core",
            action="subject.pod_config.updated",
            target_type="subject",
            target_id=subject.entity_id,
            payload={key: "[redacted]" if key == "vless_connection" else value for key, value in payload.model_dump(exclude_none=True, mode="json").items()},
            result={
                "network_profile_version": subject.network_profile_version,
                "system_tabs_profile_version": subject.system_tabs_profile_version,
            },
        )
        db.commit()
        return subject_pod_config(subject, get_settings())

    @app.get("/v1/subjects/{subject_id}/pods")
    def list_subject_pods(
        subject_id: str,
        include_revoked: bool = False,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        subject = get_subject(db, subject_id)
        settings = get_settings()
        records = db.scalars(
            select(PodProvisioningRecord)
            .where(PodProvisioningRecord.subject_id == subject.id)
            .order_by(PodProvisioningRecord.created_at.asc())
        ).all()
        instances = db.scalars(select(Pod).where(Pod.subject_id == subject.id).order_by(Pod.created_at.asc())).all()
        current = now_utc()
        for pod in instances:
            last_heartbeat = normalize_timestamp(pod.last_heartbeat_at)
            if pod.status not in {"revoked", "suspicious"}:
                pod.status = "active" if last_heartbeat and current - last_heartbeat <= timedelta(seconds=settings.perimetr_pod_offline_after_sec) else "offline"
        db.commit()
        if not include_revoked:
            records = [record for record in records if record.status not in {"revoked", "active", "expired"}]
            instances = [pod for pod in instances if pod.status != "revoked"]
        return {
            "provisioning": [provisioning_payload(record, subject, settings) for record in records],
            "instances": [pod_payload(pod, subject) for pod in instances],
        }

    @app.post("/v1/subjects/{subject_id}/pods", response_model=PodProvisioningRead, status_code=201)
    def create_subject_pod(
        subject_id: str,
        payload: PodProvisioningCreate,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        subject = get_subject(db, subject_id)
        settings = get_settings()
        validate_subject_pod_config(subject, settings)
        login = payload.login.strip()
        if not login:
            raise HTTPException(status_code=400, detail="pod_login_required")
        if payload.password != payload.confirm_password:
            raise HTTPException(status_code=400, detail="pod_password_confirmation_mismatch")
        decoy_password = payload.decoy_password or ""
        confirm_decoy_password = payload.confirm_decoy_password or ""
        if bool(decoy_password) != bool(confirm_decoy_password):
            raise HTTPException(status_code=400, detail="pod_decoy_password_confirmation_required")
        if decoy_password != confirm_decoy_password:
            raise HTTPException(status_code=400, detail="pod_decoy_password_confirmation_mismatch")
        if decoy_password and secrets.compare_digest(decoy_password, payload.password):
            raise HTTPException(status_code=400, detail="pod_decoy_password_must_differ")
        try:
            artifact = ensure_latest_pod_artifact(settings, force=True)
        except PodArtifactError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"pod_runtime_unavailable: {exc}",
            ) from exc
        password_hash = hash_pod_password(payload.password)
        decoy_password_hash = hash_pod_password(decoy_password) if decoy_password else ""
        _, token_hash, encrypted_token = issue_enrollment_token(settings)
        record = PodProvisioningRecord(
            subject_id=subject.id,
            name=login,
            login=login,
            password_hash=password_hash,
            decoy_password_hash=decoy_password_hash,
            status="ready_to_download",
            enrollment_token_hash=token_hash,
            enrollment_token_encrypted=encrypted_token,
            bundle_version=artifact.version,
            artifact_sha256=artifact.sha256,
            expires_at=provisioning_expiry(settings),
            metadata_json={
                "network_profile_version": subject.network_profile_version,
                "system_tabs_profile_version": subject.system_tabs_profile_version,
                "executable_name": pod_executable_name(login),
                "runtime_source": artifact.source,
                "runtime_warning": artifact.refresh_error,
                "artifact_manifest": (
                    artifact.manifest if artifact.manifest.get("signature") else {}
                ),
            },
        )
        db.add(record)
        db.flush()
        audit(
            db,
            actor_type="perimetr",
            actor_id="core",
            action="pod.provisioning.created",
            target_type="pod_provisioning",
            target_id=record.id,
            result={
                "subject_id": subject.entity_id,
                "bundle_version": artifact.version,
                "artifact_sha256": artifact.sha256,
                "runtime_source": artifact.source,
            },
        )
        db.commit()
        db.refresh(record)
        return provisioning_payload(record, subject, settings)

    @app.get("/v1/subjects/{subject_id}/pods/{provisioning_id}/download")
    def download_subject_pod(
        subject_id: str,
        provisioning_id: str,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> StreamingResponse:
        subject = get_subject(db, subject_id)
        record = db.get(PodProvisioningRecord, provisioning_id)
        if record is None or record.subject_id != subject.id:
            raise HTTPException(status_code=404, detail="pod_provisioning_not_found")
        if record.status in {"revoked", "expired", "active"} or not record.enrollment_token_encrypted:
            raise HTTPException(status_code=409, detail="pod_bundle_not_downloadable")
        if normalize_timestamp(record.expires_at) and normalize_timestamp(record.expires_at) <= now_utc():
            record.status = "expired"
            db.commit()
            raise HTTPException(status_code=410, detail="pod_provisioning_expired")
        settings = get_settings()
        try:
            if record.artifact_sha256:
                artifact = resolve_pinned_pod_artifact(
                    settings,
                    record.artifact_sha256,
                    record.bundle_version,
                    manifest=(record.metadata_json or {}).get("artifact_manifest"),
                )
                if artifact.source == "pinned-redownload":
                    record.metadata_json = {
                        **(record.metadata_json or {}),
                        "runtime_source": artifact.source,
                        "runtime_warning": "",
                    }
            else:
                artifact = ensure_latest_pod_artifact(settings, force=False)
                record.bundle_version = artifact.version
                record.artifact_sha256 = artifact.sha256
                record.metadata_json = {
                    **(record.metadata_json or {}),
                    "runtime_source": artifact.source,
                    "runtime_warning": artifact.refresh_error,
                }
            content = build_pod_bundle(record, subject, settings, artifact)
        except PodArtifactError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"pod_runtime_unavailable: {exc}",
            ) from exc
        record.status = "downloaded"
        record.download_count += 1
        record.downloaded_at = now_utc()
        audit(
            db,
            actor_type="perimetr",
            actor_id="core",
            action="pod.bundle.downloaded",
            target_type="pod_provisioning",
            target_id=record.id,
            result={
                "download_count": record.download_count,
                "bundle_version": record.bundle_version,
                "artifact_sha256": record.artifact_sha256,
                "runtime_source": artifact.source,
            },
        )
        db.commit()
        filename = re.sub(r"[^A-Za-z0-9._-]+", "-", record.name).strip("-") or "perimetr-pod"
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}.zip"'},
        )

    @app.delete("/v1/subjects/{subject_id}/pods/provisioning/{provisioning_id}")
    def delete_pending_pod(
        subject_id: str,
        provisioning_id: str,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        subject = get_subject(db, subject_id)
        record = db.get(PodProvisioningRecord, provisioning_id)
        if record is None or record.subject_id != subject.id:
            raise HTTPException(status_code=404, detail="pod_provisioning_not_found")
        if record.status == "active":
            raise HTTPException(status_code=409, detail="active_pod_must_be_revoked")
        record.status = "revoked"
        record.enrollment_token_encrypted = ""
        record.revoked_at = now_utc()
        db.add(PodDenylist(subject_id=subject.id, identifier_type="enrollment_token", identifier_value=record.enrollment_token_hash, reason="provisioning_removed"))
        audit(db, actor_type="perimetr", actor_id="core", action="pod.provisioning.removed", target_type="pod_provisioning", target_id=record.id)
        db.commit()
        return {"deleted": True, "id": record.id}

    @app.delete("/v1/subjects/{subject_id}")
    def delete_subject(subject_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        subject = get_subject(db, subject_id)
        public_id = subject.entity_id
        subject_pods = db.scalars(select(Pod).where(Pod.subject_id == subject.id)).all()
        pod_ids = [item.id for item in subject_pods]
        for pod in subject_pods:
            for identifier_type, identifier_value in (
                ("pod_id", pod.id),
                ("certificate_fingerprint", pod.certificate_fingerprint),
                ("device_binding_fingerprint", pod.device_binding_fingerprint),
            ):
                if identifier_value and not db.scalar(select(PodDenylist).where(PodDenylist.identifier_type == identifier_type, PodDenylist.identifier_value == identifier_value)):
                    db.add(PodDenylist(pod_id=pod.id, subject_id=subject.id, identifier_type=identifier_type, identifier_value=identifier_value, reason="subject_deleted"))
        db.execute(delete(AgentAssignment).where(AgentAssignment.block_type == "subject", AgentAssignment.block_id == public_id))
        db.execute(delete(LaunchAuthorization).where(LaunchAuthorization.subject_id == subject.id))
        db.execute(delete(SessionLease).where(SessionLease.subject_id == subject.id))
        if pod_ids:
            db.execute(delete(SessionLease).where(SessionLease.pod_id.in_(pod_ids)))
            db.execute(delete(Pod).where(Pod.id.in_(pod_ids)))
        db.execute(delete(PodProvisioningRecord).where(PodProvisioningRecord.subject_id == subject.id))
        _remove_correlation_block(db, f"subject_{public_id}")
        db.delete(subject)
        audit(db, actor_type="perimetr", actor_id="core", action="subject.deleted", target_type="subject", target_id=public_id)
        db.commit()
        return {"deleted": True, "id": public_id}

    @app.post("/v1/subjects/{subject_id}/materialize", response_model=MaterializeResponse)
    def materialize_subject(subject_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> MaterializeResponse:
        subject = get_subject(db, subject_id)
        if not subject.pod_id:
            raise HTTPException(status_code=400, detail="subject does not have a pod")
        pod = get_pod(db, subject.pod_id)
        pod.last_materialized_at = now_utc()
        pod.runtime_state = {**(pod.runtime_state or {}), "materialized": True}
        subject.primary_route = subject.primary_route or f"/subjects/{subject.entity_id}/web"
        audit(db, actor_type="perimetr", actor_id="core", action="subject.materialized", target_type="subject", target_id=subject.id, result={"pod_id": pod.id})
        db.commit()
        return MaterializeResponse(pod_id=pod.id, launcher_path=pod.launcher_path, state_path=f"{pod.path}/state", primary_route=subject.primary_route)

    @app.post("/v1/subjects/{subject_id}/authorize", response_model=LaunchAuthorizationRead)
    def authorize_subject(subject_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        subject = get_subject(db, subject_id)
        if not subject.pod_id:
            raise HTTPException(status_code=400, detail="subject does not have a pod")
        pod = get_pod(db, subject.pod_id)
        authorization = LaunchAuthorization(
            subject_id=subject.id,
            pod_id=pod.id,
            decision=LaunchDecision.approved.value,
            reason="authorized by perimetr",
            issued_at=now_utc(),
        )
        subject.primary_route = subject.primary_route or f"/subjects/{subject.entity_id}/web"
        db.add(authorization)
        db.flush()
        audit(db, actor_type="perimetr", actor_id="core", action="subject.authorized", target_type="subject", target_id=subject.id, result={"authorization_id": authorization.id})
        db.commit()
        db.refresh(authorization)
        return {
            "id": authorization.id,
            "subject_id": subject.entity_id,
            "pod_id": authorization.pod_id,
            "decision": authorization.decision,
            "reason": authorization.reason,
            "issued_at": authorization.issued_at,
            "expires_at": authorization.expires_at,
            "revoked_at": authorization.revoked_at,
            "created_at": authorization.created_at,
            "updated_at": authorization.updated_at,
        }

    @app.post("/v1/subjects/{subject_id}/revoke", response_model=LaunchAuthorizationRead)
    def revoke_subject(subject_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        subject = get_subject(db, subject_id)
        authorization = revoke_subject_access(db, subject, "revoked by perimetr")
        if authorization is None:
            raise HTTPException(status_code=404, detail="authorization not found")
        audit(db, actor_type="perimetr", actor_id="core", action="subject.revoked", target_type="subject", target_id=subject.id, result={"authorization_id": authorization.id})
        db.commit()
        db.refresh(authorization)
        return {
            "id": authorization.id,
            "subject_id": subject.entity_id,
            "pod_id": authorization.pod_id,
            "decision": authorization.decision,
            "reason": authorization.reason,
            "issued_at": authorization.issued_at,
            "expires_at": authorization.expires_at,
            "revoked_at": authorization.revoked_at,
            "created_at": authorization.created_at,
            "updated_at": authorization.updated_at,
        }

    @app.get("/v1/subjects/{subject_id}/state")
    def read_subject_state(subject_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        subject = get_subject(db, subject_id)
        if not subject.pod_id:
            return {"subject_id": subject.id, "state": {}}
        pod = get_pod(db, subject.pod_id)
        return {"subject_id": subject.id, "state": (pod.runtime_state or {}).get("web_subject", {})}

    @app.put("/v1/subjects/{subject_id}/state")
    def update_subject_state(subject_id: str, payload: dict, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        subject = get_subject(db, subject_id)
        if not subject.pod_id:
            raise HTTPException(status_code=400, detail="subject does not have a pod")
        pod = get_pod(db, subject.pod_id)
        pod.runtime_state = {**(pod.runtime_state or {}), "web_subject": payload, "materialized": True}
        audit(db, actor_type="perimetr", actor_id="core", action="subject.state.updated", target_type="subject", target_id=subject.id, payload=payload)
        db.commit()
        return {"subject_id": subject.id, "state": payload}

    @app.get("/subjects/{subject_id}/web", response_class=HTMLResponse)
    def subject_web_runtime(subject_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> str:
        subject = get_subject(db, subject_id)
        if subject.runtime_type != "web":
            raise HTTPException(status_code=400, detail="subject is not web runtime")
        authorization = db.scalar(
            select(LaunchAuthorization)
            .where(
                LaunchAuthorization.subject_id == subject.id,
                LaunchAuthorization.decision == LaunchDecision.approved.value,
                LaunchAuthorization.revoked_at.is_(None),
            )
            .order_by(LaunchAuthorization.created_at.desc())
        )
        if authorization is None:
            raise HTTPException(status_code=403, detail="subject_not_authorized")
        pod = get_pod(db, subject.pod_id) if subject.pod_id else None
        state = ((pod.runtime_state or {}).get("web_subject", {}) if pod else {}) or {}
        title = html.escape(str(state.get("title") or subject.name))
        body = html.escape(str(state.get("body") or subject.description or "Subject workspace is ready."))
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex,nofollow,noarchive,nosnippet" />
  <title>{title} - Web Subject</title>
  <style>
    :root {{ --dark:#000000; --light:#ffffff; --accent:#00a8ff; --line:color-mix(in srgb, var(--light) 50%, transparent); --line-mid:color-mix(in srgb, var(--light) 75%, transparent); --line-outer:var(--light); }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Consolas, Cascadia Mono, monospace; background: var(--dark); color: var(--light); }}
    main {{ min-height: 100vh; display: grid; grid-template-columns: 320px 1fr; border: 1px solid var(--line-outer); }}
    aside {{ border-right: 1px solid var(--line-mid); padding: 24px; background: var(--dark); }}
    section {{ padding: 32px; }}
    h1 {{ margin: 0 0 12px; font-size: 28px; color: var(--accent); }}
    h2 {{ color: var(--accent); }}
    .meta {{ color: #a0a0a0; line-height: 1.7; }}
    textarea, input {{ width: 100%; margin-top: 8px; border: 1px solid var(--line); background: var(--dark); color: var(--light); padding: 10px; font: inherit; }}
    textarea {{ min-height: 300px; resize: vertical; }}
    button, a {{ display: inline-flex; align-items: center; min-height: 38px; padding: 0 12px; border: 1px solid var(--line); background: var(--dark); color: var(--accent); text-decoration: none; cursor: pointer; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }}
  </style>
</head>
<body>
  <main>
    <aside>
      <div class="meta">WEB SUBJECT</div>
      <h2>{html.escape(subject.name)}</h2>
      <div class="meta">
        id: {html.escape(subject.entity_id)}<br />
        route: {html.escape(subject.primary_route or "")}
      </div>
      <div class="actions"><a href="/">core</a></div>
    </aside>
    <section>
      <label>title<input id="title" value="{title}" /></label>
      <label>workspace<textarea id="body">{body}</textarea></label>
      <div class="actions">
        <button id="save">save state</button>
        <button id="reload">reload</button>
      </div>
      <p class="meta" id="status">state is stored in PERIMETR core.</p>
    </section>
  </main>
  <script>
    async function save() {{
      const response = await fetch('/v1/subjects/{subject.entity_id}/state', {{
        method: 'PUT',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ title: document.getElementById('title').value, body: document.getElementById('body').value }})
      }});
      document.getElementById('status').textContent = response.ok ? 'saved' : await response.text();
    }}
    document.getElementById('save').addEventListener('click', save);
    document.getElementById('reload').addEventListener('click', () => location.reload());
  </script>
</body>
</html>"""

    @app.get("/v1/policies", response_model=list[PolicyRead])
    def list_policies(_: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> list[AccessPolicy]:
        return db.scalars(select(AccessPolicy).order_by(AccessPolicy.created_at.desc())).all()

    @app.post("/v1/policies", response_model=PolicyRead, status_code=201)
    def create_policy(payload: PolicyCreate, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> AccessPolicy:
        policy = AccessPolicy(**payload.model_dump())
        db.add(policy)
        db.flush()
        audit(db, actor_type="perimetr", actor_id="core", action="policy.created", target_type="policy", target_id=policy.id, payload=payload.model_dump(mode="json"), result={"status": policy.status})
        db.commit()
        db.refresh(policy)
        return policy

    @app.patch("/v1/policies/{policy_id}", response_model=PolicyRead)
    def update_policy(policy_id: str, payload: PolicyUpdate, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> AccessPolicy:
        policy = db.get(AccessPolicy, policy_id)
        if policy is None:
            raise HTTPException(status_code=404, detail=f"policy {policy_id} not found")
        for key, value in payload.model_dump(exclude_none=True).items():
            setattr(policy, key, value)
        audit(db, actor_type="perimetr", actor_id="core", action="policy.updated", target_type="policy", target_id=policy.id, payload=payload.model_dump(exclude_none=True, mode="json"), result={"status": policy.status})
        db.commit()
        db.refresh(policy)
        return policy

    @app.post("/v1/pods/enroll", response_model=PodEnrollRead, status_code=201)
    def enroll_pod(payload: PodEnrollRequest, db: Session = Depends(get_db)) -> dict:
        settings = get_settings()
        record = None
        credential_login = ""
        credential_hash = ""
        decoy_credential_hash = ""
        if payload.provisioning_id:
            record = db.get(PodProvisioningRecord, payload.provisioning_id)
            if record is None or not payload.enrollment_token:
                raise HTTPException(status_code=404, detail="pod_provisioning_not_found")
            supplied_hash = hash_token(payload.enrollment_token)
            if not secrets.compare_digest(supplied_hash, record.enrollment_token_hash):
                raise HTTPException(status_code=403, detail="invalid_enrollment_token")
            if record.status in {"active", "revoked", "expired"} or not record.enrollment_token_encrypted:
                raise HTTPException(status_code=409, detail="enrollment_token_consumed")
            if normalize_timestamp(record.expires_at) and normalize_timestamp(record.expires_at) <= now_utc():
                record.status = "expired"
                db.commit()
                raise HTTPException(status_code=410, detail="pod_provisioning_expired")
            subject = db.get(Subject, record.subject_id)
            credential_login = record.login
            credential_hash = record.password_hash
            decoy_credential_hash = record.decoy_password_hash
        elif payload.clone_from_pod_id:
            previous = get_pod(db, payload.clone_from_pod_id)
            subject = previous.subject
            credential_login = previous.login
            credential_hash = previous.password_hash
            decoy_credential_hash = previous.decoy_password_hash
        else:
            raise HTTPException(status_code=400, detail="provisioning_or_clone_source_required")
        if subject is None:
            raise HTTPException(status_code=404, detail="subject_not_found")
        access_mode = None
        if credential_hash:
            access_mode = pod_access_mode(
                username=payload.username,
                password=payload.password,
                login=credential_login,
                password_hash=credential_hash,
                decoy_password_hash=decoy_credential_hash,
            )
            credentials_valid = access_mode is not None
        else:
            credentials_valid = verify_direct_login(db, settings, target="perimetr", username=payload.username, password=payload.password)
            if credentials_valid:
                access_mode = "primary"
                credential_login = payload.username
                credential_hash = hash_pod_password(payload.password)
        if not credentials_valid:
            raise HTTPException(status_code=403, detail="invalid_credentials")
        validate_subject_pod_config(subject, settings)
        fingerprint = public_key_fingerprint(payload.public_key_pem)
        if fingerprint.upper() != payload.certificate_fingerprint.upper():
            raise HTTPException(status_code=400, detail="certificate_fingerprint_mismatch")
        blocked_values = {
            (item.identifier_type, item.identifier_value)
            for item in db.scalars(
                select(PodDenylist).where(
                    PodDenylist.identifier_value.in_([fingerprint, payload.device_binding_fingerprint])
                )
            ).all()
        }
        if ("certificate_fingerprint", fingerprint) in blocked_values:
            raise HTTPException(status_code=403, detail="certificate_fingerprint_revoked")
        if ("device_binding_fingerprint", payload.device_binding_fingerprint) in blocked_values:
            raise HTTPException(status_code=403, detail="device_binding_revoked")
        duplicate = db.scalar(select(Pod).where(Pod.certificate_fingerprint == fingerprint, Pod.status != "revoked"))
        if duplicate:
            raise HTTPException(status_code=409, detail="certificate_already_registered")
        pod = Pod(
            subject_id=subject.id,
            provisioning_id=record.id if record else None,
            name=credential_login,
            login=credential_login,
            password_hash=credential_hash,
            decoy_password_hash=decoy_credential_hash,
            status="offline",
            host_id=payload.host_id,
            path="state/profile",
            launcher_path=pod_executable_name(credential_login),
            runtime_state={"network_status": "pending", "temporary_tabs_count": 0},
            public_key_pem=payload.public_key_pem,
            certificate_fingerprint=fingerprint,
            device_binding_fingerprint=payload.device_binding_fingerprint,
            device_binding_status="valid",
            pod_version=payload.pod_version,
            network_profile_version=subject.network_profile_version,
            system_tabs_profile_version=subject.system_tabs_profile_version,
            activated_at=now_utc(),
            last_seen_at=now_utc(),
        )
        db.add(pod)
        db.flush()
        pod.identity_certificate = issue_identity_certificate(pod, settings)
        if record:
            record.status = "active"
            record.activated_at = now_utc()
            record.enrollment_token_encrypted = ""
            db.add(PodDenylist(subject_id=subject.id, identifier_type="enrollment_token", identifier_value=record.enrollment_token_hash, reason="consumed"))
        subject.pod_id = pod.id
        audit(db, actor_type="pod", actor_id=pod.id, action="pod.enrolled", target_type="subject", target_id=subject.entity_id, result={"fingerprint": fingerprint})
        db.commit()
        return {
            "pod_id": pod.id,
            "subject_id": subject.entity_id,
            "identity_certificate": pod.identity_certificate,
            "status": pod.status,
            "access_mode": access_mode,
            "access_grant": issue_pod_access_grant(pod.id, access_mode or "primary", settings),
            "next_heartbeat_sequence": 1,
            "config": pod_config_for_access(subject, settings, access_mode or "primary"),
        }

    @app.get("/v1/pods")
    def list_all_pods(
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> list[dict]:
        settings = get_settings()
        subjects = db.scalars(select(Subject).order_by(Subject.name.asc())).all()
        subject_by_id = {item.id: item for item in subjects}
        current = now_utc()
        result: list[dict] = []
        instances = db.scalars(select(Pod).where(Pod.status != "revoked").order_by(Pod.created_at.asc())).all()
        for pod in instances:
            subject = subject_by_id.get(pod.subject_id)
            if subject is None:
                continue
            last_heartbeat = normalize_timestamp(pod.last_heartbeat_at)
            if pod.status != "suspicious":
                pod.status = "active" if last_heartbeat and current - last_heartbeat <= timedelta(seconds=settings.perimetr_pod_offline_after_sec) else "offline"
            result.append({
                "kind": "instance",
                **pod_payload(pod, subject),
                "subject_name": subject.name,
            })
        records = db.scalars(
            select(PodProvisioningRecord)
            .where(PodProvisioningRecord.status.not_in(["revoked", "expired", "active"]))
            .order_by(PodProvisioningRecord.created_at.asc())
        ).all()
        for record in records:
            subject = subject_by_id.get(record.subject_id)
            if subject is None:
                continue
            result.append({
                "kind": "provisioning",
                **provisioning_payload(record, subject, settings),
                "subject_name": subject.name,
                "last_seen_at": None,
            })
        db.commit()
        return result

    @app.get("/v1/pods/{pod_id}", response_model=PodRead)
    def read_pod(pod_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> Pod:
        return get_pod(db, pod_id)

    @app.patch("/v1/pods/{pod_id}")
    def rename_pod(pod_id: str, payload: PodRenameRequest, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        pod = get_pod(db, pod_id)
        pod.name = payload.name.strip() or pod.name
        audit(db, actor_type="perimetr", actor_id="core", action="pod.renamed", target_type="pod", target_id=pod.id, result={"name": pod.name})
        db.commit()
        return pod_payload(pod, pod.subject)

    @app.put("/v1/pods/{pod_id}/password")
    def change_pod_password(
        pod_id: str,
        payload: PodPasswordUpdate,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        pod = get_pod(db, pod_id)
        if payload.new_password != payload.confirm_password:
            raise HTTPException(status_code=400, detail="pod_password_confirmation_mismatch")
        pod.password_hash = hash_pod_password(payload.new_password)
        audit(db, actor_type="perimetr", actor_id="core", action="pod.password.updated", target_type="pod", target_id=pod.id)
        db.commit()
        return {"changed": True, "id": pod.id, "login": pod.login}

    @app.post("/v1/pods/{pod_id}/verify")
    def verify_pod_access(pod_id: str, payload: DirectLoginRequest, db: Session = Depends(get_db)) -> dict:
        pod = get_pod(db, pod_id)
        if pod.status == "revoked" or db.scalar(select(PodDenylist).where(PodDenylist.identifier_type == "pod_id", PodDenylist.identifier_value == pod.id)):
            raise HTTPException(status_code=403, detail="pod_revoked")
        access_mode = None
        if pod.password_hash:
            access_mode = pod_access_mode(
                username=payload.username,
                password=payload.password,
                login=pod.login,
                password_hash=pod.password_hash,
                decoy_password_hash=pod.decoy_password_hash,
            )
            credentials_valid = access_mode is not None
        else:
            credentials_valid = verify_direct_login(db, get_settings(), target="perimetr", username=payload.username, password=payload.password)
            if credentials_valid:
                access_mode = "primary"
                pod.login = payload.username
                pod.name = payload.username
                pod.password_hash = hash_pod_password(payload.password)
        if not credentials_valid:
            raise HTTPException(status_code=403, detail="invalid_credentials")
        audit(db, actor_type="pod_user", actor_id=payload.username, action="pod.access.verified", target_type="pod", target_id=pod.id)
        db.commit()
        return {
            "allowed": True,
            "status": pod.status,
            "access_mode": access_mode,
            "access_grant": issue_pod_access_grant(pod.id, access_mode or "primary", get_settings()),
            "next_heartbeat_sequence": pod.heartbeat_sequence + 1,
            "config": pod_config_for_access(pod.subject, get_settings(), access_mode or "primary"),
        }

    @app.post("/v1/pods/{pod_id}/status")
    def read_pod_runtime_status(pod_id: str, payload: dict, db: Session = Depends(get_db)) -> dict:
        pod = db.get(Pod, pod_id)
        if pod is None:
            denied = db.scalar(select(PodDenylist).where(PodDenylist.identifier_type == "pod_id", PodDenylist.identifier_value == pod_id))
            if denied:
                return {"deleted": True, "status": "revoked"}
            raise HTTPException(status_code=404, detail="pod_not_found")
        fingerprint = str(payload.get("certificate_fingerprint") or "")
        timestamp = str(payload.get("timestamp") or "")
        signature = str(payload.get("signature") or "")
        if not fingerprint or not timestamp or not signature:
            raise HTTPException(status_code=422, detail="invalid_pod_status_request")
        if not secrets.compare_digest(fingerprint, pod.certificate_fingerprint):
            raise HTTPException(status_code=403, detail="certificate_fingerprint_mismatch")
        try:
            observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid_pod_status_timestamp") from exc
        if abs((now_utc() - observed).total_seconds()) > 300:
            raise HTTPException(status_code=400, detail="pod_status_timestamp_out_of_range")
        verify_heartbeat_signature(pod.public_key_pem, payload, signature)
        deleted = pod.status == "revoked" or bool(db.scalar(select(PodDenylist).where(PodDenylist.identifier_type == "pod_id", PodDenylist.identifier_value == pod.id)))
        return {"deleted": deleted, "status": "revoked" if deleted else pod.status}

    @app.post("/v1/pods/{pod_id}/heartbeat")
    def heartbeat_pod(pod_id: str, payload: dict, db: Session = Depends(get_db)) -> dict:
        pod = get_pod(db, pod_id)
        if not pod.public_key_pem:
            legacy = PodHeartbeatRequest.model_validate(payload)
            pod.runtime_state = {"status": legacy.status, "runtime_state": legacy.runtime_state, "observed_at": legacy.observed_at.isoformat()}
            pod.status = legacy.status
            pod.last_seen_at = legacy.observed_at
            pod.last_heartbeat_at = legacy.observed_at
            audit(db, actor_type="pod", actor_id=pod.id, action="pod.heartbeat", target_type="pod", target_id=pod.id, payload=legacy.model_dump(mode="json"), result={"status": legacy.status})
            db.commit()
            db.refresh(pod)
            return PodRead.model_validate(pod).model_dump(mode="json")
        try:
            heartbeat = PodSignedHeartbeatRequest.model_validate(payload)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="invalid_pod_heartbeat") from exc
        if pod.status == "revoked":
            raise HTTPException(status_code=403, detail="pod_revoked")
        denied = db.scalar(
            select(PodDenylist).where(
                PodDenylist.identifier_type == "certificate_fingerprint",
                PodDenylist.identifier_value == heartbeat.certificate_fingerprint,
            )
        )
        if denied:
            raise HTTPException(status_code=403, detail="certificate_fingerprint_revoked")
        if heartbeat.certificate_fingerprint != pod.certificate_fingerprint:
            raise HTTPException(status_code=403, detail="certificate_fingerprint_mismatch")
        if heartbeat.device_binding_fingerprint != pod.device_binding_fingerprint:
            pod.status = "suspicious"
            pod.device_binding_status = "mismatch"
            audit(db, actor_type="pod", actor_id=pod.id, action="pod.device_binding.mismatch", target_type="pod", target_id=pod.id)
            db.commit()
            raise HTTPException(status_code=403, detail="device_binding_mismatch")
        if heartbeat.sequence <= pod.heartbeat_sequence:
            raise HTTPException(status_code=409, detail="heartbeat_replay_detected")
        observed = heartbeat.timestamp
        if abs((now_utc() - observed).total_seconds()) > 300:
            raise HTTPException(status_code=400, detail="heartbeat_timestamp_out_of_range")
        # Verify the exact wire representation. Re-serializing a parsed timestamp
        # can expand milliseconds to microseconds and invalidate a correct signature.
        verify_heartbeat_signature(pod.public_key_pem, payload, heartbeat.signature)
        if heartbeat.access_grant:
            access_mode = verify_pod_access_grant(heartbeat.access_grant, pod.id, get_settings())
        elif pod.decoy_password_hash:
            raise HTTPException(status_code=403, detail="pod_access_grant_required")
        else:
            # Backward compatibility for Pods created before decoy credentials existed.
            access_mode = "primary"
        previous_network_status = (pod.runtime_state or {}).get("network_status")
        pod.heartbeat_sequence = heartbeat.sequence
        pod.status = "active"
        pod.device_binding_status = heartbeat.device_binding_status
        pod.pod_version = heartbeat.pod_version
        pod.xray_version = heartbeat.xray_version
        pod.last_seen_at = now_utc()
        pod.last_heartbeat_at = now_utc()
        pod.runtime_state = {
            "network_status": heartbeat.network_status,
            "proxy_engine": heartbeat.proxy_engine,
            "temporary_tabs_count": heartbeat.temporary_tabs_count,
        }
        pod.network_profile_version = pod.subject.network_profile_version
        pod.system_tabs_profile_version = pod.subject.system_tabs_profile_version
        if heartbeat.network_status == "proxy_verified" and previous_network_status != "proxy_verified":
            audit(db, actor_type="pod", actor_id=pod.id, action="pod.session.opened", target_type="pod", target_id=pod.id, result={"subject_id": pod.subject.entity_id, "network_status": heartbeat.network_status})
        audit(db, actor_type="pod", actor_id=pod.id, action="pod.heartbeat", target_type="pod", target_id=pod.id, result={"status": pod.status, "network_status": heartbeat.network_status})
        db.commit()
        return {
            "allowed": True,
            "status": pod.status,
            "lease_seconds": get_settings().perimetr_pod_offline_after_sec,
            "config": pod_config_for_access(pod.subject, get_settings(), access_mode),
        }

    @app.delete("/v1/pods/{pod_id}")
    def revoke_pod(pod_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        pod = db.scalar(select(Pod).where(Pod.id == pod_id).with_for_update())
        if pod is None:
            raise HTTPException(status_code=404, detail=f"pod {pod_id} not found")
        if pod.status != "revoked":
            values = [
                ("pod_id", pod.id),
                ("certificate_fingerprint", pod.certificate_fingerprint),
                ("device_binding_fingerprint", pod.device_binding_fingerprint),
            ]
            for identifier_type, identifier_value in values:
                if not identifier_value:
                    continue
                exists = db.scalar(select(PodDenylist).where(PodDenylist.identifier_type == identifier_type, PodDenylist.identifier_value == identifier_value))
                if not exists:
                    db.add(PodDenylist(pod_id=pod.id, subject_id=pod.subject_id, identifier_type=identifier_type, identifier_value=identifier_value, reason="operator_deleted"))
            pod.status = "revoked"
            pod.revoked_at = now_utc()
            pod.revoke_reason = "operator_deleted"
            if pod.subject.pod_id == pod.id:
                pod.subject.pod_id = None
            audit(db, actor_type="perimetr", actor_id="core", action="pod.revoked", target_type="pod", target_id=pod.id, result={"fingerprint_blacklisted": bool(pod.certificate_fingerprint)})
            db.commit()
        return {"deleted": True, "id": pod.id, "status": "revoked"}

    @app.post("/v1/pods/{pod_id}/release", response_model=PodRead)
    def release_pod(pod_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> Pod:
        pod = get_pod(db, pod_id)
        pod.runtime_state = {**pod.runtime_state, "released": True}
        audit(db, actor_type="perimetr", actor_id="core", action="pod.released", target_type="pod", target_id=pod.id, result={"released": True})
        db.commit()
        db.refresh(pod)
        return pod

    def _assignment_payload(db: Session, assignment: AgentAssignment) -> AgentAssignmentRead:
        return AgentAssignmentRead(
            id=assignment.id,
            agent_id=assignment.agent_id,
            block_id=assignment.block_id,
            block_type=assignment.block_type,
            position=assignment.position,
            created_by=assignment.created_by,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at,
            agent=AgentControlRead(**summarize_agent(db, assignment.agent)) if assignment.agent else None,
        )

    @app.get("/api/blocks/{block_id}/agents", response_model=list[AgentAssignmentRead])
    def list_block_agents(
        block_id: str,
        block_type: str = Query(...),
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> list[AgentAssignmentRead]:
        normalized = normalize_agent_block_type(block_type)
        assignments = db.scalars(
            select(AgentAssignment)
            .where(AgentAssignment.block_id == block_id, AgentAssignment.block_type == normalized)
            .order_by(AgentAssignment.position.asc(), AgentAssignment.created_at.asc())
        ).all()
        return [_assignment_payload(db, item) for item in assignments]

    @app.post("/api/blocks/{block_id}/agents", response_model=AgentAssignmentRead, status_code=201)
    def add_block_agent(
        block_id: str,
        payload: AgentAssignmentCreate,
        block_type: str = Query(...),
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> AgentAssignmentRead:
        assignment = assign_agent_to_block(db, agent_id=payload.agent_id, block_type=block_type, block_id=block_id, created_by=payload.created_by)
        audit(db, actor_type="perimetr", actor_id=payload.created_by, action="agent.assigned", target_type="agent", target_id=payload.agent_id, payload={"block_id": block_id, "block_type": block_type})
        db.commit()
        db.refresh(assignment)
        return _assignment_payload(db, assignment)

    @app.delete("/api/blocks/{block_id}/agents/{agent_id}")
    def remove_block_agent(
        block_id: str,
        agent_id: str,
        block_type: str = Query(...),
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        unassign_agent_from_block(db, agent_id=agent_id, block_type=block_type, block_id=block_id)
        audit(db, actor_type="perimetr", actor_id="operator", action="agent.unassigned", target_type="agent", target_id=agent_id, payload={"block_id": block_id, "block_type": block_type}, result={"server_agent_removed": False, "sindri_removed": False})
        db.commit()
        return {"removed": True, "revoke_sent": False}

    @app.post("/api/blocks/{block_id}/agents/reorder")
    def reorder_agents(
        block_id: str,
        payload: AgentReorderRequest,
        block_type: str = Query(...),
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        reorder_block_agents(db, block_type=block_type, block_id=block_id, ordered_agent_ids=payload.ordered_agent_ids)
        audit(db, actor_type="perimetr", actor_id="operator", action="agent.assignments.reordered", target_type="block", target_id=block_id, payload={"block_type": block_type, "ordered_agent_ids": payload.ordered_agent_ids})
        db.commit()
        return {"reordered": True}

    @app.get("/api/agents/library", response_model=list[AgentControlRead])
    def list_agent_library(
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> list[AgentControlRead]:
        agents = db.scalars(select(Agent).order_by(Agent.library_position.asc(), Agent.created_at.asc())).all()
        return [AgentControlRead(**summarize_agent(db, agent)) for agent in agents]

    @app.post("/api/agents/reorder")
    def reorder_agent_library(
        payload: AgentReorderRequest,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> dict:
        agents = db.scalars(select(Agent)).all()
        by_id = {agent.id: agent for agent in agents}
        if set(payload.ordered_agent_ids) != set(by_id):
            raise HTTPException(status_code=400, detail="AGENT_LIBRARY_ORDER_MISMATCH")
        for position, agent_id in enumerate(payload.ordered_agent_ids):
            by_id[agent_id].library_position = position
        audit(db, actor_type="perimetr", actor_id="operator", action="agent.library.reordered", target_type="agent_library", target_id=PERIMETR_SYSTEM_ENTITY_ID, payload={"ordered_agent_ids": payload.ordered_agent_ids})
        db.commit()
        return {"reordered": True}

    @app.post("/api/agents/enroll", response_model=AgentControlRead, status_code=201)
    def enroll_agent(
        payload: AgentEnrollRequest,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> AgentControlRead:
        existing = db.get(Agent, payload.agent_id)
        denied = db.scalar(
            select(CertificateDenylist).where(
                (CertificateDenylist.agent_id == payload.agent_id)
                | (CertificateDenylist.fingerprint_sha256 == payload.identity_fingerprint)
                | (
                    (CertificateDenylist.serial_number != "")
                    & (CertificateDenylist.serial_number == (payload.certificate_serial or ""))
                )
            )
        )
        if denied or (existing and existing.enrollment_state == "revoked"):
            raise HTTPException(status_code=409, detail="AGENT_REVOKED")
        base_url = payload.api_base_url or f"https://{payload.domain}:{payload.port}"
        remote_enrollment = None
        if payload.enrollment_token:
            settings = get_settings()
            controller_identity = ensure_controller_signing_material(
                db, settings, PERIMETR_SYSTEM_ENTITY_ID
            )
            heartbeat_endpoint = (
                f"{settings.perimetr_public_url.rstrip('/')}"
                f"/api/agents/{payload.agent_id}/heartbeat"
            )
            try:
                remote_enrollment = enroll_remote_agent(
                    base_url=base_url,
                    agent_id=payload.agent_id,
                    enrollment_token=payload.enrollment_token,
                    expected_fingerprint=payload.identity_fingerprint,
                    controller_id=PERIMETR_SYSTEM_ENTITY_ID,
                    controller_certificate_pem=controller_identity.certificate_pem,
                    heartbeat_endpoint=heartbeat_endpoint,
                    timeout_seconds=settings.perimetr_agent_request_timeout_sec,
                )
            except AgentTransportError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"AGENT_ENROLLMENT_FAILED: {exc}",
                ) from exc
        agent = existing or Agent(
            id=payload.agent_id,
            name=payload.display_name,
            agent_type="agent",
            host_id=payload.domain,
            identity_fingerprint=payload.identity_fingerprint,
            api_base_url=base_url,
        )
        if existing is None:
            last_position = db.scalar(select(func.max(Agent.library_position)))
            agent.library_position = (last_position if last_position is not None else -1) + 1
            db.add(agent)
        agent.name = payload.display_name
        agent.display_name = payload.display_name
        agent.domain = payload.domain
        agent.port = payload.port
        agent.host_id = payload.domain
        agent.api_base_url = base_url
        previous_fingerprint = agent.identity_fingerprint
        if existing and previous_fingerprint and previous_fingerprint != payload.identity_fingerprint:
            previous_certificate = db.scalar(
                select(AgentCertificate).where(
                    AgentCertificate.agent_id == agent.id,
                    AgentCertificate.fingerprint_sha256 == previous_fingerprint,
                )
            )
            if previous_certificate:
                previous_certificate.status = "rotated"
        agent.identity_fingerprint = (
            remote_enrollment["fingerprint_sha256"]
            if remote_enrollment
            else payload.identity_fingerprint
        )
        agent.identity_certificate = (
            remote_enrollment["identity_certificate_pem"]
            if remote_enrollment
            else payload.identity_certificate
        )
        agent.certificate_serial = (
            remote_enrollment["certificate_serial"]
            if remote_enrollment
            else payload.certificate_serial
        )
        if remote_enrollment:
            agent.certificate_valid_not_before = remote_enrollment["certificate_valid_not_before"]
            agent.certificate_valid_not_after = remote_enrollment["certificate_valid_not_after"]
        agent.enrollment_state = "enrolled"
        agent.status = "OFFLINE"
        agent.agent_version = (
            remote_enrollment.get("agent_version") or payload.agent_version
            if remote_enrollment
            else payload.agent_version
        )
        agent.sindri_version = (
            remote_enrollment.get("sindri_version") or payload.sindri_version
            if remote_enrollment
            else payload.sindri_version
        )
        agent.sindri_protocol_version = (
            remote_enrollment.get("sindri_protocol_version") or payload.sindri_protocol_version
            if remote_enrollment
            else payload.sindri_protocol_version
        )
        agent.tags = payload.tags
        agent.environment = payload.environment
        agent.notes = payload.notes
        agent.metadata_json = {
            **(agent.metadata_json or {}),
            "remote_enrolled": bool(remote_enrollment),
            "controller_id": PERIMETR_SYSTEM_ENTITY_ID if remote_enrollment else "",
            "request_signing_required": bool(
                remote_enrollment
                and remote_enrollment.get("request_auth") == "ecdsa-p256-sha256-v1"
            ),
        }
        db.flush()
        certificate = db.scalar(
            select(AgentCertificate).where(
                AgentCertificate.agent_id == agent.id,
                AgentCertificate.fingerprint_sha256 == agent.identity_fingerprint,
            )
        )
        if certificate is None:
            db.add(
                AgentCertificate(
                    agent_id=agent.id,
                    fingerprint_sha256=agent.identity_fingerprint,
                    serial_number=agent.certificate_serial or "",
                    certificate_pem=agent.identity_certificate,
                    valid_not_before=agent.certificate_valid_not_before,
                    valid_not_after=agent.certificate_valid_not_after,
                    status="active",
                )
            )
        endpoint = db.scalar(select(AgentEndpoint).where(AgentEndpoint.agent_id == agent.id))
        if endpoint is None:
            endpoint = AgentEndpoint(agent_id=agent.id, domain=payload.domain, port=payload.port, base_url=base_url)
            db.add(endpoint)
        else:
            endpoint.domain = payload.domain
            endpoint.port = payload.port
            endpoint.base_url = base_url
            endpoint.status = "active"
        capabilities = (
            list(remote_enrollment.get("capabilities") or payload.capabilities)
            if remote_enrollment
            else payload.capabilities
        )
        upsert_agent_capabilities(db, agent.id, capabilities)
        audit(
            db,
            actor_type="perimetr",
            actor_id="operator",
            action="agent.enrolled",
            target_type="agent",
            target_id=agent.id,
            payload={
                **payload.model_dump(mode="json", exclude={"enrollment_token"}),
                "enrollment_token": "[redacted]" if payload.enrollment_token else "",
            },
            result={
                "state": agent.enrollment_state,
                "remote_enrolled": bool(remote_enrollment),
            },
        )
        db.commit()
        db.refresh(agent)
        return AgentControlRead(**summarize_agent(db, agent))

    @app.get("/api/agents/{agent_id}", response_model=AgentControlRead)
    def read_agent_control(agent_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> AgentControlRead:
        return AgentControlRead(**summarize_agent(db, find_agent(db, agent_id)))

    @app.patch("/api/agents/{agent_id}", response_model=AgentControlRead)
    def update_agent_control(
        agent_id: str,
        payload: AgentUpdateRequest,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> AgentControlRead:
        agent = find_agent(db, agent_id)
        data = payload.model_dump(exclude_none=True)
        if "display_name" in data:
            agent.display_name = data["display_name"]
            agent.name = data["display_name"]
        if "tags" in data:
            agent.tags = data["tags"]
        if "environment" in data:
            agent.environment = data["environment"]
        if "notes" in data:
            agent.notes = data["notes"]
        audit(db, actor_type="perimetr", actor_id="operator", action="agent.metadata.updated", target_type="agent", target_id=agent.id, payload=data)
        db.commit()
        db.refresh(agent)
        return AgentControlRead(**summarize_agent(db, agent))

    @app.delete("/api/agents/{agent_id}")
    def delete_agent_control(agent_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        agent = find_agent(db, agent_id)
        denied = db.scalar(select(CertificateDenylist).where(CertificateDenylist.fingerprint_sha256 == agent.identity_fingerprint))
        if denied is None:
            db.add(CertificateDenylist(
                agent_id=agent.id,
                fingerprint_sha256=agent.identity_fingerprint,
                serial_number=agent.certificate_serial or "",
                reason="agent_deleted_from_perimetr",
            ))
        dependent_models = [
            ApprovalDecision, ApprovalRequest, JobResult, JobEvent, AgentJob,
            AgentCommand, SessionLease, RevocationRecord, AgentStateEvent,
            AgentHeartbeat, AgentCapability, AgentCertificate, AgentEndpoint,
            AgentAssignment,
        ]
        for model in dependent_models:
            db.execute(delete(model).where(model.agent_id == agent.id))
        public_id = agent.id
        db.delete(agent)
        audit(db, actor_type="perimetr", actor_id="operator", action="agent.deleted", target_type="agent", target_id=public_id, result={"server_agent_removed": False, "identity_denylisted": True})
        db.commit()
        return {"deleted": True, "id": public_id, "server_agent_removed": False}

    @app.get("/api/agents/{agent_id}/capabilities")
    def list_agent_capabilities(agent_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        find_agent(db, agent_id)
        capabilities = db.scalars(select(AgentCapability).where(AgentCapability.agent_id == agent_id).order_by(AgentCapability.group.asc(), AgentCapability.action.asc())).all()
        return {"items": [{"action": item.action, "title": item.title, "description": item.description, "group": item.group, "risk": item.risk, "inputs": item.inputs, "available": item.available} for item in capabilities]}

    @app.post("/api/agents/{agent_id}/heartbeat")
    async def receive_agent_heartbeat(
        agent_id: str,
        payload: AgentControlHeartbeatRequest,
        request: Request,
        db: Session = Depends(get_db),
    ) -> dict:
        agent = find_agent(db, agent_id)
        if agent.enrollment_state == "revoked" or db.scalar(
            select(CertificateDenylist).where(CertificateDenylist.agent_id == agent_id)
        ):
            raise HTTPException(status_code=403, detail="AGENT_REVOKED")
        if payload.agent_id != agent.id:
            raise HTTPException(status_code=400, detail="AGENT_ID_MISMATCH")
        await require_agent_callback_authentication(request, agent)
        heartbeat = apply_agent_heartbeat(db, agent=agent, payload=payload.model_dump(mode="python"))
        db.commit()
        return {"accepted": True, "heartbeat_id": heartbeat.id, "status": visible_agent_status(agent)}

    @app.post("/api/agents/{agent_id}/jobs", response_model=AgentJobRead, status_code=201)
    def create_control_job(
        agent_id: str,
        payload: AgentJobCreate,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> AgentJob:
        agent = find_agent(db, agent_id)
        job = create_agent_job(db, agent=agent, action=payload.action, inputs=payload.inputs, created_by=payload.created_by, expires_at=payload.expires_at)
        audit(
            db,
            actor_type="perimetr",
            actor_id=payload.created_by,
            action="agent.job.created",
            target_type="job",
            target_id=job.job_id,
            payload={
                "action": payload.action,
                "inputs": job.inputs,
                "created_by": payload.created_by,
                "expires_at": (
                    payload.expires_at.isoformat()
                    if payload.expires_at
                    else None
                ),
            },
            result={"agent_id": agent.id, "status": job.status},
        )
        db.commit()
        db.refresh(job)
        if (agent.metadata_json or {}).get("remote_enrolled"):
            try:
                controller_identity = ensure_controller_signing_material(
                    db, get_settings(), PERIMETR_SYSTEM_ENTITY_ID
                )
                dispatch_remote_agent_job(
                    base_url=agent.api_base_url,
                    controller_id=PERIMETR_SYSTEM_ENTITY_ID,
                    timeout_seconds=get_settings().perimetr_agent_request_timeout_sec,
                    job_id=job.job_id,
                    request_id=job.request_id,
                    action=job.action,
                    inputs=payload.inputs,
                    created_at=job.created_at,
                    expires_at=job.expires_at,
                    controller_private_key_pem=controller_identity.private_key_pem,
                )
                record_job_event(
                    db,
                    agent_id=agent.id,
                    job_id=job.job_id,
                    event_type="job.dispatched",
                    status=job.status,
                )
                audit(
                    db,
                    actor_type="perimetr",
                    actor_id=payload.created_by,
                    action="agent.job.dispatched",
                    target_type="job",
                    target_id=job.job_id,
                    result={"agent_id": agent.id},
                )
                db.commit()
                db.refresh(job)
            except AgentTransportError as exc:
                job.status = "DELIVERY_FAILED"
                job.error = {"code": "AGENT_DELIVERY_FAILED", "message": str(exc)}
                record_job_event(
                    db,
                    agent_id=agent.id,
                    job_id=job.job_id,
                    event_type="job.delivery_failed",
                    status=job.status,
                    message=str(exc),
                )
                db.commit()
                raise HTTPException(
                    status_code=502,
                    detail=f"AGENT_JOB_DELIVERY_FAILED: {exc}",
                ) from exc
        return job

    @app.get("/api/agents/{agent_id}/jobs", response_model=list[AgentJobRead])
    def list_control_jobs(agent_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> list[AgentJob]:
        find_agent(db, agent_id)
        return db.scalars(select(AgentJob).where(AgentJob.agent_id == agent_id).order_by(AgentJob.created_at.desc())).all()

    @app.get("/api/agents/{agent_id}/jobs/{job_id}", response_model=AgentJobRead)
    def read_control_job(agent_id: str, job_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> AgentJob:
        return get_agent_job(db, agent_id, job_id)

    @app.post("/api/agents/{agent_id}/jobs/{job_id}/events", response_model=JobEventRead)
    async def ingest_job_event(
        agent_id: str,
        job_id: str,
        payload: dict,
        request: Request,
        db: Session = Depends(get_db),
    ) -> JobEvent:
        agent = find_agent(db, agent_id)
        await require_agent_callback_authentication(request, agent)
        event = apply_agent_job_event(db, agent_id=agent_id, job_id=job_id, payload=payload)
        db.commit()
        db.refresh(event)
        return event

    @app.get("/api/agents/{agent_id}/jobs/{job_id}/events", response_model=list[JobEventRead])
    def list_job_events(agent_id: str, job_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> list[JobEvent]:
        get_agent_job(db, agent_id, job_id)
        return db.scalars(select(JobEvent).where(JobEvent.agent_id == agent_id, JobEvent.job_id == job_id).order_by(JobEvent.sequence.asc())).all()

    @app.post("/api/agents/{agent_id}/jobs/{job_id}/approve")
    def approve_job(agent_id: str, job_id: str, payload: ApprovalDecisionRequest, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        agent = find_agent(db, agent_id)
        decision = decide_approval(db, agent_id=agent_id, job_id=job_id, approval_id=payload.approval_id, plan_hash=payload.plan_hash, decision="approved", actor=payload.decided_by)
        audit(db, actor_type="perimetr", actor_id=payload.decided_by, action="agent.job.approved", target_type="job", target_id=job_id, payload=payload.model_dump(mode="json"))
        forwarded = False
        if (agent.metadata_json or {}).get("remote_enrolled"):
            try:
                controller_identity = ensure_controller_signing_material(
                    db, get_settings(), PERIMETR_SYSTEM_ENTITY_ID
                )
                decide_remote_agent_job(
                    base_url=agent.api_base_url,
                    controller_id=PERIMETR_SYSTEM_ENTITY_ID,
                    timeout_seconds=get_settings().perimetr_agent_request_timeout_sec,
                    job_id=job_id,
                    decision="approved",
                    approval_id=payload.approval_id,
                    plan_hash=payload.plan_hash,
                    confirmation_phrase=payload.confirmation_phrase,
                    hostname_confirmation=payload.hostname_confirmation,
                    controller_private_key_pem=controller_identity.private_key_pem,
                )
                forwarded = True
            except AgentTransportError as exc:
                db.rollback()
                raise HTTPException(
                    status_code=502,
                    detail=f"AGENT_APPROVAL_FORWARD_FAILED: {exc}",
                ) from exc
        db.commit()
        return {"decision": decision.decision, "forward_to_agent": forwarded}

    @app.post("/api/agents/{agent_id}/jobs/{job_id}/reject")
    def reject_job(agent_id: str, job_id: str, payload: ApprovalDecisionRequest, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        agent = find_agent(db, agent_id)
        decision = decide_approval(db, agent_id=agent_id, job_id=job_id, approval_id=payload.approval_id, plan_hash=payload.plan_hash, decision="rejected", actor=payload.decided_by)
        audit(db, actor_type="perimetr", actor_id=payload.decided_by, action="agent.job.rejected", target_type="job", target_id=job_id, payload=payload.model_dump(mode="json"))
        forwarded = False
        if (agent.metadata_json or {}).get("remote_enrolled"):
            try:
                controller_identity = ensure_controller_signing_material(
                    db, get_settings(), PERIMETR_SYSTEM_ENTITY_ID
                )
                decide_remote_agent_job(
                    base_url=agent.api_base_url,
                    controller_id=PERIMETR_SYSTEM_ENTITY_ID,
                    timeout_seconds=get_settings().perimetr_agent_request_timeout_sec,
                    job_id=job_id,
                    decision="rejected",
                    approval_id=payload.approval_id,
                    plan_hash=payload.plan_hash,
                    controller_private_key_pem=controller_identity.private_key_pem,
                )
                forwarded = True
            except AgentTransportError as exc:
                db.rollback()
                raise HTTPException(
                    status_code=502,
                    detail=f"AGENT_REJECTION_FORWARD_FAILED: {exc}",
                ) from exc
        db.commit()
        return {"decision": decision.decision, "forward_to_agent": forwarded}

    @app.post("/api/agents/{agent_id}/jobs/{job_id}/cancel")
    def cancel_job(agent_id: str, job_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        agent = find_agent(db, agent_id)
        job = get_agent_job(db, agent_id, job_id)
        if job.status == "RUNNING":
            raise HTTPException(status_code=409, detail="CANCEL_NOT_SAFE")
        job.status = "CANCELLED"
        job.canceller = "operator"
        record_job_event(db, agent_id=agent_id, job_id=job_id, event_type="job.cancelled", status="CANCELLED")
        audit(db, actor_type="perimetr", actor_id="operator", action="agent.job.cancelled", target_type="job", target_id=job_id)
        forwarded = False
        if (agent.metadata_json or {}).get("remote_enrolled"):
            try:
                controller_identity = ensure_controller_signing_material(
                    db, get_settings(), PERIMETR_SYSTEM_ENTITY_ID
                )
                cancel_remote_agent_job(
                    base_url=agent.api_base_url,
                    controller_id=PERIMETR_SYSTEM_ENTITY_ID,
                    timeout_seconds=get_settings().perimetr_agent_request_timeout_sec,
                    job_id=job_id,
                    controller_private_key_pem=controller_identity.private_key_pem,
                )
                forwarded = True
            except AgentTransportError as exc:
                db.rollback()
                raise HTTPException(
                    status_code=502,
                    detail=f"AGENT_CANCEL_FORWARD_FAILED: {exc}",
                ) from exc
        db.commit()
        return {"cancelled": True, "forward_to_agent": forwarded}

    def serialize_approval(db: Session, approval: ApprovalRequest) -> dict:
        job = get_agent_job(db, approval.agent_id, approval.job_id)
        agent = find_agent(db, approval.agent_id)
        return {
            "id": approval.id,
            "agent_id": approval.agent_id,
            "job_id": approval.job_id,
            "approval_id": approval.approval_id,
            "plan_hash": approval.plan_hash,
            "risk": approval.risk,
            "warning": approval.warning,
            "plan": approval.plan,
            "expires_at": approval.expires_at,
            "status": approval.status,
            "action": job.action,
            "hostname": agent.hostname or agent.domain or "",
            "created_at": approval.created_at,
            "updated_at": approval.updated_at,
        }

    @app.get("/api/agents/{agent_id}/approvals", response_model=list[ApprovalRequestRead])
    def list_agent_approvals(agent_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> list[dict]:
        find_agent(db, agent_id)
        approvals = db.scalars(
            select(ApprovalRequest)
            .where(ApprovalRequest.agent_id == agent_id)
            .order_by(ApprovalRequest.created_at.desc())
        ).all()
        return [serialize_approval(db, approval) for approval in approvals]

    @app.get("/api/approvals/pending", response_model=list[ApprovalRequestRead])
    def list_pending_approvals(
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> list[dict]:
        approvals = db.scalars(
            select(ApprovalRequest)
            .where(ApprovalRequest.status == "PENDING")
            .order_by(ApprovalRequest.created_at.asc())
        ).all()
        return [serialize_approval(db, approval) for approval in approvals]

    @app.post("/api/agents/{agent_id}/revoke")
    def prepare_agent_revoke(agent_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> dict:
        agent = find_agent(db, agent_id)
        plan = [
            "Stop accepting new jobs",
            "Cancel queued jobs",
            "Revoke Agent identity",
            "Remove Agent Node service",
            "Remove Agent Node files",
            "Close Agent Node firewall port if owned by installer and safe",
        ]
        record = db.scalar(select(RevocationRecord).where(RevocationRecord.agent_id == agent.id, RevocationRecord.status == "prepared"))
        if record is None:
            record = RevocationRecord(agent_id=agent.id, certificate_fingerprint_sha256=agent.identity_fingerprint, certificate_serial=agent.certificate_serial or "", payload={"plan": plan})
            db.add(record)
        denied = db.scalar(select(CertificateDenylist).where(CertificateDenylist.fingerprint_sha256 == agent.identity_fingerprint))
        if denied is None:
            db.add(CertificateDenylist(agent_id=agent.id, fingerprint_sha256=agent.identity_fingerprint, serial_number=agent.certificate_serial or "", reason="agent_revoke_prepared"))
        else:
            denied.agent_id = agent.id
        audit(db, actor_type="perimetr", actor_id="operator", action="agent.revoke.prepared", target_type="agent", target_id=agent.id, result={"plan": plan})
        db.commit()
        return {"status": "approval_required", "action": "agent.revoke", "plan": plan, "agent_id": agent.id}

    @app.post("/v1/agents/register", response_model=AgentRead, status_code=201)
    def register_agent(
        payload: AgentRegisterRequest,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> Agent:
        existing = db.scalar(select(Agent).where(Agent.host_id == payload.host_id, Agent.identity_fingerprint == payload.identity_fingerprint))
        if existing:
            raise HTTPException(status_code=409, detail="agent already registered")
        agent = Agent(
            name=payload.name,
            agent_type=payload.agent_type.value,
            host_id=payload.host_id,
            status="registered",
            identity_fingerprint=payload.identity_fingerprint,
            api_base_url=payload.api_base_url,
        )
        db.add(agent)
        db.flush()
        audit(db, actor_type="agent", actor_id=agent.id, action="agent.registered", target_type="agent", target_id=agent.id, payload=payload.model_dump(mode="json"), result={"status": agent.status})
        db.commit()
        db.refresh(agent)
        return agent

    @app.post("/v1/agents/{agent_id}/heartbeat", response_model=AgentRead)
    def heartbeat_agent(
        agent_id: str,
        payload: AgentHeartbeatRequest,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> Agent:
        agent = get_agent(db, agent_id)
        agent.status = payload.status
        agent.last_heartbeat_at = payload.observed_at
        audit(db, actor_type="agent", actor_id=agent.id, action="agent.heartbeat", target_type="agent", target_id=agent.id, payload=payload.model_dump(mode="json"), result={"status": agent.status})
        db.commit()
        db.refresh(agent)
        return agent

    @app.get("/v1/agents", response_model=list[AgentRead])
    def list_agents(_: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> list[Agent]:
        return db.scalars(select(Agent).order_by(Agent.created_at.desc())).all()

    @app.post("/v1/agents/{agent_id}/commands", response_model=AgentCommandRead, status_code=201)
    def create_agent_command(agent_id: str, payload: AgentCommandCreate, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> AgentCommand:
        agent = get_agent(db, agent_id)
        ensure_allowed_agent_command(payload.command)
        command = AgentCommand(agent_id=agent.id, command=payload.command, target=payload.target, params=payload.params)
        db.add(command)
        db.flush()
        audit(db, actor_type="perimetr", actor_id="core", action="agent.command.queued", target_type="agent_command", target_id=command.id, payload=payload.model_dump(mode="json"), result={"status": command.status})
        db.commit()
        db.refresh(command)
        return command

    @app.get("/v1/agents/{agent_id}/commands/pending", response_model=list[AgentCommandRead])
    def list_pending_commands(agent_id: str, _: SessionLease = Depends(require_core_access), db: Session = Depends(get_db)) -> list[AgentCommand]:
        get_agent(db, agent_id)
        return list_pending_agent_commands(db, agent_id)

    @app.post("/v1/agents/{agent_id}/commands/{command_id}/status", response_model=AgentCommandRead)
    def update_agent_command(
        agent_id: str,
        command_id: str,
        payload: AgentCommandStatusUpdate,
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> AgentCommand:
        get_agent(db, agent_id)
        command = get_command(db, command_id)
        if command.agent_id != agent_id:
            raise HTTPException(status_code=404, detail="command does not belong to agent")
        previous_status = command.status
        update_agent_command_status(db, command, status=payload.status, result=payload.result)
        audit(db, actor_type="agent", actor_id=agent_id, action=f"agent.command.{payload.status}", target_type="agent_command", target_id=command.id, payload=payload.model_dump(mode="json"), result={"previous_status": previous_status, "status": command.status})
        db.commit()
        db.refresh(command)
        return command

    @app.get("/v1/audit", response_model=list[AuditRead])
    def list_audit_events(
        actor_type: str | None = None,
        actor_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        action: str | None = None,
        from_ts: datetime | None = Query(None, alias="from"),
        to_ts: datetime | None = Query(None, alias="to"),
        _: SessionLease = Depends(require_core_access),
        db: Session = Depends(get_db),
    ) -> list[AuditEvent]:
        query = select(AuditEvent).order_by(AuditEvent.created_at.desc())
        if actor_type:
            query = query.where(AuditEvent.actor_type == actor_type)
        if actor_id:
            query = query.where(AuditEvent.actor_id == actor_id)
        if target_type:
            query = query.where(AuditEvent.target_type == target_type)
        if target_id:
            query = query.where(AuditEvent.target_id == target_id)
        if action:
            query = query.where(AuditEvent.action == action)
        if from_ts:
            query = query.where(AuditEvent.created_at >= from_ts)
        if to_ts:
            query = query.where(AuditEvent.created_at <= to_ts)
        return db.scalars(query).all()

    return app
