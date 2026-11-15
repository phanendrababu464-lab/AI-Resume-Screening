#!/usr/bin/env bash
set -e

# Resolve absolute path to the project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Legacy Streamlit UI has been retired in favor of the React + Vite web frontend and FastAPI backend.
# Delegates execution to run_web.sh.
exec "$PROJECT_ROOT/run_web.sh" "$@"
