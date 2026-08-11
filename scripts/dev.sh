#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

if [ ! -f "$PROJECT_ROOT/.env" ]; then
  echo "Missing .env. Copy .env.example to .env and review the local credentials." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not available. Install Docker Engine with Compose v2." >&2
  exit 1
fi

cd "$PROJECT_ROOT"
docker compose --env-file .env up --build "$@"

