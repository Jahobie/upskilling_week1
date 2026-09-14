#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Service uses only the Python standard library — no venv or install needed.
exec python3 "$SCRIPT_DIR/src/service.py" "$@"
