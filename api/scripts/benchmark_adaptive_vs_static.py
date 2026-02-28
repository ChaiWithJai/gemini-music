from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
from pathlib import Path
from statistics import mean

from fastapi.testclient import TestClient

from gemini_music_api.db import Base, engine
from gemini_music_api.main import app

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "evals" / "reports" / "adaptive_vs_static_benchmark.json"


def _ci95(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], values[0]
    m = mean(values)
    variance = sum((value - m) ** 2 for value in values) / (len(values) - 1)
    se = math.sqrt(variance / len(values))
    margin = 1.96 * se
    return m - margin, m + margin


def _create_user(client: TestClient, name: str) -> str:
    resp = client.post("/v1/users", json={"display_name": name})
    resp.raise_for_status()
    return resp.json()["id"]


def _start_session(client: TestClient, user_id: str, mood: str) -> str:
    resp = client.post(
        "/v1/sessions",
        json={
            "user_id": user_id,
            "intention": "adaptive-vs-static benchmark trial",
            "mantra_key": "maha_mantra_hare_krishna_hare_rama",
            "mood": mood,
            "target_duration_minutes": 8,
        },
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _run_trial(client: TestClient, trial_idx: int, rng: random.Random) -> dict[str, float]:
    user_id = _create_user(client, f"Benchmark User {trial_idx}")

    cadence = rng.uniform(76, 88)
    heart_rate = rng.randint(108, 126)
    noise = rng.uniform(44, 58)

    adaptive_session = _start_session(client, user_id, "anxious")
    event_adaptive = client.post(
        f"/v1/sessions/{adaptive_session}/events",
        json={
            "event_type": "voice_window",
            "client_event_id": f"bench-adaptive-{trial_idx}",
            "payload": {
                "cadence_bpm": cadence,
                "practice_seconds": 360,
                "heart_rate": heart_rate,
                "noise_level_db": noise,
                "pronunciation_score": 0.68,
                "flow_score": 0.64,
            },
        },
    )
    event_adaptive.raise_for_status()
    adaptive = client.post(
        f"/v1/sessions/{adaptive_session}/adaptations",
        json={"explicit_mood": "anxious"},
    )
    adaptive.raise_for_status()
    adaptive_body = adaptive.json()

    static_session = _start_session(client, user_id, "neutral")
    event_static = client.post(
        f"/v1/sessions/{static_session}/events",
        json={
            "event_type": "voice_window",
            "client_event_id": f"bench-static-{trial_idx}",
            "payload": {
                "cadence_bpm": cadence,
                "practice_seconds": 360,
                "noise_level_db": noise,
                "pronunciation_score": 0.68,
                "flow_score": 0.64,
            },
        },
    )
    event_static.raise_for_status()
    static = client.post(
        f"/v1/sessions/{static_session}/adaptations",
        json={"explicit_mood": "neutral"},
    )
    static.raise_for_status()
    static_body = static.json()

    tempo_uplift = float(static_body["tempo_bpm"]) - float(adaptive_body["tempo_bpm"])
    guidance_uplift = float(adaptive_body["guidance_intensity"] == "high") - float(
        static_body["guidance_intensity"] == "high"
    )
    explainability_uplift = (
        float(len(str(adaptive_body["reason"])))
        - float(len(str(static_body["reason"])))
    )
    return {
        "tempo_uplift_bpm": tempo_uplift,
        "guidance_uplift": guidance_uplift,
        "explainability_uplift_chars": explainability_uplift,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Adaptive-vs-static benchmark with CI95.")
    parser.add_argument("--runs", type=int, default=30, help="Number of benchmark trials.")
    parser.add_argument("--seed", type=int, default=202603, help="Seed for deterministic sampling.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    tempo_uplifts: list[float] = []
    guidance_uplifts: list[float] = []
    explainability_uplifts: list[float] = []

    with TestClient(app) as client:
        for idx in range(args.runs):
            trial = _run_trial(client, idx, rng)
            tempo_uplifts.append(trial["tempo_uplift_bpm"])
            guidance_uplifts.append(trial["guidance_uplift"])
            explainability_uplifts.append(trial["explainability_uplift_chars"])

    metrics = {
        "tempo_uplift_bpm": tempo_uplifts,
        "guidance_uplift": guidance_uplifts,
        "explainability_uplift_chars": explainability_uplifts,
    }
    summary: dict[str, dict[str, float | bool]] = {}
    significant_positive = 0
    for name, values in metrics.items():
        low, high = _ci95(values)
        avg = mean(values) if values else 0.0
        significant = low > 0
        if significant:
            significant_positive += 1
        summary[name] = {
            "mean": round(avg, 4),
            "ci95_low": round(low, 4),
            "ci95_high": round(high, 4),
            "significant_positive": significant,
        }

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "config": {"runs": args.runs, "seed": args.seed},
        "metrics": summary,
        "success": {
            "significant_positive_metrics": significant_positive,
            "meets_target": significant_positive >= 2,
        },
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["success"]["meets_target"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
