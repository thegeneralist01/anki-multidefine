#!/usr/bin/env bash
# Build multidefine.ankiaddon for upload to AnkiWeb.
# Run from repo root: bash scripts/build_ankiaddon.sh

set -e

OUT="multidefine.ankiaddon"
ADDON_DIR="AutoDefineAddon"

# Remove old build
rm -f "$OUT"

# Zip the contents of AutoDefineAddon/ (not the folder itself)
# Exclude Python cache, macOS metadata, and test files
cd "$ADDON_DIR"
zip -r "../$OUT" . \
  --exclude "*.pyc" \
  --exclude "__pycache__/*" \
  --exclude ".DS_Store" \
  --exclude "bs4/tests/*"
cd ..

echo "Built: $OUT ($(du -sh "$OUT" | cut -f1))"
