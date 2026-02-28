#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="$ROOT_DIR/docs/submission/hackathon_submission_dossier.md"
SUMMARY="$ROOT_DIR/api/evals/reports/release_evidence_summary.md"
OUT="$ROOT_DIR/docs/submission/hackathon_submission_dossier.generated.md"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Missing template: $TEMPLATE"
  exit 1
fi

{
  cat "$TEMPLATE"
  echo
  echo "## Appendix: Latest Release Evidence Summary"
  echo
  if [[ -f "$SUMMARY" ]]; then
    cat "$SUMMARY"
  else
    echo "_Run \`make -C api release_evidence_summary\` to populate this appendix._"
  fi
} > "$OUT"

echo "Generated: $OUT"
