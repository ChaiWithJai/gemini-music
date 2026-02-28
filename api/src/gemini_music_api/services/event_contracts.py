from __future__ import annotations

from typing import Any


SUPPORTED_SCHEMA_VERSIONS = {"v1"}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_event_payload(*, event_type: str, payload: dict[str, Any], schema_version: str) -> None:
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"Unsupported schema_version: {schema_version}")

    if event_type == "voice_window":
        required = ["cadence_bpm", "practice_seconds"]
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"voice_window missing required fields: {', '.join(missing)}")
        if not _is_number(payload.get("cadence_bpm")):
            raise ValueError("voice_window.cadence_bpm must be numeric")
        if not _is_number(payload.get("practice_seconds")):
            raise ValueError("voice_window.practice_seconds must be numeric")
        return

    if event_type == "partner_signal":
        if "signal_type" not in payload:
            raise ValueError("partner_signal missing required field: signal_type")
        return

    if event_type == "maha_mantra_stage_eval":
        if "stage" not in payload:
            raise ValueError("maha_mantra_stage_eval missing required field: stage")
        return
