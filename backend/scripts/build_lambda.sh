#!/usr/bin/env bash
# Build the Lambda deployment package (spec 10.8).
#
# Run from backend/:  ./scripts/build_lambda.sh
# Produces:           backend/build/scrappy-api.zip
#
# CI runs this same script, so the package that is tested locally and the one that is
# deployed are built identically.
set -euo pipefail

cd "$(dirname "$0")/.."
BUILD_DIR="build"
PACKAGE_DIR="$BUILD_DIR/package"
ZIP_PATH="$BUILD_DIR/scrappy-api.zip"

rm -rf "$BUILD_DIR"
mkdir -p "$PACKAGE_DIR"

# --no-dev leaves out pytest, ruff and boto3. The Lambda runtime already provides boto3,
# and bundling it would only make the package bigger and risk a version clash.
uv export --no-dev --no-hashes --format requirements-txt > "$BUILD_DIR/requirements.txt"

# --python-platform is what makes this work from an ARM Mac: it fetches Linux x86-64
# wheels rather than building for the host. Without it, psycopg's compiled parts would be
# Mac binaries and the Lambda would fail to import them.
uv pip install \
  --target "$PACKAGE_DIR" \
  --python-platform x86_64-manylinux_2_28 \
  --python-version 3.13 \
  --only-binary :all: \
  --quiet \
  -r "$BUILD_DIR/requirements.txt"

cp -r app "$PACKAGE_DIR/app"

# Drop bytecode caches so the zip's hash depends only on real content.
#
# Do NOT delete *.dist-info: psycopg reads its own version through
# importlib.metadata.version("psycopg"), which needs that metadata. Without it the version
# reads as 0.0.0.0 and SQLAlchemy refuses to start with "psycopg version 3.0.2 or higher
# is required" — at runtime on Lambda, not at build time.
find "$PACKAGE_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +

(cd "$PACKAGE_DIR" && zip -qr "../../$ZIP_PATH" .)

echo "built $ZIP_PATH ($(du -h "$ZIP_PATH" | cut -f1))"
