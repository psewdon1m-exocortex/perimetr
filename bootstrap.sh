#!/usr/bin/env sh
set -eu

REPOSITORY="psewdon1m-exocortex/perimetr"
INSTALL_DIR="${PERIMETR_INSTALL_DIR:-/opt/exocortex/perimetr}"
PERIMETR_BOOTSTRAP_RELEASE_VERSION="__PERIMETR_BOOTSTRAP_RELEASE_VERSION__"
PERIMETR_BOOTSTRAP_PUBLIC_KEY_B64="__PERIMETR_BOOTSTRAP_PUBLIC_KEY_BASE64__"

[ "$(id -u)" -eq 0 ] || { echo "Run the Perimetr bootstrap as root." >&2; exit 4; }
printf '%s' "$PERIMETR_BOOTSTRAP_RELEASE_VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || { echo "Invalid embedded Perimetr release version." >&2; exit 4; }
[ ! -f "$INSTALL_DIR/.env" ] || {
  echo "Perimetr is already prepared at $INSTALL_DIR. Use the Settings updater for an existing installation." >&2
  exit 5
}
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl openssl python3 python3-dotenv tar

temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT INT TERM
release_base="https://github.com/$REPOSITORY/releases/download/perimetr-v$PERIMETR_BOOTSTRAP_RELEASE_VERSION"
manifest_url="$release_base/perimetr-release.json"
curl -fsSL --retry 3 --retry-max-time 120 --connect-timeout 10 --max-time 180 --proto '=https' --proto-redir '=https' --max-filesize 2097152 "$manifest_url" -o "$temporary/manifest.json"

trust_file="${EXOCORTEX_RELEASE_TRUST_FILE:-/etc/exocortex/release-trust/perimetr.pem}"
curl -fsSL --proto '=https' --proto-redir '=https' --max-filesize 16384 "${manifest_url}.sig.json" -o "$temporary/manifest.sig.json"
printf '%s' "$PERIMETR_BOOTSTRAP_PUBLIC_KEY_B64" | openssl base64 -d -A >"$temporary/perimetr.pem"
openssl pkey -pubin -in "$temporary/perimetr.pem" -noout >/dev/null 2>&1 || { echo "Embedded Perimetr release key is invalid." >&2; exit 4; }
if [ -e "$trust_file" ]; then
  if [ ! -f "$trust_file" ] || [ -L "$trust_file" ] || ! cmp -s "$temporary/perimetr.pem" "$trust_file"; then
    echo "Installed Perimetr release key differs from this release." >&2
    exit 4
  fi
fi
python3 - "$temporary/manifest.json" "$temporary/manifest.sig.json" "$temporary/perimetr.pem" "$PERIMETR_BOOTSTRAP_RELEASE_VERSION" <<'PYVERIFY'
"""Verify the exact release with the public key embedded in this bootstrap."""
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

manifest, envelope, trust = map(Path, sys.argv[1:4])
expected_version = sys.argv[4]
if manifest.stat().st_size > 2 * 1024 * 1024 or envelope.stat().st_size > 16384 or trust.stat().st_size > 16384:
    raise SystemExit("Release signature input exceeds limit")
signed = json.loads(envelope.read_text(encoding="utf8"))
if signed.get("schema") != "exocortex.release-signature.v1" or signed.get("algorithm") != "RSA-PSS-SHA256":
    raise SystemExit("Unsupported release signature")
public = subprocess.run(["openssl", "pkey", "-pubin", "-in", str(trust), "-outform", "DER"], check=True, capture_output=True).stdout
if hashlib.sha256(public).hexdigest() != signed.get("key_id"):
    raise SystemExit("Release signer is not trusted")
description = subprocess.run(["openssl", "rsa", "-pubin", "-in", str(trust), "-text", "-noout"], check=True, capture_output=True, text=True).stdout
bits = re.search(r"Public-Key: \((\d+) bit\)", description)
if not bits or int(bits[1]) < 3072:
    raise SystemExit("Release trust requires RSA with at least 3072 bits")
with tempfile.TemporaryDirectory(prefix="exocortex-signature-") as temporary:
    signature = Path(temporary) / "signature.bin"
    signature.write_bytes(base64.b64decode(signed["signature"], validate=True))
    subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(trust), "-signature", str(signature), "-sigopt", "rsa_padding_mode:pss", "-sigopt", "rsa_pss_saltlen:32", str(manifest)], check=True)
data = json.loads(manifest.read_text(encoding="utf8"))
if data.get("service") != "perimetr" or data.get("version") != expected_version:
    raise SystemExit("Perimetr release identity mismatch")
PYVERIFY
install -d -o root -g root -m 0755 "$(dirname "$trust_file")"
[ -f "$trust_file" ] || install -o root -g root -m 0644 "$temporary/perimetr.pem" "$trust_file"

fields=$(python3 - "$temporary/manifest.json" <<'PY'
import json, re, sys
from urllib.parse import urlparse
with open(sys.argv[1], encoding="utf-8") as handle:
    manifest = json.load(handle)
bundle = manifest.get("compose_bundle") or {}
image = manifest.get("image") or {}
version = str(manifest.get("version") or "")
url = str(bundle.get("url") or "")
checksum = str(bundle.get("sha256") or "").removeprefix("sha256:").lower()
reference = str(image.get("reference") or "")
digest = str(image.get("digest") or "")
parsed = urlparse(url)
if manifest.get("schema_version") != 1 or manifest.get("service") != "perimetr":
    raise SystemExit("Invalid Perimetr release manifest identity.")
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    raise SystemExit("Invalid Perimetr release version.")
if parsed.scheme != "https" or parsed.hostname != "github.com":
    raise SystemExit("Perimetr bundle must be downloaded from GitHub over HTTPS.")
if not re.fullmatch(r"[a-f0-9]{64}", checksum):
    raise SystemExit("Invalid Perimetr bundle checksum.")
if not reference.startswith("ghcr.io/") or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
    raise SystemExit("Invalid immutable Perimetr image reference.")
print(version)
print(url)
print(checksum)
print(reference + "@" + digest)
PY
)
version=$(printf '%s\n' "$fields" | sed -n '1p')
[ "$version" = "$PERIMETR_BOOTSTRAP_RELEASE_VERSION" ] || { echo "Perimetr release identity mismatch." >&2; exit 4; }
bundle_url=$(printf '%s\n' "$fields" | sed -n '2p')
bundle_sha=$(printf '%s\n' "$fields" | sed -n '3p')
image=$(printf '%s\n' "$fields" | sed -n '4p')

curl -fsSL --retry 3 --retry-max-time 120 --connect-timeout 10 --max-time 180 --proto '=https' --proto-redir '=https' --max-filesize 268435456 "$bundle_url" -o "$temporary/perimetr.tar.gz"
printf '%s  %s\n' "$bundle_sha" "$temporary/perimetr.tar.gz" | sha256sum -c -
mkdir -p "$temporary/stage" "$INSTALL_DIR"
python3 - "$temporary/perimetr.tar.gz" "$temporary/stage" <<'PYEXTRACT'
import pathlib, sys, tarfile
root = pathlib.Path(sys.argv[2]).resolve()
seen, expanded = set(), 0
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    for member in archive:
        name = pathlib.PurePosixPath(member.name)
        if name.is_absolute() or '..' in name.parts or '\\' in member.name or ':' in member.name:
            raise SystemExit('Unsafe release path')
        normalized = str(name)
        if normalized in seen or len(seen) >= 1024 or not (member.isfile() or member.isdir()):
            raise SystemExit('Duplicate, linked or unsupported release member')
        seen.add(normalized)
        expanded += member.size
        if member.size > 128*1024*1024 or expanded > 384*1024*1024:
            raise SystemExit('Release extraction budget exceeded')
        if normalized == '.':
            continue
        if name.parts[0] not in {'.env.example', 'compose.production.yaml', 'install.sh', 'scripts', 'updater', 'nginx.security.conf'}:
            raise SystemExit('Unexpected release member')
        target = root.joinpath(*name.parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open('xb') as output:
                while chunk := source.read(65536): output.write(chunk)
            target.chmod(0o755 if normalized.endswith('.sh') or normalized.endswith('updater-linux-amd64') else 0o644)
PYEXTRACT
cp -a "$temporary/stage/." "$INSTALL_DIR/"
chown -R root:root "$INSTALL_DIR"
chmod 0755 "$INSTALL_DIR/install.sh"
PERIMETR_RELEASE_VERSION="$version" PERIMETR_RELEASE_IMAGE="$image" \
  "$INSTALL_DIR/install.sh" prepare
