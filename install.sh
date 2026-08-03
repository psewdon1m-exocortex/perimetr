#!/usr/bin/env sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer as root." >&2
  exit 1
fi

install_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
cd "$install_dir"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created $install_dir/.env. Configure it, then run this installer again." >&2
  exit 2
fi

./updater/install.sh perimetr "$install_dir/.env" "$install_dir/updater/updater-linux-amd64"
docker compose --env-file .env -f compose.production.yaml up -d
echo "Perimetr and the local updater are running on the loopback listener."
echo "Expose Perimetr through the shared host Nginx after configuring its SNI."
