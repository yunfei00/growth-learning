# Server integration infrastructure

The root `docker-compose.yml` is the source of truth for the Phase 1 Linux server integration stack. Windows development uses native Python and Node.js and does not require Docker.

| Service | Image/runtime | Persistent volume | Health signal |
| --- | --- | --- | --- |
| PostgreSQL | `postgres:18.3-alpine` | `postgres_data` | `pg_isready` |
| Redis | `redis:8.10.0-alpine` | `redis_data` | `redis-cli ping` |
| MinIO | pinned release image | `minio_data` | MinIO live endpoint |
| Backend | repository Dockerfile | none | `GET /health` |
| Frontend | repository production Dockerfile | none | `GET /status` |

All services share the private `growth_learning` bridge network. PostgreSQL, Redis, and MinIO have no host port mappings. Only frontend and backend ports are published, with bind addresses and ports controlled by the untracked root `.env` file.

The fixed deployment path is `/opt/apps/growth-learning`. Run `scripts/server-bootstrap.sh` once to create a protected `.env` with generated service credentials and install the idempotent shell command block. GitHub CI publishes an immutable frontend Linux image archive for every `main` commit. `scripts/server-deploy.sh` validates and loads that exact revision, builds only the lightweight backend locally, starts the stack, and waits for health checks.

The Phase 1 backend does not create a bucket at startup because application liveness must not mutate infrastructure. A later media-storage use case should add an idempotent bucket provisioning task with an explicit retention policy.

Named volumes preserve local service data across ordinary `docker compose down` calls. Running `docker compose down --volumes` intentionally and irreversibly removes the local PostgreSQL, Redis, and MinIO data.
