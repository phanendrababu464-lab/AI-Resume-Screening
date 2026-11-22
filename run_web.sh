#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "=== AI Resume Screening Web Application ==="
echo "Project Root: $REPO_ROOT"

# 1. Activate Python virtual environment
if [ -d "$REPO_ROOT/.venv" ]; then
    source "$REPO_ROOT/.venv/bin/activate"
    echo "Python Interpreter: $(which python)"
else
    echo "Error: .venv not found in $REPO_ROOT"
    exit 1
fi

# Cleanup background processes on exit
cleanup() {
    echo ""
    echo "Stopping backend and frontend servers..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 2. Start FastAPI Backend on port 8000
echo "Starting FastAPI backend on http://127.0.0.1:8000 ..."
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Wait briefly for backend to initialize
sleep 2

# 3. Start Vite Dev Server on port 5173
echo "Starting Vite React frontend on http://localhost:5173 ..."
cd "$REPO_ROOT/frontend"
npm run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!

echo ""
echo "🚀 Both servers running:"
echo "   - Web Frontend:  http://localhost:5173"
echo "   - Backend API:   http://127.0.0.1:8000"
echo "   - API Docs:      http://127.0.0.1:8000/docs"
echo "Press Ctrl+C to terminate both servers."

wait
