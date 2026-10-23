#!/bin/sh
# Apply migrations, then run a single worker: the advisory lock rejects a second
# instance, so --workers 1 is required rather than a tuning choice.
set -e

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
