# Local infrastructure

The root `docker-compose.yml` is the source of truth for the Phase 1 local stack.

| Service | Image/runtime | Persistent volume | Health signal |
| --- | --- | --- | --- |
| PostgreSQL | `postgres:18.3-alpine` | `postgres_data` | `pg_isready` |
| Redis | `redis:8.10.0-alpine` | `redis_data` | `redis-cli ping` |
| MinIO | pinned release image | `minio_data` | MinIO live endpoint |
| Backend | repository Dockerfile | none | `GET /health` |
| Frontend | repository Dockerfile | dependency/build caches only | `GET /status` |

All services share the private `growth_learning` bridge network. Only developer-facing ports are published. Credentials and port overrides come from the untracked root `.env` file.

The Phase 1 backend does not create a bucket at startup because application liveness must not mutate infrastructure. A later media-storage use case should add an idempotent bucket provisioning task with an explicit retention policy.

Named volumes preserve local service data across ordinary `docker compose down` calls. Running `docker compose down --volumes` intentionally and irreversibly removes the local PostgreSQL, Redis, and MinIO data.

