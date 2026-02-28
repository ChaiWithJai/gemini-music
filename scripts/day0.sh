#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT_DIR/api"
FULL_RUN=true

usage() {
  cat <<USAGE
Usage: ./scripts/day0.sh [--quick]

Options:
  --quick   Run bootstrap + install + tests only (skip full make ci)
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --quick)
      FULL_RUN=false
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg"
      usage
      exit 1
      ;;
  esac
done

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3.13 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.13)"
  elif [[ -x "/opt/homebrew/bin/python3.13" ]]; then
    PYTHON_BIN="/opt/homebrew/bin/python3.13"
  else
    echo "Python 3.13 not found. Install python3.13 and retry."
    exit 1
  fi
fi

if [[ ! -d "$API_DIR" ]]; then
  echo "API directory not found at: $API_DIR"
  exit 1
fi

echo "Using Python: $PYTHON_BIN"
cd "$API_DIR"

make PYTHON="$PYTHON_BIN" PYTHON_VERSION=3.13 bootstrap
make PYTHON="$PYTHON_BIN" PYTHON_VERSION=3.13 install
make PYTHON="$PYTHON_BIN" PYTHON_VERSION=3.13 doctor

if [[ "$FULL_RUN" == "true" ]]; then
  echo "Running full quality chain (make ci)..."
  make PYTHON="$PYTHON_BIN" PYTHON_VERSION=3.13 ci
else
  echo "Running quick verification (make test)..."
  make PYTHON="$PYTHON_BIN" PYTHON_VERSION=3.13 test
fi

echo "Day 0 setup complete."
echo "Next: cd api && make run"
