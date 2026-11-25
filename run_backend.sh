#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export TOKENIZERS_PARALLELISM=false
if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python -m uvicorn src.api:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
fi
exec python -m uvicorn src.api:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
