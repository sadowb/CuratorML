#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

ML_DIR="$PROJECT_ROOT/backend/app/services/ml"
OCR_DIR="$PROJECT_ROOT/backend/models/manga-ocr-2025-onnx"

# Override these when the project model is moved to Hugging Face.
INPAINT_MODEL_URL=${INPAINT_MODEL_URL:-"https://github.com/sadowb/CuratorML/releases/download/v1.0/final_best_with_split_logic.pt"}

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

echo "Downloading model files for Manga Translation UI..."

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

download_if_missing \
  "$INPAINT_MODEL_URL" \
  "$ML_DIR/final_best_with_split_logic.pt"

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
