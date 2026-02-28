from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORECARD_REPORT = ROOT / "evals" / "reports" / "latest_report.json"
GOAL_REPORT = ROOT / "evals" / "reports" / "project_goal_status.json"
DRIFT_REPORT = ROOT / "evals" / "reports" / "eval_drift_snapshot.json"
ADAPTIVE_BENCH_REPORT = ROOT / "evals" / "reports" / "adaptive_vs_static_benchmark.json"
LOAD_REPORT = ROOT / "evals" / "reports" / "load_latency_benchmark.json"
CHAOS_REPORT = ROOT / "evals" / "reports" / "chaos_reliability_report.json"
SEED_REPORT = ROOT / "evals" / "reports" / "seed_reproducibility_report.json"
AI_KIRTAN_REPORT = ROOT / "evals" / "reports" / "ai_kirtan_quality_report.json"
ADAPTER_REPORT = ROOT / "evals" / "reports" / "adapter_starter_kit_verification.json"
WEEKLY_KPI_REPORT = ROOT / "evals" / "reports" / "weekly_kpi_report.json"
OUT_PATH = ROOT / "evals" / "reports" / "release_gate_status.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _dim_score(scorecard: dict, dim_id: str) -> float:
    dims = scorecard.get("scorecard", {}).get("dimensions", [])
    for dim in dims:
        if dim.get("id") == dim_id:
            return float(dim.get("weighted_score", 0.0))
    return 0.0


def main() -> int:
    scorecard = _load(SCORECARD_REPORT)
    goal = _load(GOAL_REPORT)
    drift = _load(DRIFT_REPORT)
    adaptive_bench = _load(ADAPTIVE_BENCH_REPORT)
    load_bench = _load(LOAD_REPORT)
    chaos = _load(CHAOS_REPORT)
    seed = _load(SEED_REPORT)
    ai_kirtan = _load(AI_KIRTAN_REPORT)
    adapter = _load(ADAPTER_REPORT)
    weekly_kpi = _load(WEEKLY_KPI_REPORT)

    min_total = float(os.getenv("RELEASE_MIN_SCORECARD_TOTAL", "93"))
    min_demis = float(os.getenv("RELEASE_MIN_DEMIS", "45"))
    min_sundar = float(os.getenv("RELEASE_MIN_SUNDAR", "45"))

    min_eco = float(os.getenv("RELEASE_MIN_ECOSYSTEM_SCORE", "10"))
    min_business = float(os.getenv("RELEASE_MIN_BUSINESS_SCORE", "9"))
    min_rigor = float(os.getenv("RELEASE_MIN_RIGOR_SCORE", "9.6"))
    min_attempts = int(os.getenv("RELEASE_MIN_CONFIDENCE_ATTEMPTS", "30"))
    min_ci95_low = float(os.getenv("RELEASE_MIN_CONFIDENCE_CI95_LOW", "0.8"))

    total = float(scorecard.get("scorecard", {}).get("total_score_0_to_100", 0.0))
    demis = float(scorecard.get("scorecard", {}).get("demis_lens_score_0_to_50", 0.0))
    sundar = float(scorecard.get("scorecard", {}).get("sundar_lens_score_0_to_50", 0.0))
    total_attempts = int(scorecard.get("summary", {}).get("total_attempts", 0) or 0)
    attempt_ci_low = float(
        scorecard.get("summary", {}).get("attempt_pass_rate_ci95", {}).get("low", 0.0) or 0.0
    )

    d_eco = _dim_score(scorecard, "D_ecosystem_leverage")
    f_business = _dim_score(scorecard, "F_measurable_business_signal")
    g_rigor = _dim_score(scorecard, "G_scientific_eval_rigor")

    checks = [
        {"name": "scorecard_total", "passed": total >= min_total, "value": total, "min": min_total},
        {"name": "demis_lens", "passed": demis >= min_demis, "value": demis, "min": min_demis},
        {"name": "sundar_lens", "passed": sundar >= min_sundar, "value": sundar, "min": min_sundar},
        {
            "name": "repeated_confidence_checks",
            "passed": total_attempts >= min_attempts and attempt_ci_low >= min_ci95_low,
            "value": {
                "total_attempts": total_attempts,
                "attempt_pass_rate_ci95_low": attempt_ci_low,
            },
            "min": {"total_attempts": min_attempts, "attempt_pass_rate_ci95_low": min_ci95_low},
        },
        {"name": "ecosystem_gap_closed", "passed": d_eco >= min_eco, "value": d_eco, "min": min_eco},
        {"name": "business_gap_closed", "passed": f_business >= min_business, "value": f_business, "min": min_business},
        {"name": "rigor_gap_closed", "passed": g_rigor >= min_rigor, "value": g_rigor, "min": min_rigor},
        {
            "name": "adaptive_vs_static_benchmark",
            "passed": bool(adaptive_bench.get("success", {}).get("meets_target", False)),
            "value": adaptive_bench.get("success", {}),
            "min": {"significant_positive_metrics": 2},
        },
        {
            "name": "load_latency_slo",
            "passed": load_bench.get("status") == "PASS",
            "value": load_bench.get("results", {}),
            "min": {"status": "PASS"},
        },
        {
            "name": "chaos_reliability",
            "passed": chaos.get("status") == "PASS",
            "value": chaos.get("status"),
            "min": "PASS",
        },
        {
            "name": "seed_reproducibility",
            "passed": seed.get("status") == "PASS",
            "value": seed.get("comparison", {}),
            "min": {"status": "PASS"},
        },
        {
            "name": "ai_kirtan_contract_quality",
            "passed": ai_kirtan.get("status") == "PASS",
            "value": ai_kirtan.get("summary", {}),
            "min": {"status": "PASS"},
        },
        {
            "name": "adapter_starter_kit",
            "passed": adapter.get("status") == "PASS",
            "value": adapter.get("checks", {}),
            "min": {"status": "PASS"},
        },
        {
            "name": "north_star_contract_and_trends",
            "passed": bool(
                weekly_kpi.get("summary", {}).get("north_star_metric_version")
                and weekly_kpi.get("trend_deltas")
            ),
            "value": {
                "north_star_metric_version": weekly_kpi.get("summary", {}).get("north_star_metric_version"),
                "trend_deltas_present": bool(weekly_kpi.get("trend_deltas")),
            },
            "min": {"north_star_metric_version": "1.0.0", "trend_deltas_present": True},
        },
        {
            "name": "goal_on_track",
            "passed": bool(goal.get("summary", {}).get("on_track_for_hackathon_demo", False)),
            "value": goal.get("summary", {}).get("on_track_for_hackathon_demo", False),
            "min": True,
        },
        {
            "name": "drift_guard",
            "passed": drift.get("status") == "PASS",
            "value": drift.get("status"),
            "min": "PASS",
        },
    ]

    passed = all(c["passed"] for c in checks)
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
