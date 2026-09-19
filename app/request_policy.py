"""Common browser request boundary; machine identities remain route-scoped."""
from __future__ import annotations

import ipaddress
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from .security import csrf_token, constant_time_text_equal

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def client_identity(request: Request, trusted_proxies: str) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        address = ipaddress.ip_address(peer)
        trusted = any(address in ipaddress.ip_network(item.strip(), strict=False)
                      for item in trusted_proxies.split(",") if item.strip())
        if trusted and request.headers.get("x-real-ip"):
            return str(ipaddress.ip_address(request.headers["x-real-ip"]))
    except ValueError:
        pass
    return peer


def validate_browser_origin(request: Request, public_url: str) -> None:
    if request.method in SAFE_METHODS:
        return
    origin = request.headers.get("origin")
    expected = urlsplit(public_url)
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site request denied")
    if origin:
        try:
            observed = urlsplit(origin)
            def identity(value):
                return value.scheme.lower(), value.hostname, value.port or (443 if value.scheme == "https" else 80)
            valid = identity(observed) == identity(expected) and not observed.username and not observed.password and not observed.query and not observed.fragment and observed.path in {"", "/"}
        except ValueError:
            valid = False
        if not valid:
            raise HTTPException(403, "Cross-site request denied")


def validate_csrf(request: Request, session_key_hash: str, public_url: str) -> None:
    validate_browser_origin(request, public_url)
    if request.method not in SAFE_METHODS and not constant_time_text_equal(
        request.headers.get("x-csrf-token", ""), csrf_token(session_key_hash)
    ):
        raise HTTPException(403, "Refresh the session before submitting this action")
import asyncio


class RequestBoundary:
    """One writer per API process; snapshot/restore holds the same write barrier.

    The supported deployment runs one Uvicorn worker. Body limits are enforced
    on streamed chunks before JSON or multipart parsing, including chunked input.
    """
    def __init__(self, app):
        self.app = app
        self.lock = asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        from .settings import get_settings
        from starlette.responses import JSONResponse
        path = scope["path"]
        settings = get_settings()
        if settings.perimetr_env == "production":
            headers = dict(scope["headers"])
            try:
                host = urlsplit("//" + headers.get(b"host", b"").decode("ascii")).hostname
                allowed = {urlsplit(settings.perimetr_public_url).hostname, "127.0.0.1", "localhost", "::1"}
                if host not in allowed:
                    raise ValueError()
            except (ValueError, UnicodeError):
                return await JSONResponse({"error": {"message": "Not found"}}, status_code=404)(scope, receive, send)
        limit = get_settings().perimetr_max_backup_upload_bytes + 65536 if (path.startswith("/v1/backups/") or path.startswith("/v1/updater/") or path == "/v1/internal/updater/restore") else 16 * 1024 * 1024
        total = 0
        messages = []
        deadline = time.monotonic() + (120 if limit > 16 * 1024 * 1024 else 15)
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            # Buffer under a hard bound. This keeps malicious multipart bodies
            # from being spooled to disk before endpoint authentication.
            async with self.lock:
                while True:
                    try:
                        message = await asyncio.wait_for(receive(), timeout=max(0, min(15, deadline - time.monotonic())))
                    except TimeoutError:
                        return await JSONResponse({"error": {"message": "Request timed out"}}, status_code=408)(scope, receive, send)
                    if message["type"] == "http.disconnect":
                        return
                    total += len(message.get("body", b""))
                    if total > limit:
                        return await JSONResponse({"error": {"message": "Request body too large"}}, status_code=413)(scope, receive, send)
                    messages.append(message)
                    if not message.get("more_body", False):
                        break
                iterator = iter(messages)
                async def buffered_receive():
                    try:
                        return next(iterator)
                    except StopIteration:
                        return await receive()
                return await self.app(scope, buffered_receive, send)
        if path in {"/v1/health", "/v1/reachability"} or path.startswith("/assets/"):
            return await self.app(scope, receive, send)
        async with self.lock:
            return await self.app(scope, receive, send)
