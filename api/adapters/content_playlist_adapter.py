#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reference content adapter for Gemini Music starter kit.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL.")
    parser.add_argument("--session-id", required=True, help="Target session id.")
    parser.add_argument("--target-url", default="https://example.org/hook", help="Webhook target URL.")
    parser.add_argument("--adapter-id", default="content_playlist_sync", help="Adapter id.")
    parser.add_argument("--playlist-id", default="starter_kit_playlist", help="Playlist id for signal payload.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with httpx.Client(timeout=20.0) as client:
        sub_resp = client.post(
            f"{args.base_url}/v1/integrations/webhooks",
            json={
                "target_url": args.target_url,
                "adapter_id": "content_playlist_adapter",
                "event_types": ["session_ended", "adaptation_applied"],
                "is_active": True,
            },
        )
        signal_resp = client.post(
            f"{args.base_url}/v1/integrations/events",
            json={
                "session_id": args.session_id,
                "partner_source": "content_reference",
                "adapter_id": args.adapter_id,
                "event_type": "partner_signal",
                "client_event_id": f"content-{uuid.uuid4().hex}",
                "payload": {
                    "signal_type": "playlist_sync",
                    "playlist_id": args.playlist_id,
                    "cadence_bpm": 72,
                    "practice_seconds": 120,
                },
            },
        )

    result = {
        "webhook_subscription_status": sub_resp.status_code,
        "signal_status": signal_resp.status_code,
    }
    if sub_resp.headers.get("content-type", "").startswith("application/json"):
        result["webhook_subscription"] = sub_resp.json()
    if signal_resp.headers.get("content-type", "").startswith("application/json"):
        result["signal_response"] = signal_resp.json()
    print(json.dumps(result, indent=2))
    return 0 if sub_resp.status_code < 400 and signal_resp.status_code < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
