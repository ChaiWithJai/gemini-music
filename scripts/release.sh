#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT_DIR/api"
DRY_RUN=false

usage() {
  cat <<USAGE
Usage: ./scripts/release.sh <version> [--dry-run]

Examples:
  ./scripts/release.sh v0.2.0
  ./scripts/release.sh 0.2.0 --dry-run
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

VERSION="$1"
shift || true

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN=true
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

if [[ "$VERSION" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  if [[ "$VERSION" == v* ]]; then
    TAG="$VERSION"
  else
    TAG="v$VERSION"
  fi
else
  echo "Version must be semver (vMAJOR.MINOR.PATCH or MAJOR.MINOR.PATCH)."
  exit 1
fi

cd "$ROOT_DIR"

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "Release must run from main. Current branch: $CURRENT_BRANCH"
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit or stash changes before release."
  exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag already exists locally: $TAG"
  exit 1
fi

if git ls-remote --tags origin "refs/tags/$TAG" | grep -q "$TAG"; then
  echo "Tag already exists on origin: $TAG"
  exit 1
fi

echo "Syncing main with origin..."
git fetch origin
git pull --ff-only origin main

echo "Running release quality gates..."
cd "$API_DIR"
make ci
cd "$ROOT_DIR"

if [[ "$DRY_RUN" == "true" ]]; then
  echo "Dry run successful. Would create and push tag: $TAG"
  exit 0
fi

echo "Creating annotated tag $TAG"
git tag -a "$TAG" -m "Release $TAG"

echo "Pushing main and tag"
git push origin main
git push origin "$TAG"

EVIDENCE_BUNDLE="$API_DIR/evals/reports/release-evidence-${TAG}.tar.gz"
EVIDENCE_SUMMARY="$API_DIR/evals/reports/release_evidence_summary.md"
echo "Building release evidence bundle..."
tar -czf "$EVIDENCE_BUNDLE" \
  -C "$API_DIR/evals/reports" \
  latest_report.json \
  project_goal_status.json \
  release_gate_status.json \
  eval_drift_snapshot.json \
  adaptive_vs_static_benchmark.json \
  load_latency_benchmark.json \
  chaos_reliability_report.json \
  seed_reproducibility_report.json \
  ai_kirtan_quality_report.json \
  adapter_starter_kit_verification.json \
  weekly_kpi_report.json \
  release_evidence_summary.md

if command -v gh >/dev/null 2>&1; then
  echo "Creating GitHub release for $TAG"
  gh release create "$TAG" --generate-notes --latest
  echo "Uploading release evidence artifacts"
  gh release upload "$TAG" "$EVIDENCE_BUNDLE" "$EVIDENCE_SUMMARY" --clobber
else
  echo "gh CLI not found. Tag pushed, but GitHub release not created automatically."
fi

echo "Release complete: $TAG"
