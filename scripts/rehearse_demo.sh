#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT_DIR/api"
MODE="full"

usage() {
  cat <<USAGE
Usage: ./scripts/rehearse_demo.sh [--degraded]

Options:
  --degraded   Run fallback rehearsal path (skip heavy benchmarks)
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --degraded)
      MODE="degraded"
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

cd "$API_DIR"
make install

if [[ "$MODE" == "full" ]]; then
  make goal_test poc_test bench_adaptive load_benchmark chaos_reliability ai_kirtan_quality adapter_verify weekly_kpi release_evidence_summary
else
  make goal_test poc_test chaos_reliability weekly_kpi release_evidence_summary
fi

export DEMO_MODE="$MODE"
PYTHONPATH=src:. .venv/bin/python - <<'PY'
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

root = Path("evals/reports")
mode = os.environ.get("DEMO_MODE", "full")

def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

goal = load_json(root / "project_goal_status.json")
poc = load_json(root / "maha_mantra_poc_status.json")
adaptive = load_json(root / "adaptive_vs_static_benchmark.json")
load = load_json(root / "load_latency_benchmark.json")
chaos = load_json(root / "chaos_reliability_report.json")
ai_kirtan = load_json(root / "ai_kirtan_quality_report.json")
adapter = load_json(root / "adapter_starter_kit_verification.json")
weekly = load_json(root / "weekly_kpi_report.json")

checkpoints = {
    "A_frontier_product_novelty": bool(goal.get("summary", {}).get("on_track_for_hackathon_demo", False)),
    "B_user_value_proof": bool(adaptive.get("success", {}).get("meets_target", False)) if mode == "full" else True,
    "C_scale_readiness": (load.get("status") == "PASS") if mode == "full" else True,
    "D_ecosystem_leverage": (adapter.get("status") == "PASS") if mode == "full" else True,
    "E_safety_privacy_rights": bool(poc.get("status") == "PASS"),
    "F_business_signal": bool(weekly.get("trend_deltas")),
    "G_eval_rigor": bool(chaos.get("status") == "PASS"),
    "AI_kirtan_contract": (ai_kirtan.get("status") == "PASS") if mode == "full" else True,
}
overall = all(checkpoints.values())
report = {
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "mode": mode,
    "status": "PASS" if overall else "FAIL",
    "checkpoints": checkpoints,
    "artifact_map": {
        "goal": "api/evals/reports/project_goal_status.json",
        "poc": "api/evals/reports/maha_mantra_poc_status.json",
        "adaptive_benchmark": "api/evals/reports/adaptive_vs_static_benchmark.json",
        "load_benchmark": "api/evals/reports/load_latency_benchmark.json",
        "chaos": "api/evals/reports/chaos_reliability_report.json",
        "ai_kirtan": "api/evals/reports/ai_kirtan_quality_report.json",
        "adapter": "api/evals/reports/adapter_starter_kit_verification.json",
        "weekly_kpi": "api/evals/reports/weekly_kpi_report.json",
    },
}
out = root / "demo_rehearsal_report.json"
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
PY

echo "Demo rehearsal complete. Artifact: api/evals/reports/demo_rehearsal_report.json"
