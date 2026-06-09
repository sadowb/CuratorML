#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

INFERENCE_HOST=${INFERENCE_HOST:-127.0.0.1}
INFERENCE_PORT=${INFERENCE_PORT:-8001}
INFERENCE_RELOAD=${INFERENCE_RELOAD:-false}
INFERENCE_RELOAD_NORMALIZED=$(printf '%s' "$INFERENCE_RELOAD" | tr '[:upper:]' '[:lower:]')

UVICORN_ARGS=(app.inference_main:app --host "$INFERENCE_HOST" --port "$INFERENCE_PORT")
case "$INFERENCE_RELOAD_NORMALIZED" in
  1|true|yes|y|on)
    UVICORN_ARGS+=(--reload)
    ;;
  0|false|no|n|off)
    ;;
  *)
    echo "Invalid INFERENCE_RELOAD=$INFERENCE_RELOAD. Use true/false, yes/no, 1/0, or on/off."
    exit 1
    ;;
esac

echo "Starting ML inference server on ${INFERENCE_HOST}:${INFERENCE_PORT} (reload=${INFERENCE_RELOAD_NORMALIZED})..."

# Check for YOLO segmentation weights. New installs use best.pt from Hugging Face;
# the legacy filename remains supported for existing local setups.
ML_DIR="$PROJECT_ROOT/backend/app/services/ml"
PRIMARY_YOLO_MODEL="$ML_DIR/best.pt"
LEGACY_YOLO_MODEL="$ML_DIR/final_best_with_split_logic.pt"
CONFIGURED_YOLO_MODEL_PATH=${YOLO_MODEL_PATH:-}

if [ -n "$CONFIGURED_YOLO_MODEL_PATH" ]; then
  if [[ "$CONFIGURED_YOLO_MODEL_PATH" = /* ]]; then
    CONFIGURED_YOLO_CANDIDATES=("$CONFIGURED_YOLO_MODEL_PATH")
  else
    CONFIGURED_YOLO_CANDIDATES=(
      "$PROJECT_ROOT/$CONFIGURED_YOLO_MODEL_PATH"
      "$PROJECT_ROOT/backend/$CONFIGURED_YOLO_MODEL_PATH"
    )
  fi

  CONFIGURED_YOLO_FOUND=""
  for candidate in "${CONFIGURED_YOLO_CANDIDATES[@]}"; do
    if [ -f "$candidate" ]; then
      CONFIGURED_YOLO_FOUND="$candidate"
      break
    fi
  done

  if [ -z "$CONFIGURED_YOLO_FOUND" ]; then
    echo "⚠ Configured YOLO_MODEL_PATH not found: $CONFIGURED_YOLO_MODEL_PATH"
    exit 1
  fi
  export YOLO_MODEL_PATH="$CONFIGURED_YOLO_FOUND"
  echo "Using configured YOLO model: $CONFIGURED_YOLO_FOUND"
elif [ -f "$PRIMARY_YOLO_MODEL" ]; then
  echo "Using YOLO model: $PRIMARY_YOLO_MODEL"
elif [ -f "$LEGACY_YOLO_MODEL" ]; then
  echo "⚠ Using legacy YOLO model path: $LEGACY_YOLO_MODEL"
  echo "  Run scripts/download-models.sh to fetch the Hugging Face best.pt default."
  export YOLO_MODEL_PATH="backend/app/services/ml/final_best_with_split_logic.pt"
else
  echo "⚠ YOLO model file not found. Run scripts/download-models.sh first."
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
exec "$VENV_PYTHON" -m uvicorn "${UVICORN_ARGS[@]}"
