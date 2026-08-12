#!/usr/bin/env bash

# Shell helpers installed by server-bootstrap.sh. Keep every command scoped to
# the Growth Learning Compose project and preserve named volumes on stop.

_growth_learning_dir() {
  printf '%s\n' "${GROWTH_LEARNING_DIR:-/opt/apps/growth-learning}"
}

_growth_learning_compose() (
  set -Eeuo pipefail
  cd "$(_growth_learning_dir)"
  docker compose --env-file .env "$@"
)

gl-start() {
  _growth_learning_compose up -d --no-build
}

gl-stop() {
  _growth_learning_compose down
}

gl-restart() {
  _growth_learning_compose down
  _growth_learning_compose up -d --no-build
}

gl-status() {
  _growth_learning_compose ps
}

gl-logs() {
  _growth_learning_compose logs -f --tail=200 "$@"
}

gl-update() (
  set -Eeuo pipefail
  cd "$(_growth_learning_dir)"
  if [[ -n "$(git status --porcelain)" ]]; then
    printf 'Refusing to update a dirty deployment checkout. Review git status first.\n' >&2
    exit 1
  fi
  git pull --ff-only origin main
  bash scripts/server-deploy.sh
)
