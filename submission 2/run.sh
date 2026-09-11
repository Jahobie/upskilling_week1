#!/usr/bin/env bash
set -euo pipefail

exec uv run --project "$(dirname "$0")" python "$(dirname "$0")/src/integration.py" "$@"