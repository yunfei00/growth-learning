#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${GROWTH_LEARNING_DIR:-/opt/apps/growth-learning}"

for command_name in docker git gzip mktemp; do
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

commit_sha="$(git rev-parse HEAD)"
app_version="${APP_VERSION:-1.0.0}"
image_archive="$(mktemp --suffix=.tar.gz)"
trap 'rm -f "$image_archive"' EXIT

printf 'Building Growth Learning %s (%s) on %s\n' \
  "$app_version" "$commit_sha" "$(hostname)"

APP_VERSION="$app_version" APP_REVISION="$commit_sha" \
  docker compose --env-file .env build backend frontend

for image_name in growth-learning-backend:latest growth-learning-frontend:latest; do
  image_revision="$(
    docker image inspect "$image_name" \
      --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
  )"
  if [[ "$image_revision" != "$commit_sha" ]]; then
    printf 'Image revision mismatch for %s: expected %s, got %s\n' \
      "$image_name" "$commit_sha" "$image_revision" >&2
    exit 1
  fi
done

docker save growth-learning-backend:latest growth-learning-frontend:latest \
  | gzip --stdout >"$image_archive"

DEPLOYMENT_IMAGES_URL="file://$image_archive" \
  GROWTH_LEARNING_DIR="$APP_DIR" \
  bash scripts/server-deploy.sh
