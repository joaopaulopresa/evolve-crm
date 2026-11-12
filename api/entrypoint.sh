#!/bin/sh
# Apply pending migrations, optionally load the demo data, then start the API.
set -e
alembic upgrade head
if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
    python -m app.seed
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
