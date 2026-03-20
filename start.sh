#!/bin/bash
celery -A backend.workers.tasks worker --loglevel=info &
uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
