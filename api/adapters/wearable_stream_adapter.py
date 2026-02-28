#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reference wearable adapter for Gemini Music starter kit.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL.")
    parser.add_argument("--session-id", required=True, help="Target session id.")
    parser.add_argument("--partner-source", default="wearable_reference", help="Partner source id.")
    parser.add_argument("--adapter-id", default="wearable_hr_stream", help="Adapter id.")
    parser.add_argument("--heart-rate", type=int, default=108, help="Heart rate payload value.")
    parser.add_argument("--cadence-bpm", type=float, default=74.0, help="Cadence BPM payload value.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = {
        "session_id": args.session_id,
        "partner_source": args.partner_source,
        "adapter_id": args.adapter_id,
        "event_type": "partner_signal",
        "client_event_id": f"wearable-{uuid.uuid4().hex}",
        "payload": {
            "signal_type": "heart_rate",
            "heart_rate": args.heart_rate,
            "cadence_bpm": args.cadence_bpm,
            "practice_seconds": 120,
        },
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(f"{args.base_url}/v1/integrations/events", json=payload)
    print(json.dumps(resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"text": resp.text}, indent=2))
    return 0 if resp.status_code < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
