#!/usr/bin/env bash
# Idempotent repository bootstrap for the Label Studio Cloud Agent environment.
# Installs backend (uv) and frontend (bun) dependencies and builds the frontend
# bundle so the Django dev server can serve the full UI.
set -euo pipefail

# uv and bun are installed system-wide in the Dockerfile (/usr/local/bin).
export PATH="/usr/local/bin:$PATH"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Installing backend dependencies with uv"
uv sync --frozen --group test

echo "==> Installing frontend dependencies with bun"
# django-manifest-plugin writes manifest.json here during the frontend build;
# collectstatic later consumes it, so make sure the directory exists.
mkdir -p label_studio/core/static/js
cd web
bun install --frozen-lockfile

echo "==> Building frontend bundle"
NODE_OPTIONS="--max-old-space-size=4096" bun run build

cd "$REPO_ROOT"

echo "==> Collecting static files"
# Populates STATIC_ROOT (label_studio/core/static_build), including
# js/manifest.json which manifest_assets.py reads to resolve hashed asset URLs.
# Without this the dev server serves a blank page in non-HMR mode.
DJANGO_DB=sqlite \
  LOG_DIR=tmp \
  DEBUG=true \
  LOG_LEVEL=INFO \
  DJANGO_SETTINGS_MODULE=core.settings.label_studio \
  uv run python label_studio/manage.py collectstatic --no-input

echo "==> Install complete"
