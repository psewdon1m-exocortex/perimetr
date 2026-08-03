from __future__ import annotations

import json
import re
from typing import Any, Callable
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


def _version(value: str) -> tuple[int, int, int, str] | None:
    match = SEMVER.fullmatch(str(value or "").strip())
    if not match:
        return None
    return int(match[1]), int(match[2]), int(match[3]), match[4] or ""


def _newer(candidate: str, current: str) -> bool:
    left = _version(candidate)
    right = _version(current)
    if not left or not right:
        return False
    if left[:3] != right[:3]:
        return left[:3] > right[:3]
    if not left[3]:
        return bool(right[3])
    if not right[3]:
        return False
    return left[3] > right[3]


def _repository_coordinates(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise ValueError("Updater currently supports HTTPS GitHub repositories")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise ValueError("Repository URL must identify a GitHub owner and repository")
    return parts[0], re.sub(r"\.git$", "", parts[1], flags=re.IGNORECASE)


def check_github_release(
    *,
    repository_url: str,
    service: str,
    current_version: str,
    timeout_seconds: float,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    owner, repository = _repository_coordinates(repository_url)
    request = Request(
        f"https://api.github.com/repos/{quote(owner)}/{quote(repository)}/releases?per_page=100",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"exocortex-{service}-updater",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        method="GET",
    )
    with opener(request, timeout=timeout_seconds) as response:
        body = response.read(2 * 1024 * 1024 + 1)
    if len(body) > 2 * 1024 * 1024:
        raise ValueError("GitHub releases response exceeds 2 MB")
    releases = json.loads(body.decode("utf-8"))
    if not isinstance(releases, list):
        raise ValueError("GitHub returned an invalid releases response")

    prefix = f"{service}-v"
    candidates = [
        item for item in releases
        if not item.get("draft") and str(item.get("tag_name") or "").lower().startswith(prefix)
    ]
    if not candidates:
        candidates = [
            item for item in releases
            if not item.get("draft") and re.match(r"^v\d+\.\d+\.\d+", str(item.get("tag_name") or ""))
        ]

    parsed: list[tuple[str, dict[str, Any]]] = []
    for release in candidates:
        tag = str(release.get("tag_name") or "")
        version = tag[len(prefix):] if tag.lower().startswith(prefix) else tag.removeprefix("v")
        if _version(version):
            parsed.append((version, release))
    available = None
    for candidate in parsed:
        if available is None or _newer(candidate[0], available[0]):
            available = candidate
    return {
        "service": service,
        "repository_url": repository_url,
        "installed_version": current_version,
        "available_version": available[0] if available else None,
        "update_available": _newer(available[0], current_version) if available else False,
        "tag": available[1].get("tag_name") if available else None,
        "release_url": available[1].get("html_url") if available else None,
        "published_at": available[1].get("published_at") if available else None,
        "prerelease": bool(available and available[1].get("prerelease")),
        "apply_via": "updater",
        "backup_required": True,
    }
