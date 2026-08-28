#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${GROWTH_LEARNING_DIR:-/opt/apps/growth-learning}"
HEALTH_TIMEOUT_SECONDS="${DEPLOY_HEALTH_TIMEOUT_SECONDS:-240}"
INFRA_SERVICES=(postgres redis minio)
APP_SERVICES=(backend frontend)
ALL_SERVICES=("${INFRA_SERVICES[@]}" "${APP_SERVICES[@]}")

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

wait_for_services() {
  local services=("$@")
  local deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))

  while ((SECONDS < deadline)); do
    local all_healthy=true
    local service container_id state

    for service in "${services[@]}"; do
      container_id="$("${compose[@]}" ps -q "$service")"
      if [[ -z "$container_id" ]]; then
        all_healthy=false
        continue
      fi

      state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")"
      if [[ "$state" == "exited" || "$state" == "dead" ]]; then
        printf 'Service %s entered terminal state: %s\n' "$service" "$state" >&2
        "${compose[@]}" logs --tail=100 "$service" >&2
        return 1
      fi
      if [[ "$state" != "healthy" && "$state" != "running" ]]; then
        all_healthy=false
      fi
    done

    if [[ "$all_healthy" == true ]]; then
      return 0
    fi
    sleep 3
  done

  printf 'Services did not become healthy within %s seconds: %s\n' \
    "$HEALTH_TIMEOUT_SECONDS" "${services[*]}" >&2
  "${compose[@]}" ps >&2
  return 1
}

# Application images are built by CI to keep compilation and dependency
# installation away from the small production host.
commit_sha="$(git rev-parse HEAD)"
image_asset_url="${DEPLOYMENT_IMAGES_URL:-https://github.com/yunfei00/growth-learning/releases/download/deployment-${commit_sha}/growth-learning-images.tar.gz}"
image_archive="$(mktemp)"
trap 'rm -f "$image_archive"' EXIT

curl --fail --location --retry 3 --retry-delay 2 --output "$image_archive" "$image_asset_url"
gzip --decompress --stdout "$image_archive" | docker load

for image_name in growth-learning-backend:latest growth-learning-frontend:latest; do
  image_revision="$(docker image inspect "$image_name" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')"
  if [[ "$image_revision" != "$commit_sha" ]]; then
    printf 'Image revision mismatch for %s: expected %s, got %s\n' \
      "$image_name" "$commit_sha" "$image_revision" >&2
    exit 1
  fi
done

# Keep existing application containers serving while infrastructure is checked.
"${compose[@]}" up -d --no-build "${INFRA_SERVICES[@]}"
wait_for_services "${INFRA_SERVICES[@]}"

# Migrations run once, explicitly, against healthy PostgreSQL. A failure stops
# deployment before backend/frontend containers are replaced.
"${compose[@]}" run --rm --no-deps backend alembic upgrade head
"${compose[@]}" run --rm --no-deps backend alembic current
"${compose[@]}" run --rm --no-deps backend python -m app.cli.characters import-chinese-catalog
"${compose[@]}" run --rm --no-deps backend python -m app.cli.pinyin import-foundation
"${compose[@]}" run --rm --no-deps backend python -m app.cli.math import-foundation
"${compose[@]}" run --rm --no-deps backend python -m app.cli.science import-starter
"${compose[@]}" run --rm --no-deps backend python -m app.cli.review
"${compose[@]}" run --rm --no-deps backend python -m app.cli.growth rebuild-growth-events
"${compose[@]}" run --rm --no-deps backend python -m app.cli.experience rebuild-achievements
"${compose[@]}" run --rm --no-deps backend python -m app.cli.growth cleanup-exports

"${compose[@]}" up -d --no-build "${APP_SERVICES[@]}"
wait_for_services "${ALL_SERVICES[@]}"

"${compose[@]}" exec -T backend python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)"
"${compose[@]}" exec -T frontend node -e \
  "fetch('http://localhost:3000' + (process.env.NEXT_PUBLIC_APP_BASE_PATH || '') + '/login').then(r => { if (!r.ok) process.exit(1) }).catch(() => process.exit(1))"

"${compose[@]}" ps
