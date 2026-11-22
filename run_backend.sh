#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

echo "Starting AI Resume Screening backend on ${HOST}:${PORT}..."
exec python -m uvicorn src.api:app --host "${HOST}" --port "${PORT}"
