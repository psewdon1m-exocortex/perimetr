#!/usr/bin/env sh
set -eu

ACTION="${1:-install}"
INSTALL_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
ENV_FILE="$INSTALL_DIR/.env"

require_root() {
  [ "$(id -u)" -eq 0 ] || { echo "Run perimetr-install as root." >&2; exit 4; }
}

get_env_from() {
  python3 "$INSTALL_DIR/scripts/installer-env.py" get "$1" "$2"
}

get_env() {
  get_env_from "$ENV_FILE" "$1"
}

set_env() {
  python3 "$INSTALL_DIR/scripts/installer-env.py" set "$ENV_FILE" "$1" "$2"
}

needs_generation() {
  current=$(get_env "$1")
  [ -z "$current" ] || [ "$current" = "CHANGE_ME" ] ||
    case "$current" in replace-*) true ;; *) false ;; esac
}

random_hex() {
  openssl rand -hex "$1"
}

install_command() {
  install -d -m 0755 /usr/local/sbin
  wrapper=/usr/local/sbin/perimetr-install
  {
    echo '#!/usr/bin/env sh'
    printf 'exec "%s/install.sh" "$@"\n' "$INSTALL_DIR"
  } >"$wrapper"
  chmod 0755 "$wrapper"
}

prepare() {
  require_root
  command -v openssl >/dev/null 2>&1 || {
    echo "openssl is required. Prepare the VPS with Sindri first." >&2
    exit 3
  }
  if [ ! -f "$ENV_FILE" ]; then
    cp "$INSTALL_DIR/.env.example" "$ENV_FILE"
  fi
  [ ! -L "$ENV_FILE" ] || { echo "Refusing a symlink environment." >&2; exit 2; }
  chmod 0600 "$ENV_FILE"
  needs_generation PERIMETR_POSTGRES_PASSWORD && set_env PERIMETR_POSTGRES_PASSWORD "$(random_hex 32)"
  database_password=$(get_env PERIMETR_POSTGRES_PASSWORD)
  set_env PERIMETR_DATABASE_URL "postgresql://perimetr:${database_password}@perimetr-db:5432/perimetr"
  needs_generation PERIMETR_POD_SIGNING_SECRET && set_env PERIMETR_POD_SIGNING_SECRET "$(random_hex 32)"
  needs_generation UPDATER_CONTROL_TOKEN && set_env UPDATER_CONTROL_TOKEN "$(random_hex 32)"
  set_env UPDATER_COMPOSE_PROJECT_DIR "$INSTALL_DIR"
  if [ -n "${PERIMETR_RELEASE_VERSION:-}" ]; then
    set_env PERIMETR_VERSION "$PERIMETR_RELEASE_VERSION"
  fi
  if [ -n "${PERIMETR_RELEASE_IMAGE:-}" ]; then
    set_env PERIMETR_IMAGE "$PERIMETR_RELEASE_IMAGE"
  fi
  install_command
  echo "Perimetr files are prepared in $INSTALL_DIR"
  echo "Edit only the OPERATOR INPUT section in $ENV_FILE"
  echo "Then run: sudo perimetr-install"
}

validate_install() {
  [ -f "$ENV_FILE" ] && [ ! -L "$ENV_FILE" ] || { echo "Run the Perimetr bootstrap command first." >&2; exit 2; }
  [ "$(stat -c %u "$ENV_FILE")" = 0 ] && [ "$(stat -c %a "$ENV_FILE")" = 600 ] || { echo "Perimetr .env must be root-owned with mode 0600." >&2; exit 2; }
  for command in docker curl openssl; do
    command -v "$command" >/dev/null 2>&1 || {
      echo "$command is required. Prepare the VPS with Sindri first." >&2
      exit 3
    }
  done
  docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required." >&2; exit 3; }
  public_url=$(get_env PERIMETR_PUBLIC_URL)
  kernel_url=$(get_env KERNEL_URL)
  kernel_token=$(get_env KERNEL_SERVICE_TOKEN)
  image=$(get_env PERIMETR_IMAGE)
  case "$public_url" in https://*.*) ;; *) echo "PERIMETR_PUBLIC_URL must be the public HTTPS URL." >&2; exit 2 ;; esac
  case "$public_url" in *CHANGE_ME*|*.example.com*) echo "Replace the example PERIMETR_PUBLIC_URL." >&2; exit 2 ;; esac
  case "$kernel_url" in https://*.*) ;; *) echo "KERNEL_URL must be the public HTTPS Kernel URL." >&2; exit 2 ;; esac
  case "$kernel_url" in *CHANGE_ME*|*.example.com*) echo "Replace the example KERNEL_URL." >&2; exit 2 ;; esac
  [ "${#kernel_token}" -ge 24 ] || { echo "Set the dedicated Kernel service credential in .env." >&2; exit 2; }
  printf '%s' "$image" | grep -Eq '^ghcr\.io/.+@sha256:[a-f0-9]{64}$' || {
    echo "PERIMETR_IMAGE was not populated from a valid release." >&2
    exit 2
  }
  docker pull "$image" >/dev/null || {
    echo "Cannot pull the Perimetr image. Make the GHCR package public or authenticate Docker to ghcr.io." >&2
    exit 14
  }
  database_password=$(get_env PERIMETR_POSTGRES_PASSWORD)
  set_env PERIMETR_DATABASE_URL "postgresql://perimetr:${database_password}@perimetr-db:5432/perimetr"
  set_env UPDATER_PUBLIC_HEALTH_URL ""
  # Hash before Compose parses the environment: the initial key is exact text,
  # including dollar signs and newlines. The database wins after initialization.
  python3 "$INSTALL_DIR/scripts/installer-env.py" seed "$ENV_FILE"
}

install_perimetr() {
  require_root
  validate_install
  cd "$INSTALL_DIR"
  "$INSTALL_DIR/updater/install.sh" perimetr "$ENV_FILE" "$INSTALL_DIR/updater/updater-linux-amd64"
  docker compose --env-file "$ENV_FILE" -f compose.production.yaml config -q
  docker compose --env-file "$ENV_FILE" -f compose.production.yaml run --rm --no-deps perimetr-api python -m app.install_validation
  docker compose --env-file "$ENV_FILE" -f compose.production.yaml up -d
  port=$(get_env PERIMETR_LISTEN_PORT)
  port=${port:-18080}
  for _ in $(seq 1 45); do
    if curl -fsS --max-time 3 "http://127.0.0.1:$port/v1/health" | python3 -c 'import json,sys; result=json.load(sys.stdin); sys.exit(0 if result.get("status")=="ok" and result.get("version")==sys.argv[1] else 1)' "$(get_env PERIMETR_VERSION)"; then
      echo "Perimetr is healthy at $(get_env PERIMETR_PUBLIC_URL)"
      return 0
    fi
    sleep 2
  done
  docker compose --env-file "$ENV_FILE" -f compose.production.yaml ps >&2
  echo "Perimetr did not become healthy within 90 seconds." >&2
  exit 15
}

case "$ACTION" in
  prepare) prepare ;;
  install) install_perimetr ;;
  status)
    require_root
    cd "$INSTALL_DIR"
    docker compose --env-file "$ENV_FILE" -f compose.production.yaml ps
    ;;
  sync-kernel)
    require_root
    cd "$INSTALL_DIR"
    docker compose --env-file "$ENV_FILE" -f compose.production.yaml exec -T perimetr-api python -m app.kernel_connection export-for-installer | python3 "$INSTALL_DIR/scripts/sync-kernel-env.py" "$ENV_FILE"
    docker compose --env-file "$ENV_FILE" -f compose.production.yaml exec -T perimetr-api python -m app.kernel_connection synced
    echo "The host Updater will read the synchronized Kernel connection on its next request."
    ;;
  *) echo "Usage: perimetr-install [install|prepare|status|sync-kernel]" >&2; exit 2 ;;
esac
