#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

export GROWTH_LEARNING_DIR="$PROJECT_ROOT"
exec bash "$SCRIPT_DIR/server-deploy.sh" "$@"
