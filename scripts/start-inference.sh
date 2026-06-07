#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

echo "Starting ML inference server..."

# Check for models
ML_DIR="$PROJECT_ROOT/backend/app/services/ml"
if [ ! -f "$ML_DIR/final_best_with_split_logic.pt" ]; then
  echo "⚠ Model file not found. Run scripts/download-models.sh first."
  exit 1
fi

VENV_DIR="$PROJECT_ROOT/backend/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS_FILE="$PROJECT_ROOT/backend/requirements-inference.txt"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Creating project-local virtual environment at $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
fi

echo "Upgrading pip in project-local virtual environment..."
"$VENV_PYTHON" -m pip install --upgrade pip

echo "Installing inference dependencies from $REQUIREMENTS_FILE..."
"$VENV_PYTHON" -m pip install -r "$REQUIREMENTS_FILE"

cd "$PROJECT_ROOT/backend"
echo "Starting inference server with backend/.venv Python..."
exec "$VENV_PYTHON" -m uvicorn app.inference_main:app --host 0.0.0.0 --port 8001 --reload
