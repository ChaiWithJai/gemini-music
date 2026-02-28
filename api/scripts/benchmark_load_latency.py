from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from fastapi.testclient import TestClient

from gemini_music_api.db import Base, engine
from gemini_music_api.main import app

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "evals" / "reports" / "load_latency_benchmark.json"


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    floor = math.floor(k)
    ceil = math.ceil(k)
    if floor == ceil:
        return ordered[int(k)]
    return ordered[floor] * (ceil - k) + ordered[ceil] * (k - floor)


def _run_session_flow(base_idx: int) -> dict[str, float | bool]:
    with TestClient(app) as client:
        name = f"LoadUser-{base_idx}-{uuid.uuid4().hex[:8]}"
        user = client.post("/v1/users", json={"display_name": name})
        if user.status_code != 201:
            return {"ok": False, "latency_ms": 0.0}
        user_id = user.json()["id"]

        session = client.post(
            "/v1/sessions",
            json={
                "user_id": user_id,
                "intention": "load benchmark session",
                "mantra_key": "om_namah_shivaya",
                "mood": "anxious",
                "target_duration_minutes": 5,
            },
        )
        if session.status_code != 201:
            return {"ok": False, "latency_ms": 0.0}
        session_id = session.json()["id"]

        event = client.post(
            f"/v1/sessions/{session_id}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": f"load-event-{uuid.uuid4().hex}",
                "payload": {
                    "cadence_bpm": 80,
                    "practice_seconds": 120,
                    "heart_rate": 112,
                    "noise_level_db": 49,
                },
            },
        )
        if event.status_code != 201:
            return {"ok": False, "latency_ms": 0.0}

        t0 = time.perf_counter()
        adaptation = client.post(
            f"/v1/sessions/{session_id}/adaptations",
            json={"explicit_mood": "anxious"},
        )
        t1 = time.perf_counter()
        return {"ok": adaptation.status_code == 200, "latency_ms": (t1 - t0) * 1000.0}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Concurrent load/latency benchmark for adaptation endpoint.")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent session flows.")
    parser.add_argument("--rounds", type=int, default=2, help="Benchmark rounds.")
    parser.add_argument("--p95-target-ms", type=float, default=250.0, help="Maximum allowed p95 latency.")
    parser.add_argument("--max-error-rate", type=float, default=0.05, help="Maximum allowed error rate (0-1).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    latencies: list[float] = []
    total = 0
    failures = 0

    for round_idx in range(args.rounds):
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [pool.submit(_run_session_flow, (round_idx * args.concurrency) + i) for i in range(args.concurrency)]
            for future in as_completed(futures):
                result = future.result()
                total += 1
                if not bool(result["ok"]):
                    failures += 1
                    continue
                latencies.append(float(result["latency_ms"]))

    error_rate = (failures / total) if total else 1.0
    p50 = _percentile(latencies, 0.50)
    p95 = _percentile(latencies, 0.95)
    p99 = _percentile(latencies, 0.99)

    status = "PASS" if p95 <= args.p95_target_ms and error_rate <= args.max_error_rate else "FAIL"
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "config": {
            "concurrency": args.concurrency,
            "rounds": args.rounds,
            "p95_target_ms": args.p95_target_ms,
            "max_error_rate": args.max_error_rate,
        },
        "results": {
            "samples": len(latencies),
            "total_requests": total,
            "failures": failures,
            "error_rate": round(error_rate, 4),
            "latency_ms": {
                "p50": round(p50, 3),
                "p95": round(p95, 3),
                "p99": round(p99, 3),
                "mean": round(statistics.mean(latencies), 3) if latencies else 0.0,
            },
        },
        "status": status,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
