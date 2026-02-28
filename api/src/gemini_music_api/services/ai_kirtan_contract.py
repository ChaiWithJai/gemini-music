from __future__ import annotations

from typing import Any

REQUIRED_TOP_LEVEL = {"tempo_bpm", "guidance_intensity", "key_center", "reason", "adaptation_json"}
REQUIRED_ARRANGEMENT = {"drone_level", "percussion", "call_response"}


def verify_payload_contract(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    missing_top = [key for key in REQUIRED_TOP_LEVEL if key not in payload]
    if missing_top:
        errors.append(f"missing_top_level:{','.join(sorted(missing_top))}")

    adaptation_json = payload.get("adaptation_json")
    if not isinstance(adaptation_json, dict):
        errors.append("adaptation_json_not_object")
        return False, errors

    arrangement = adaptation_json.get("arrangement")
    if not isinstance(arrangement, dict):
        errors.append("arrangement_not_object")
    else:
        missing_arrangement = [key for key in REQUIRED_ARRANGEMENT if key not in arrangement]
        if missing_arrangement:
            errors.append(f"missing_arrangement:{','.join(sorted(missing_arrangement))}")

    coach_actions = adaptation_json.get("coach_actions")
    if not isinstance(coach_actions, list) or len(coach_actions) < 1:
        errors.append("coach_actions_missing")

    reason = payload.get("reason")
    if not isinstance(reason, str) or len(reason.strip()) < 10:
        errors.append("reason_too_short")

    return len(errors) == 0, errors


def quality_rubric_score(payload: dict[str, Any]) -> float:
    passed, errors = verify_payload_contract(payload)
    if passed:
        return 1.0
    penalty = min(0.8, 0.2 * len(errors))
    return max(0.0, 1.0 - penalty)
