#!/bin/sh
set -e

alembic upgrade head
python -m app.core.bootstrap

exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
