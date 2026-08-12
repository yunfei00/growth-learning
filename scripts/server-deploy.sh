#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${GROWTH_LEARNING_DIR:-/opt/apps/growth-learning}"
HEALTH_TIMEOUT_SECONDS="${DEPLOY_HEALTH_TIMEOUT_SECONDS:-240}"
SERVICES=(postgres redis minio backend frontend)

for command_name in curl docker git gzip; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Required command is missing: %s\n' "$command_name" >&2
    exit 1
  fi
done

cd "$APP_DIR"

if [[ ! -f .env ]]; then
  printf 'Missing %s/.env. Run scripts/server-bootstrap.sh first.\n' "$APP_DIR" >&2
  exit 1
fi

compose=(docker compose --env-file .env)

"${compose[@]}" config --quiet

# The frontend production image is built on GitHub's Linux runner so this small
# server never has to run the memory-intensive Next.js compiler.
commit_sha="$(git rev-parse HEAD)"
frontend_asset_url="${FRONTEND_IMAGE_URL:-https://github.com/yunfei00/growth-learning/releases/download/deployment-${commit_sha}/growth-learning-frontend.tar.gz}"
frontend_archive="$(mktemp)"
trap 'rm -f "$frontend_archive"' EXIT

curl --fail --location --retry 3 --retry-delay 2 --output "$frontend_archive" "$frontend_asset_url"
gzip --decompress --stdout "$frontend_archive" | docker load

frontend_revision="$(docker image inspect growth-learning-frontend:latest --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')"
if [[ "$frontend_revision" != "$commit_sha" ]]; then
  printf 'Frontend image revision mismatch: expected %s, got %s\n' "$commit_sha" "$frontend_revision" >&2
  exit 1
fi

"${compose[@]}" build backend
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
