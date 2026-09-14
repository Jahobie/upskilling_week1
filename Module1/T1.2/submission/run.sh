#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$DIR/node_modules" ]; then
  npm install --prefix "$DIR" --silent
fi

exec "$DIR/node_modules/.bin/tsx" "$DIR/src/integration.ts" "$@"
