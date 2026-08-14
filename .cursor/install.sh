#!/usr/bin/env bash
# Idempotent repository bootstrap for the Label Studio Cloud Agent environment.
# Installs backend (uv) and frontend (bun) dependencies and builds the frontend
# bundle so the Django dev server can serve the full UI.
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"

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

echo "==> Install complete"
