# Server integration infrastructure

The root `docker-compose.yml` is the source of truth for the Phase 1 Linux server integration stack. Windows development uses native Python and Node.js and does not require Docker.

| Service | Image/runtime | Persistent volume | Health signal |
| --- | --- | --- | --- |
| PostgreSQL | `postgres:18.3-alpine` | `postgres_data` | `pg_isready` |
| Redis | `redis:8.10.0-alpine` | `redis_data` | `redis-cli ping` |
| MinIO | pinned release image | `minio_data` | MinIO live endpoint |
| Backend | repository Dockerfile | none | `GET /health` |
| Frontend | repository production Dockerfile | none | `GET /status` |

All services share the private `growth_learning` bridge network. PostgreSQL, Redis, and MinIO have no host port mappings. Only frontend and backend ports are published, with bind addresses and ports controlled by the untracked root `.env` file. When Nginx is installed on the same host, bind both application ports to `127.0.0.1`.

The fixed deployment path is `/opt/apps/growth-learning`. Run `scripts/server-bootstrap.sh` once to create a protected `.env` with generated service credentials and install the idempotent shell command block. GitHub CI publishes an immutable frontend Linux image archive for every `main` commit. `scripts/server-deploy.sh` validates and loads that exact revision, builds only the lightweight backend locally, starts the stack, and waits for health checks.

For path-based publishing, CI builds the deployment frontend with `/growth` as its Next.js base path and `/growth/api` as its browser API URL. Copy `infra/nginx/growth-learning.conf` to `/etc/nginx/snippets/growth-learning.conf`. The temporary IP/default virtual host may include that snippet directly. For the production domain, install `infra/nginx/growth-learning-site.conf` as an independent server block after Certbot has issued the trusted certificate. Always validate with `nginx -t` before reloading Nginx. Configure the server `.env` with:

```dotenv
BACKEND_BIND_ADDRESS=127.0.0.1
FRONTEND_BIND_ADDRESS=127.0.0.1
PUBLIC_APP_BASE_PATH=/growth
PUBLIC_API_BASE_URL=/growth/api
API_ROOT_PATH=/growth/api
CORS_ORIGINS=https://growth.flycloudjia.xyz,http://106.55.18.228
AUTH_COOKIE_SECURE=true
```

The production browser address remains `https://growth.flycloudjia.xyz/growth`; do not remove the `/growth` base path. Port 80 for the domain redirects to the same HTTPS request URI, while the IP/default virtual host remains independently available. Certbot's systemd timer performs certificate renewal.

The backend keeps experiment and growth media in the private MinIO `MINIO_BUCKET` named volume. The bucket is created idempotently on the first authorized upload, never as a health-check side effect. Object keys contain opaque family/session/asset IDs rather than child names. Browsers read objects only through household-authorized API endpoints; do not add a public Nginx `/media` or `/static` alias. The Nginx API location allows the configured 50 MiB video ceiling and disables request buffering for uploads.

Named volumes preserve local service data across ordinary `docker compose down` calls. Running `docker compose down --volumes` intentionally and irreversibly removes the local PostgreSQL, Redis, and MinIO data.
