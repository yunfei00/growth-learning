#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

cd "$PROJECT_ROOT/backend"
../.venv/bin/python -m ruff check .
../.venv/bin/python -m ruff format --check .
../.venv/bin/python -m pytest

cd "$PROJECT_ROOT/frontend"
pnpm test
pnpm lint
pnpm typecheck
pnpm build
