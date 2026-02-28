from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LATEST_REPORT = ROOT / "evals" / "reports" / "latest_report.json"
GOAL_REPORT = ROOT / "evals" / "reports" / "project_goal_status.json"
RELEASE_GATE = ROOT / "evals" / "reports" / "release_gate_status.json"
OUT_PATH = ROOT / "evals" / "reports" / "release_evidence_summary.md"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    latest = _load(LATEST_REPORT)
    goal = _load(GOAL_REPORT)
    gates = _load(RELEASE_GATE)

    scorecard = latest.get("scorecard", {})
    dims = scorecard.get("dimensions", [])
    dim_map = {dim.get("id"): dim for dim in dims}

    lines = [
        "# Release Evidence Summary",
        "",
        f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat()}",
        "",
        "## Score Summary",
        "",
        f"- Total score: {scorecard.get('total_score_0_to_100', 0.0)}",
        f"- Demis lens: {scorecard.get('demis_lens_score_0_to_50', 0.0)}",
        f"- Sundar lens: {scorecard.get('sundar_lens_score_0_to_50', 0.0)}",
        f"- Release gate status: {gates.get('status', 'UNKNOWN')}",
        "",
        "## Judge Criteria Mapping (A-G)",
        "",
    ]

    ordered_ids = [
        "A_frontier_product_novelty",
        "B_user_value_proof",
        "C_scale_readiness",
        "D_ecosystem_leverage",
        "E_safety_privacy_rights",
        "F_measurable_business_signal",
        "G_scientific_eval_rigor",
    ]
    for dim_id in ordered_ids:
        dim = dim_map.get(dim_id, {})
        lines.append(f"- {dim.get('id', dim_id)}: score={dim.get('weighted_score', 0.0)} rating={dim.get('rating_1_to_5', 0.0)}")

    lines.extend(
        [
            "",
            "## Core Artifacts",
            "",
            "- `api/evals/reports/latest_report.json`",
            "- `api/evals/reports/project_goal_status.json`",
            "- `api/evals/reports/release_gate_status.json`",
            "- `api/evals/reports/eval_drift_snapshot.json`",
            "- `api/evals/reports/adaptive_vs_static_benchmark.json`",
            "- `api/evals/reports/load_latency_benchmark.json`",
            "- `api/evals/reports/chaos_reliability_report.json`",
            "- `api/evals/reports/seed_reproducibility_report.json`",
            "- `api/evals/reports/weekly_kpi_report.json`",
            "",
            "## Goal Status",
            "",
            f"- On track for hackathon demo: {goal.get('summary', {}).get('on_track_for_hackathon_demo', False)}",
        ]
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
