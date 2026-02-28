#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== Gemini Music preflight diagnostics =="

failures=0

check() {
  local label="$1"
  shift
  if "$@"; then
    echo "[PASS] $label"
  else
    echo "[FAIL] $label"
    failures=$((failures + 1))
  fi
}

check "git available" command -v git >/dev/null 2>&1
check "gh available" command -v gh >/dev/null 2>&1
if command -v gh >/dev/null 2>&1; then
  check "gh authenticated" gh auth status >/dev/null 2>&1
fi

check "python3.13 available" command -v python3.13 >/dev/null 2>&1
check "make available" command -v make >/dev/null 2>&1
check "npx available (Playwright workflows)" command -v npx >/dev/null 2>&1

check "git user.name configured" git config --get user.name >/dev/null 2>&1
check "git user.email configured" git config --get user.email >/dev/null 2>&1

if [[ -d "$ROOT_DIR/api" ]]; then
  echo "[INFO] API directory located: $ROOT_DIR/api"
else
  echo "[FAIL] API directory missing at $ROOT_DIR/api"
  failures=$((failures + 1))
fi

if [[ $failures -gt 0 ]]; then
  echo "Preflight found $failures issue(s). See docs/runbooks/day0.md troubleshooting matrix."
  exit 1
fi

echo "Preflight checks passed."
