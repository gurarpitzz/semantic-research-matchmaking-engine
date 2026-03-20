#!/bin/bash
export MALLOC_ARENA_MAX=2
celery -A backend.workers.tasks worker --concurrency=1 --loglevel=info &
uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
