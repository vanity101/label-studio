#!/usr/bin/env bash
# Per-boot reconciliation for the Label Studio Cloud Agent environment.
# Applies database migrations against the local SQLite dev database. Migrations
# are idempotent, so this is safe to run on every start.
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Applying database migrations (SQLite)"
DJANGO_DB=sqlite \
  LOG_DIR=tmp \
  DEBUG=true \
  LOG_LEVEL=INFO \
  DJANGO_SETTINGS_MODULE=core.settings.label_studio \
  uv run python label_studio/manage.py migrate --noinput

echo "==> Start reconciliation complete"
