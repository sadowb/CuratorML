#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

ML_DIR="$PROJECT_ROOT/backend/app/services/ml"
OCR_DIR="$PROJECT_ROOT/backend/models/manga-ocr-2025-onnx"
YOLO_MODEL_RELATIVE_PATH="backend/app/services/ml/best.pt"
YOLO_MODEL_DEST_PATH="$PROJECT_ROOT/$YOLO_MODEL_RELATIVE_PATH"
LEGACY_YOLO_MODEL_RELATIVE_PATH="backend/app/services/ml/final_best_with_split_logic.pt"
LEGACY_YOLO_MODEL_DEST_PATH="$PROJECT_ROOT/$LEGACY_YOLO_MODEL_RELATIVE_PATH"

# Default public YOLO segmentation weights. The Hugging Face repository also
# contains last.pt; best.pt is the default for CuratorML.
DEFAULT_YOLO_MODEL_URL="https://huggingface.co/ShadowB/Manga109-panel-balloon-text-yolov26-segmentation/resolve/main/best.pt?download=1"

if [[ -n "${YOLO_MODEL_URL:-}" ]]; then
  ACTIVE_YOLO_MODEL_URL="$YOLO_MODEL_URL"
elif [[ -n "${INPAINT_MODEL_URL:-}" ]]; then
  ACTIVE_YOLO_MODEL_URL="$INPAINT_MODEL_URL"
  echo "⚠ INPAINT_MODEL_URL is deprecated; use YOLO_MODEL_URL for YOLO segmentation weights."
else
  ACTIVE_YOLO_MODEL_URL="$DEFAULT_YOLO_MODEL_URL"
fi

# MangaOCR ONNX model repository used by manga-ocr-torchless / local OCR loading.
MANGA_OCR_REPO=${MANGA_OCR_REPO:-"https://huggingface.co/l0wgear/manga-ocr-2025-onnx/resolve/main"}

# Files required for local from_pretrained-style loading: ONNX weights + tokenizer/config assets.
MANGA_OCR_FILES=(
  "encoder_model.onnx"
  "decoder_model.onnx"
  "config.json"
  "generation_config.json"
  "preprocessor_config.json"
  "special_tokens_map.json"
  "tokenizer.json"
  "tokenizer_config.json"
  "vocab.txt"
)

echo "Downloading model files for CuratorML..."

mkdir -p "$ML_DIR" "$OCR_DIR"

failed=0

download_if_missing() {
  local url="$1"
  local dest="$2"
  local filename
  filename=$(basename "$dest")

  if [[ -f "$dest" ]]; then
    echo "✓ ${filename} already exists"
    return 0
  fi

  echo "Downloading ${filename}..."
  if ! curl --fail --location --progress-bar --max-time 300 -o "$dest" "$url"; then
    echo "✗ Failed to download ${filename}"
    rm -f "$dest"
    failed=1
  fi
}

download_yolo_model() {
  local dest="$1"
  local filename
  filename=$(basename "$dest")

  if [[ -f "$dest" ]]; then
    echo "✓ ${filename} already exists"
    return 0
  fi

  echo "Downloading ${filename}..."
  if curl --fail --location --progress-bar --max-time 300 -o "$dest" "$ACTIVE_YOLO_MODEL_URL" && [[ -s "$dest" ]]; then
    return 0
  fi

  rm -f "$dest"

  if [[ -f "$LEGACY_YOLO_MODEL_DEST_PATH" ]]; then
    cat >&2 <<EOF
⚠ Failed to download ${filename}, but legacy YOLO weights exist at:
  ${LEGACY_YOLO_MODEL_RELATIVE_PATH}

The inference service can still use that legacy path for backwards
compatibility. New installs should use the Hugging Face best.pt default.
EOF
    return 0
  fi

  cat >&2 <<EOF
✗ Failed to download ${filename} from:
  ${ACTIVE_YOLO_MODEL_URL}

The YOLO segmentation model is required for ML auto-detection. The repository
keeps model weights out of Git. The default public source is Hugging Face:
  ${DEFAULT_YOLO_MODEL_URL}

Resolve this using one of these options:
  1. Rerun with a reachable direct URL:
     YOLO_MODEL_URL=<direct-url> bash scripts/download-models.sh
  2. Manually place the YOLO weights at:
     ${YOLO_MODEL_RELATIVE_PATH}
     (resolved path: ${dest})
  3. Existing installs may continue using the legacy path:
     ${LEGACY_YOLO_MODEL_RELATIVE_PATH}

INPAINT_MODEL_URL is still accepted as a deprecated alias for YOLO_MODEL_URL,
but this file is used only for YOLO segmentation; cleanup/inpainting uses
traditional OpenCV processing.
EOF
  return 1
}

if ! download_yolo_model "$YOLO_MODEL_DEST_PATH"; then
  exit 1
fi

for file in "${MANGA_OCR_FILES[@]}"; do
  download_if_missing \
    "$MANGA_OCR_REPO/$file?download=1" \
    "$OCR_DIR/$file"
done

if [[ "$failed" -eq 0 ]]; then
  echo "✓ All models ready"
  exit 0
else
  echo "✗ Some downloads failed"
  exit 1
fi
