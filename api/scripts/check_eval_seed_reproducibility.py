from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "evals" / "reports" / "seed_reproducibility_report.json"
RUN_EVALS = ROOT / "evals" / "run_evals.py"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify seeded eval reproducibility across repeated runs.")
    parser.add_argument("--seed", type=int, default=1337, help="Seed value to test.")
    parser.add_argument("--attempts", type=int, default=6, help="USUALLY_PASSES attempts for each run.")
    parser.add_argument("--tolerance", type=float, default=1e-6, help="Allowed numeric drift between seeded runs.")
    return parser.parse_args()


def _run_once(output: Path, seed: int, attempts: int) -> dict:
    cmd = [
        sys.executable,
        str(RUN_EVALS),
        "--include-usually-passes",
        "--usually-attempts",
        str(attempts),
        "--seed",
        str(seed),
        "--output",
        str(output),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)
    return _load(output)


def _max_indicator_delta(a: dict, b: dict) -> float:
    keys = set(a.keys()) | set(b.keys())
    max_delta = 0.0
    for key in keys:
        delta = abs(float(a.get(key, 0.0)) - float(b.get(key, 0.0)))
        if delta > max_delta:
            max_delta = delta
    return max_delta


def main() -> int:
    args = parse_args()

    out_a = ROOT / "evals" / "reports" / ".tmp_seed_run_a.json"
    out_b = ROOT / "evals" / "reports" / ".tmp_seed_run_b.json"

    report_a = _run_once(out_a, args.seed, args.attempts)
    report_b = _run_once(out_b, args.seed, args.attempts)

    a_score = report_a.get("scorecard", {})
    b_score = report_b.get("scorecard", {})
    score_delta = abs(float(a_score.get("total_score_0_to_100", 0.0)) - float(b_score.get("total_score_0_to_100", 0.0)))
    demis_delta = abs(float(a_score.get("demis_lens_score_0_to_50", 0.0)) - float(b_score.get("demis_lens_score_0_to_50", 0.0)))
    sundar_delta = abs(float(a_score.get("sundar_lens_score_0_to_50", 0.0)) - float(b_score.get("sundar_lens_score_0_to_50", 0.0)))
    indicator_delta = _max_indicator_delta(
        report_a.get("automated_indicators", {}),
        report_b.get("automated_indicators", {}),
    )

    stable = all(
        delta <= args.tolerance
        for delta in [score_delta, demis_delta, sundar_delta, indicator_delta]
    )
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "config": {"seed": args.seed, "attempts": args.attempts, "tolerance": args.tolerance},
        "comparison": {
            "total_score_delta": score_delta,
            "demis_delta": demis_delta,
            "sundar_delta": sundar_delta,
            "automated_indicator_max_delta": indicator_delta,
        },
        "status": "PASS" if stable else "FAIL",
    }

    for path in [out_a, out_b]:
        if path.exists():
            path.unlink()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if stable else 1


if __name__ == "__main__":
    raise SystemExit(main())
