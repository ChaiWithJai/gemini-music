from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AdaptationContext:
    mood: str | None = None
    cadence_bpm: float | None = None
    pronunciation_score: float | None = None
    flow_score: float | None = None
    heart_rate: int | None = None
    noise_level_db: float | None = None


def generate_adaptation(ctx: AdaptationContext) -> dict:
    """
    Deterministic rule engine stub for hackathon.
    Replace this function with Gemini orchestration while keeping API contract unchanged.
    """
    tempo = 72
    key_center = "C"
    guidance = "medium"
    reason_parts: list[str] = []

    if ctx.cadence_bpm is not None:
        tempo = int(max(48, min(128, round(ctx.cadence_bpm))))
        reason_parts.append(f"cadence match {tempo} bpm")

    if ctx.mood:
        mood = ctx.mood.lower()
        if mood in {"anxious", "stressed", "overwhelmed"}:
            tempo = max(52, tempo - 8)
            guidance = "high"
            key_center = "D"
            reason_parts.append("calming adjustment for anxious mood")
        elif mood in {"joyful", "energized"}:
            tempo = min(108, tempo + 8)
            guidance = "low"
            key_center = "G"
            reason_parts.append("uplift adjustment for joyful mood")
        else:
            reason_parts.append("neutral mood profile")

    if ctx.heart_rate is not None:
        if ctx.heart_rate > 110:
            tempo = max(56, tempo - 6)
            guidance = "high"
            reason_parts.append("heart rate elevated, easing tempo")
        elif ctx.heart_rate < 60:
            tempo = min(96, tempo + 4)
            reason_parts.append("heart rate low, adding gentle momentum")

    if ctx.noise_level_db is not None and ctx.noise_level_db > 65:
        guidance = "high"
        reason_parts.append("high ambient noise, increasing guidance intensity")

    if ctx.pronunciation_score is not None and ctx.pronunciation_score < 0.65:
        guidance = "high"
        reason_parts.append("pronunciation below threshold")

    if ctx.flow_score is not None and ctx.flow_score > 0.8 and guidance != "high":
        guidance = "low"
        reason_parts.append("strong flow, reducing interruptions")

    reason = "; ".join(reason_parts) if reason_parts else "default devotional adaptation"

    return {
        "tempo_bpm": tempo,
        "guidance_intensity": guidance,
        "key_center": key_center,
        "reason": reason,
        "adaptation_json": {
            "arrangement": {
                "drone_level": "medium",
                "percussion": "tabla_soft" if tempo < 80 else "tabla_groove",
                "call_response": guidance == "high",
            },
            "coach_actions": [
                "repeat_line" if guidance == "high" else "continue_flow",
                "show_pronunciation_hint" if guidance == "high" else "hide_hint",
            ],
        },
    }
