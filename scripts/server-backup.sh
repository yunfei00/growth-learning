#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${GROWTH_LEARNING_DIR:-/opt/apps/growth-learning}"
BACKUP_ROOT="${GROWTH_LEARNING_BACKUP_ROOT:-/opt/backups/growth-learning}"
RETENTION="${GROWTH_LEARNING_BACKUP_RETENTION_DAYS:-${GROWTH_LEARNING_BACKUP_RETENTION:-7}}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${BACKUP_ROOT}/${timestamp}"

if [[ ! "$RETENTION" =~ ^[1-9][0-9]*$ ]]; then
  printf 'Backup retention must be a positive integer.\n' >&2
  exit 1
fi
resolved_backup_root="$(readlink -m "$BACKUP_ROOT")"
if [[ "$resolved_backup_root" != "/opt/backups/growth-learning" ]]; then
  printf 'Refusing backup root outside /opt/backups/growth-learning.\n' >&2
  exit 1
fi
BACKUP_ROOT="$resolved_backup_root"

cd "$APP_DIR"
compose=(docker compose --env-file .env)
"${compose[@]}" config --quiet
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

"${compose[@]}" exec -T postgres sh -c \
  'pg_dump --format=custom --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  >"${backup_dir}/postgres.dump"
test -s "${backup_dir}/postgres.dump"

"${compose[@]}" exec -T backend python - <<'PY' >"${backup_dir}/object-storage-manifest.json"
import json
from app.core.config import get_settings
from app.integrations.object_storage import build_minio_client

settings = get_settings()
client = build_minio_client(settings)
objects = [
    {"object_key": item.object_name, "size_bytes": item.size, "etag": item.etag}
    for item in client.list_objects(settings.minio_bucket, recursive=True)
]
print(json.dumps({"bucket": settings.minio_bucket, "objects": objects}, sort_keys=True))
PY

db_sha="$(sha256sum "${backup_dir}/postgres.dump" | awk '{print $1}')"
objects_sha="$(sha256sum "${backup_dir}/object-storage-manifest.json" | awk '{print $1}')"
commit_sha="$(git rev-parse HEAD)"
"${compose[@]}" ps >"${backup_dir}/service-status.txt"
services_sha="$(sha256sum "${backup_dir}/service-status.txt" | awk '{print $1}')"
cat >"${backup_dir}/manifest.json" <<EOF
{
  "format": "growth-learning-backup-v1",
  "created_at": "${timestamp}",
  "git_commit": "${commit_sha}",
  "postgres_dump": {"path": "postgres.dump", "sha256": "${db_sha}"},
  "object_storage_manifest": {"path": "object-storage-manifest.json", "sha256": "${objects_sha}"},
  "service_status": {"path": "service-status.txt", "sha256": "${services_sha}"},
  "object_storage_note": "Media objects remain in the private MinIO volume; copy that volume or mirror the listed objects before disaster recovery."
}
EOF
chmod 600 "${backup_dir}"/*
(
  cd "$backup_dir"
  sha256sum postgres.dump object-storage-manifest.json service-status.txt manifest.json >checksums.sha256
)
chmod 600 "${backup_dir}/checksums.sha256"

mapfile -t backups < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*T*Z' -printf '%f\n' | sort)
if ((${#backups[@]} > RETENTION)); then
  remove_count=$((${#backups[@]} - RETENTION))
  for ((index = 0; index < remove_count; index++)); do
    candidate="${BACKUP_ROOT}/${backups[$index]}"
    resolved_candidate="$(readlink -m "$candidate")"
    if [[ "$resolved_candidate" =~ ^/opt/backups/growth-learning/[0-9]{8}T[0-9]{6}Z$ ]]; then
      rm -rf -- "$resolved_candidate"
    fi
  done
fi

printf 'Growth Learning backup completed: %s\n' "$backup_dir"
"${compose[@]}" ps
