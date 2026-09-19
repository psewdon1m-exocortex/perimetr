#!/usr/bin/env python3
"""Verify exact-tag Perimetr assets anonymously before promoting the prerelease."""
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
assets = Path(sys.argv[1]).resolve()
manifest = json.loads((assets / "perimetr-release.json").read_bytes())
version = manifest["version"]
tag = "perimetr-v" + version
assert manifest["service"] == "perimetr" and re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version) and version != "0.0.0"
base = f"https://github.com/psewdon1m-exocortex/perimetr/releases/download/{tag}"
core_names = [
    "perimetr-release.json",
    "perimetr-release.json.sig.json",
    "perimetr.pem",
    "bootstrap.sh",
    f"perimetr-{version}-compose.tar.gz",
]
names = core_names
with tempfile.TemporaryDirectory() as directory:
    downloaded = Path(directory)
    metadata = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                f"https://api.github.com/repos/psewdon1m-exocortex/perimetr/releases/tags/{tag}",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "perimetr-release-verifier"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                metadata = json.load(response)
            if {item["name"] for item in metadata["assets"]} == set(names):
                break
        except Exception:
            if attempt == 2:
                raise
        if attempt == 2:
            raise AssertionError("Published release asset inventory differs from the signed candidate")
        time.sleep(min(2 ** attempt, 20))
    for name in names:
        data = None
        for attempt in range(3):
            try:
                request = urllib.request.Request(base + "/" + name, headers={"User-Agent": "perimetr-release-verifier"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    data = response.read(268435457)
                if len(data) > 268435456:
                    raise ValueError("Asset exceeds limit")
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(min(2 ** attempt, 20))
        assert data is not None
        assert hashlib.sha256(data).digest() == hashlib.sha256((assets / name).read_bytes()).digest(), name + " differs externally"
        (downloaded / name).write_bytes(data)
    subprocess.run([
        sys.executable,
        str(root / "scripts/verify-release-manifest.py"),
        str(downloaded / "perimetr-release.json"),
        str(downloaded / "perimetr-release.json.sig.json"),
        str(assets / "perimetr.pem"),
    ], check=True)
    bootstrap = (downloaded / "bootstrap.sh").read_text(encoding="utf-8")
    assert "PRIVATE KEY" not in bootstrap and "__PERIMETR_BOOTSTRAP_" not in bootstrap
    assert f'PERIMETR_BOOTSTRAP_RELEASE_VERSION="{version}"' in bootstrap
    embedded = base64.b64decode(re.search(r'PERIMETR_BOOTSTRAP_PUBLIC_KEY_B64="([^"]+)"', bootstrap)[1], validate=True)
    assert embedded == (assets / "perimetr.pem").read_bytes()
    bundle_name = f"perimetr-{version}-compose.tar.gz"
    assert hashlib.sha256((downloaded / bundle_name).read_bytes()).hexdigest() == manifest["compose_bundle"]["sha256"]
    remote = subprocess.check_output([
        "git", "ls-remote", "--exit-code", "origin", "refs/tags/" + tag, "refs/tags/" + tag + "^{}",
    ], cwd=root, text=True)
    hashes = [line.split()[0] for line in remote.splitlines()]
    local = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    assert hashes and hashes[-1] == local, "Published tag points to a different commit"
print(json.dumps({"result": "PASS", "tag": tag, "assets": names, "anonymous": True, "embedded_public_trust": True, "revision": local}))
