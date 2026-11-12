#!/bin/sh
# Apply pending migrations, then start the API.
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
