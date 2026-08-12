#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${GROWTH_LEARNING_DIR:-/opt/apps/growth-learning}"
REPOSITORY_URL="${GROWTH_LEARNING_REPOSITORY_URL:-https://github.com/yunfei00/growth-learning.git}"
BASHRC_PATH="${GROWTH_LEARNING_BASHRC:-/root/.bashrc}"
MANAGED_START="# >>> growth-learning managed >>>"
MANAGED_END="# <<< growth-learning managed <<<"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Required command is missing: %s\n' "$1" >&2
    exit 1
  fi
}

set_env_value() {
  local key="$1"
  local value="$2"
  local escaped
  escaped="$(printf '%s' "$value" | sed 's/[&|]/\\&/g')"

  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*$|${key}=${escaped}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >>.env
  fi
}

require_command git
require_command docker
require_command openssl
require_command sed
require_command awk

docker compose version >/dev/null
docker info >/dev/null

if [[ ! -d "$APP_DIR/.git" ]]; then
  if [[ -e "$APP_DIR" && -n "$(ls -A "$APP_DIR" 2>/dev/null)" ]]; then
    printf 'Deployment path exists and is not an empty Git repository: %s\n' "$APP_DIR" >&2
    exit 1
  fi

  mkdir -p "$(dirname "$APP_DIR")"
  git clone "$REPOSITORY_URL" "$APP_DIR"
fi

cd "$APP_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  set_env_value POSTGRES_PASSWORD "$(openssl rand -hex 24)"
  set_env_value MINIO_ROOT_PASSWORD "$(openssl rand -hex 24)"
  chmod 600 .env
  printf 'Created %s/.env with generated service credentials.\n' "$APP_DIR"
else
  printf 'Preserved existing %s/.env.\n' "$APP_DIR"
fi

if ! grep -q '^AUTH_SECRET=.' .env; then
  set_env_value AUTH_SECRET "$(openssl rand -hex 32)"
fi

if [[ -n "${GROWTH_LEARNING_PUBLIC_FRONTEND_ORIGIN:-}" ]]; then
  set_env_value CORS_ORIGINS "$GROWTH_LEARNING_PUBLIC_FRONTEND_ORIGIN"
fi

if [[ -n "${GROWTH_LEARNING_PUBLIC_API_BASE_URL:-}" ]]; then
  set_env_value PUBLIC_API_BASE_URL "$GROWTH_LEARNING_PUBLIC_API_BASE_URL"
fi

if [[ -n "${GROWTH_LEARNING_PUBLIC_APP_BASE_PATH:-}" ]]; then
  set_env_value PUBLIC_APP_BASE_PATH "$GROWTH_LEARNING_PUBLIC_APP_BASE_PATH"
fi

if [[ -n "${GROWTH_LEARNING_API_ROOT_PATH:-}" ]]; then
  set_env_value API_ROOT_PATH "$GROWTH_LEARNING_API_ROOT_PATH"
fi

if [[ -n "${GROWTH_LEARNING_AUTH_COOKIE_PATH:-}" ]]; then
  set_env_value AUTH_COOKIE_PATH "$GROWTH_LEARNING_AUTH_COOKIE_PATH"
fi

if [[ -n "${GROWTH_LEARNING_AUTH_COOKIE_SECURE:-}" ]]; then
  set_env_value AUTH_COOKIE_SECURE "$GROWTH_LEARNING_AUTH_COOKIE_SECURE"
fi

if [[ -n "${GROWTH_LEARNING_BIND_ADDRESS:-}" ]]; then
  set_env_value BACKEND_BIND_ADDRESS "$GROWTH_LEARNING_BIND_ADDRESS"
  set_env_value FRONTEND_BIND_ADDRESS "$GROWTH_LEARNING_BIND_ADDRESS"
fi

touch "$BASHRC_PATH"
temporary_bashrc="$(mktemp)"
trap 'rm -f "$temporary_bashrc"' EXIT

awk -v start="$MANAGED_START" -v end="$MANAGED_END" '
  $0 == start { managed = 1; next }
  $0 == end { managed = 0; next }
  !managed { print }
' "$BASHRC_PATH" >"$temporary_bashrc"

{
  printf '\n%s\n' "$MANAGED_START"
  printf 'export GROWTH_LEARNING_DIR=%q\n' "$APP_DIR"
  printf 'if [ -f "%s/scripts/server-functions.sh" ]; then\n' "$APP_DIR"
  printf '  . "%s/scripts/server-functions.sh"\n' "$APP_DIR"
  printf 'fi\n'
  printf '%s\n' "$MANAGED_END"
} >>"$temporary_bashrc"

cp "$temporary_bashrc" "$BASHRC_PATH"
printf 'Installed Growth Learning shell commands in %s.\n' "$BASHRC_PATH"
printf 'Run: source %s\n' "$BASHRC_PATH"
