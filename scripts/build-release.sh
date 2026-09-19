#!/usr/bin/env bash
set -euo pipefail

version="${1:?version is required}"
output="${2:-release-artifacts}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repository="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
image_reference="${IMAGE_REFERENCE:?IMAGE_REFERENCE is required}"
image_digest="${IMAGE_DIGEST:?IMAGE_DIGEST is required}"
updater_dir="${UPDATER_BUNDLE_DIR:?UPDATER_BUNDLE_DIR is required}"
updater_version="$(cat "$root/.release/updater.version")"

[[ "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ && "$version" != 0.0.0 ]] || exit 2
[[ "$version" == "$(cat "$root/VERSION")" ]] || exit 2
[[ "$image_digest" =~ ^sha256:[a-f0-9]{64}$ ]] || exit 2
[[ "$image_reference" =~ ^ghcr.io/[a-z0-9_./-]+$ ]] || exit 2
[[ "$repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || exit 2
python "$root/scripts/release-inputs.py" --validate-only
[[ -f "$updater_dir/install.sh" && -f "$updater_dir/updater-linux-amd64" ]] || {
  echo "Verified Updater install bundle is incomplete" >&2
  exit 3
}
[[ -s "$root/pod-runtime/pod.exe" ]] || {
  echo "A verified Pod release must be staged at pod-runtime/pod.exe" >&2
  exit 4
}
[[ -s "$root/pod-runtime/pod-update-public-key.pem" ]] || {
  echo "The verified Pod update public key must be staged with the factory runtime" >&2
  exit 4
}

mkdir -p "$root/$output"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
cp "$root/compose.production.yaml" "$root/.env.example" \
  "$root/install.sh" "$root/nginx.security.conf" "$stage/"
mkdir "$stage/scripts"
cp "$root/scripts/installer-env.py" "$root/scripts/sync-kernel-env.py" "$stage/scripts/"
cp -R "$updater_dir" "$stage/updater"
find "$stage/updater" -type f -name '*.sh' -exec chmod 0755 {} +
chmod 0755 "$stage/install.sh" "$stage/updater/updater-linux-amd64"
sed -i \
  -e "s|^PERIMETR_VERSION=.*|PERIMETR_VERSION=$version|" \
  -e "s|^PERIMETR_IMAGE=.*|PERIMETR_IMAGE=${image_reference}@${image_digest}|" \
  "$stage/.env.example"

bundle="$root/$output/perimetr-${version}-compose.tar.gz"
tar -czf "$bundle" -C "$stage" .
bundle_sha="$(sha256sum "$bundle" | awk '{print $1}')"
database_revision="$(cd "$root" && python -m alembic -c alembic.ini heads | awk 'NR == 1 { print $1 }')"
[[ "$database_revision" =~ ^[0-9]+$ ]] || {
  echo "Perimetr Alembic head must be numeric, got: $database_revision" >&2
  exit 5
}
database_schema=$((10#$database_revision))
cat > "$root/$output/perimetr-release.json" <<EOF
{
  "schema_version": 1,
  "service": "perimetr",
  "version": "$version",
  "channel": "stable",
  "image": {
    "reference": "$image_reference",
    "digest": "$image_digest"
  },
  "compose_bundle": {
    "url": "https://github.com/${repository}/releases/download/perimetr-v${version}/perimetr-${version}-compose.tar.gz",
    "sha256": "$bundle_sha"
  },
  "minimum_updater_version": "$updater_version",
  "database_schema": $database_schema,
  "release_notes_url": "https://github.com/${repository}/releases/tag/perimetr-v${version}"
}
EOF
