#!/usr/bin/env bash
set -e

# Resolve absolute path to the project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Activate the local virtual environment
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
else
    echo "Error: Virtual environment not found at $PROJECT_ROOT/.venv"
    exit 1
fi

# Print diagnostic information
echo "Project Root: $PROJECT_ROOT"
echo "Python Interpreter: $(which python)"

# Execute Streamlit using the active Python interpreter
exec python -m streamlit run app/streamlit_app.py "$@"
