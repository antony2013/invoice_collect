# Coolify Deployment — invoice_collect

Deploy the FastAPI backend on Coolify (v4+) using the **Docker Compose build
pack** from this Git repository. The stack is app-only: **no MinIO container**.
File storage uses an external S3-compatible bucket (`s3.jamicore.com`, bucket
`invoice-upload`).

## What's already prepared in the repo

- `Dockerfile` — non-root (`appuser`), healthcheck, copies app + migrations.
- `docker/entrypoint.sh` — runs `alembic upgrade head` then starts uvicorn.
  Schema auto-applies on every deploy; no manual migration step.
- `docker-compose.yml` — single `backend` service. Prod-safe env defaults
  (`ENVIRONMENT=production`, `DEBUG=false`), named volume for SQLite,
  `restart: unless-stopped`, healthcheck. No MinIO/minio-init services.
- `.dockerignore` — keeps `.env`, `.git`, `tests`, `mobile`, docs out of the image.

## Prerequisites

- A Coolify instance (self-hosted on a VPS with Docker) and a domain pointing
  to it.
- Your invoice_collect repo on GitHub. Public repo → no auth setup needed.
  Private repo → use a Coolify "Deploy Key" instead of Public Repository.
- An S3-compatible bucket named `invoice-upload` at `https://s3.jamicore.com`
  (already created) with **Access Key** and **Secret Key**.

## Step-by-step

### 1. Create the resource

1. Open your Coolify project → **Environment** → **+ New → Application**.
2. Choose the source:
   - **Public Repository**: paste `https://github.com/antony2013/invoice_collect.git`
     → **Check Repository**. Branch auto-selects `master`.
   - **Private repository**: create a **Deploy Key** and add it to the GitHub repo.
3. Under **Configuration → General**, set **Build Pack = Docker Compose**.
4. Set:
   - **Base Directory** = `/` (repo root)
   - **Docker Compose Location** = `docker-compose.yml`
5. Enable **Preserve Repository During Deployment** (recommended by Coolify so
   the compose definition and build context stay present).
6. Coolify parses the compose file — you'll see the single `backend` service
   preloaded.

### 2. Set environment variables

Open the resource's **Environment Variables** tab (stored in Coolify, not the
image). Set at minimum:

| Variable | Value | Notes |
|---|---|---|
| `SECRET_KEY` | `<openssl rand -hex 32>` | **Required.** App refuses <32 char / default keys in production. |
| `ENVIRONMENT` | `production` | |
| `DEBUG` | `false` | |
| `CORS_ORIGINS` | `["https://app.yourdomain.com","https://mobile-app.yourdomain.com"]` | Comma-split or JSON array. |
| `MINIO_ACCESS_KEY` | your s3.jamicore.com Access Key | **Required** for uploads/downloads. |
| `MINIO_SECRET_KEY` | your s3.jamicore.com Secret Key | **Required** for uploads/downloads. |

Backend defaults (only override if your bucket differs):
`MINIO_ENDPOINT=s3.jamicore.com`, `MINIO_BUCKET=invoice-upload`,
`MINIO_SECURE=true`.

Optional: `ACCESS_TOKEN_EXPIRE_MINUTES`, `LOG_LEVEL`, `BACKEND_PORT`.

### 3. Set up domains

Under **Domains**: point your API domain at the `backend` service, container
port **8000** (e.g. `https://api.yourdomain.com`). Coolify issues an HTTPS
cert automatically and proxies to the container.

### 4. Deploy

Click **Deploy**. Watch the logs:
- `[entrypoint] applying database migrations...` → alembic runs head.
- `[entrypoint] starting API on 0.0.0.0:8000`.

### 5. Verify

```
curl https://api.yourdomain.com/api/v1/health
# → {"status":"ok","app":"Invoice Management API","version":"0.1.0"}
```

Then point the Expo mobile app at the backend by changing `API_BASE_URL` in
`mobile/src/api.ts` to `https://api.yourdomain.com/api/v1` and rebuild/export
the app (or update the backend `CORS_ORIGINS` for the web UI).

## Useful troubleshooting

- **Health check failing at first** — normal during `alembic upgrade`; the
  compose `healthcheck` has a `start_period`.
- **`not a directory: unknown`** — compose can't find a file; make sure
  **Preserve Repository During Deployment** is on and Base Directory is `/`.
- **Uploads return 503 "Object storage is unavailable"** — the app can't reach
  `s3.jamicore.com`. Check `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`,
  `MINIO_SECRET_KEY`, and that the `invoice-upload` bucket exists.
- **Image fails to bind** — Coolify proxies to the internal port 8000; no host
  port publishing is needed.

## Known limitations & next steps

- **SQLite not PostgreSQL**: the current stack persists SQLite on a named
  volume. Fine for a single-replica MVP, but for multi-replica / high-availability
  switch to Postgres: add `psycopg[binary]` to `pyproject.toml`, set
  `DATABASE_URL=postgresql+psycopg://...`, and make `reports` month-grouping
  DB-portable (it uses `func.strftime`, SQLite-specific).
- **Backups**: snapshot the `backend_data` Coolify volume (Coolify backup
  feature or manual `docker run --volumes-from`). Uploaded files live in the
  remote S3 bucket, which requires its own backup/versioning strategy.
- **No local MinIO**: the compose stack intentionally ships app-only. For a
  local dev environment, run `start_backend.ps1` (uvicorn) and point `.env`
  at whatever storage you want; if you ever need an ephemeral local MinIO,
  start it manually with `docker run -p 9000:9000 minio/minio server /data`.