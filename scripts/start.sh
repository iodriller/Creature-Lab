#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

choose_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

if ! PYTHON="$(choose_python)"; then
  echo "Creature Lab needs Python 3.11 or newer." >&2
  echo "Install Python, then rerun: bash scripts/start.sh" >&2
  exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/start.py" "$@"
