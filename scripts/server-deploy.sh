#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${GROWTH_LEARNING_DIR:-/opt/apps/growth-learning}"
HEALTH_TIMEOUT_SECONDS="${DEPLOY_HEALTH_TIMEOUT_SECONDS:-240}"
COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"
SERVICES=(postgres redis minio backend frontend)

cd "$APP_DIR"

if [[ ! -f .env ]]; then
  printf 'Missing %s/.env. Run scripts/server-bootstrap.sh first.\n' "$APP_DIR" >&2
  exit 1
fi

compose=(docker compose --env-file .env)

"${compose[@]}" config --quiet

# Build sequentially on small servers, then start without an implicit second build.
COMPOSE_PARALLEL_LIMIT="$COMPOSE_PARALLEL_LIMIT" "${compose[@]}" build backend frontend
"${compose[@]}" up -d --no-build --remove-orphans

deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))
while ((SECONDS < deadline)); do
  all_healthy=true

  for service in "${SERVICES[@]}"; do
    container_id="$("${compose[@]}" ps -q "$service")"
    if [[ -z "$container_id" ]]; then
      all_healthy=false
      continue
    fi

    state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")"
    if [[ "$state" == "exited" || "$state" == "dead" ]]; then
      printf 'Service %s entered terminal state: %s\n' "$service" "$state" >&2
      "${compose[@]}" logs --tail=100 "$service" >&2
      exit 1
    fi
    if [[ "$state" != "healthy" && "$state" != "running" ]]; then
      all_healthy=false
    fi
  done

  if [[ "$all_healthy" == true ]]; then
    "${compose[@]}" ps
    exit 0
  fi

  sleep 3
done

printf 'Services did not become healthy within %s seconds.\n' "$HEALTH_TIMEOUT_SECONDS" >&2
"${compose[@]}" ps >&2
"${compose[@]}" logs --tail=100 >&2
exit 1
