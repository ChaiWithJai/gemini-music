from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import traceback
from pathlib import Path
from statistics import mean
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Gemini Music behavioral evals + leadership scorecard.")
    parser.add_argument(
        "--include-usually-passes",
        action="store_true",
        help="Include USUALLY_PASSES evals (similar to RUN_EVALS=1 behavior).",
    )
    parser.add_argument(
        "--usually-attempts",
        type=int,
        default=3,
        help="Number of attempts for each USUALLY_PASSES eval.",
    )
    parser.add_argument(
        "--manual-evidence",
        default="evals/manual_evidence.json",
        help="Path to manual evidence JSON.",
    )
    parser.add_argument(
        "--output",
        default="evals/reports/latest_report.json",
        help="Path to output JSON report.",
    )
    return parser.parse_args()


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(mean(values))


def main() -> int:
    args = parse_args()

    # Keep eval DB isolated from demo DB.
    os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/gemini_music_eval.db")

    from fastapi.testclient import TestClient

    from gemini_music_api.db import Base, engine
    from gemini_music_api.main import app

    from evals.cases import get_eval_cases
    from evals.framework import compute_scorecard, load_manual_evidence

    def reset_db() -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    manual_path = Path(args.manual_evidence)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    manual_evidence = load_manual_evidence(manual_path)
    eval_cases = get_eval_cases()

    run_evals = []
    aggregate_indicators: dict[str, list[float]] = {}

    total_attempts = 0
    total_passed_attempts = 0

    for case in eval_cases:
        if case.policy == "USUALLY_PASSES" and not args.include_usually_passes:
            run_evals.append(
                {
                    "name": case.name,
                    "policy": case.policy,
                    "skipped": True,
                    "skip_reason": "USUALLY_PASSES disabled; pass --include-usually-passes to run.",
                }
            )
            continue

        attempts = 1 if case.policy == "ALWAYS_PASSES" else max(1, args.usually_attempts)
        attempt_results = []
        case_indicator_values: dict[str, list[float]] = {}

        for attempt in range(1, attempts + 1):
            total_attempts += 1
            reset_db()
            passed = False
            indicators: dict[str, float] = {}
            error_message = None
            error_trace = None

            try:
                with TestClient(app) as client:
                    indicators = case.run(client)
                passed = True
                total_passed_attempts += 1
            except Exception as exc:  # noqa: BLE001
                error_message = str(exc)
                error_trace = traceback.format_exc()

            for key, value in indicators.items():
                case_indicator_values.setdefault(key, []).append(float(value))
                aggregate_indicators.setdefault(key, []).append(float(value))

            attempt_results.append(
                {
                    "attempt": attempt,
                    "passed": passed,
                    "indicators": indicators,
                    "error": error_message,
                    "traceback": error_trace,
                }
            )

        pass_rate = sum(1 for a in attempt_results if a["passed"]) / float(attempts)
        pass_rate_margin = 1.96 * math.sqrt((pass_rate * (1.0 - pass_rate)) / float(attempts)) if attempts else 0.0
        case_status = "PASS" if (pass_rate == 1.0 if case.policy == "ALWAYS_PASSES" else pass_rate >= 0.66) else "FAIL"

        run_evals.append(
            {
                "name": case.name,
                "policy": case.policy,
                "skipped": False,
                "attempts": attempts,
                "pass_rate": round(pass_rate, 3),
                "pass_rate_ci95": {
                    "low": round(max(0.0, pass_rate - pass_rate_margin), 3),
                    "high": round(min(1.0, pass_rate + pass_rate_margin), 3),
                },
                "status": case_status,
                "indicators_avg": {
                    key: round(_safe_mean(values), 3) for key, values in case_indicator_values.items()
                },
                "attempt_results": attempt_results,
            }
        )

    automated_indicators = {
        key: round(_safe_mean(values), 3) for key, values in aggregate_indicators.items()
    }
    scorecard = compute_scorecard(
        automated_indicators=automated_indicators,
        manual_evidence=manual_evidence,
    )

    always_failures = [
        c["name"]
        for c in run_evals
        if not c.get("skipped") and c["policy"] == "ALWAYS_PASSES" and c.get("status") != "PASS"
    ]

    run_status = "PASS" if not always_failures else "FAIL"
    total_pass_rate = (total_passed_attempts / total_attempts) if total_attempts else 0.0
    total_margin = (
        1.96 * math.sqrt((total_pass_rate * (1.0 - total_pass_rate)) / float(total_attempts))
        if total_attempts
        else 0.0
    )

    report: dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "run_status": run_status,
        "config": {
            "include_usually_passes": args.include_usually_passes,
            "usually_attempts": args.usually_attempts,
            "database_url": os.environ.get("DATABASE_URL"),
            "manual_evidence_path": str(manual_path),
        },
        "summary": {
            "total_eval_cases": len(eval_cases),
            "executed_eval_cases": sum(1 for c in run_evals if not c.get("skipped")),
            "total_attempts": total_attempts,
            "passed_attempts": total_passed_attempts,
            "attempt_pass_rate": round(total_pass_rate, 3),
            "attempt_pass_rate_ci95": {
                "low": round(max(0.0, total_pass_rate - total_margin), 3),
                "high": round(min(1.0, total_pass_rate + total_margin), 3),
            },
            "always_failures": always_failures,
        },
        "cases": run_evals,
        "automated_indicators": automated_indicators,
        "manual_evidence": manual_evidence,
        "scorecard": scorecard,
    }

    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote report: {output_path}")
    print(
        f"Total score: {scorecard['total_score_0_to_100']} | "
        f"Demis: {scorecard['demis_lens_score_0_to_50']} | "
        f"Sundar: {scorecard['sundar_lens_score_0_to_50']} | "
        f"Priority ready: {scorecard['priority_ready']}"
    )
    return 0 if run_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
