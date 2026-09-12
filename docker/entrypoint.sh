#!/bin/sh
set -e

echo "[entrypoint] applying database migrations..."
.venv/bin/alembic upgrade head

echo "[entrypoint] starting API on 0.0.0.0:8000"
exec .venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips '*'