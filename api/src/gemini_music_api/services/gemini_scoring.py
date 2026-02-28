from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from ..schemas import MahaMantraEvalOut, MahaMantraMetrics
from .bhav import LineageProfile, clamp01


@dataclass(frozen=True)
class GeminiScoringConfig:
    enabled: bool
    model: str
    api_key: str | None


def get_gemini_scoring_config() -> GeminiScoringConfig:
    enabled = os.getenv("USE_GEMINI_SCORING", "false").strip().lower() in {"1", "true", "yes"}
    model = os.getenv("GEMINI_SCORING_MODEL", os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"))
    api_key = os.getenv("GEMINI_API_KEY")
    return GeminiScoringConfig(enabled=enabled, model=model, api_key=api_key)


def _validate_model(model: str) -> bool:
    return model.startswith("gemini-3-")


def _extract_json(text: str) -> dict[str, Any] | None:
    candidates: list[str] = [text.strip()]
    if "```" in text:
        stripped = text.strip()
        if stripped.startswith("```"):
            first_nl = stripped.find("\n")
            last_fence = stripped.rfind("```")
            if first_nl != -1 and last_fence != -1 and last_fence > first_nl:
                candidates.append(stripped[first_nl + 1:last_fence].strip())

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start:end + 1])

    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _float_01(value: Any) -> float | None:
    try:
        numeric = float(value)
    except Exception:
        return None
    if numeric != numeric:
        return None
    return round(clamp01(numeric), 3)


def _normalize_payload(
    *,
    parsed: dict[str, Any],
    deterministic_eval: MahaMantraEvalOut,
    lineage: LineageProfile,
) -> dict[str, Any] | None:
    discipline = _float_01(parsed.get("discipline"))
    resonance = _float_01(parsed.get("resonance"))
    coherence = _float_01(parsed.get("coherence"))
    if discipline is None or resonance is None or coherence is None:
        return None

    composite = _float_01(parsed.get("composite"))
    if composite is None:
        composite = round(
            clamp01(
                (lineage.weights.discipline * discipline)
                + (lineage.weights.resonance * resonance)
                + (lineage.weights.coherence * coherence)
            ),
            3,
        )

    passes_golden_raw = parsed.get("passes_golden")
    passes_golden = (
        bool(passes_golden_raw)
        if isinstance(passes_golden_raw, bool)
        else bool(deterministic_eval.passes_golden)
    )

    feedback_raw = parsed.get("feedback", deterministic_eval.feedback)
    feedback: list[str] = []
    if isinstance(feedback_raw, list):
        for item in feedback_raw:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if text:
                feedback.append(text)
    if not feedback:
        feedback = list(deterministic_eval.feedback)
    feedback = feedback[:4]

    scorer_confidence = _float_01(parsed.get("scorer_confidence"))
    if scorer_confidence is None:
        scorer_confidence = _float_01(parsed.get("confidence"))
    if scorer_confidence is None:
        scorer_confidence = 0.5

    evidence_json = parsed.get("evidence_json")
    if not isinstance(evidence_json, dict):
        evidence_json = {}
    metrics_used = parsed.get("metrics_used")
    if not isinstance(metrics_used, dict):
        metrics_used = dict(deterministic_eval.metrics_used)

    return {
        "discipline": discipline,
        "resonance": resonance,
        "coherence": coherence,
        "composite": composite,
        "passes_golden": passes_golden,
        "feedback": feedback,
        "scorer_confidence": scorer_confidence,
        "evidence_json": evidence_json,
        "metrics_used": metrics_used,
    }


def try_gemini_stage_score(
    *,
    stage: str,
    lineage: LineageProfile,
    golden_profile: str,
    metrics: MahaMantraMetrics,
    deterministic_eval: MahaMantraEvalOut,
    aggregate_info: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """
    Optional Gemini-backed scoring path for stage projections.
    Returns (payload, metadata). payload is None when fallback should be used.
    """

    cfg = get_gemini_scoring_config()
    meta: dict[str, Any] = {
        "attempted": False,
        "model": None,
        "reason": "disabled",
    }
    if not cfg.enabled:
        return None, meta
    if not cfg.api_key:
        return None, {**meta, "reason": "missing_api_key"}
    if not _validate_model(cfg.model):
        return None, {**meta, "reason": "invalid_model", "model": cfg.model}

    try:
        from google import genai  # type: ignore
    except Exception:
        return None, {**meta, "reason": "sdk_unavailable", "model": cfg.model}

    meta = {"attempted": True, "model": cfg.model, "reason": "request_failed"}
    prompt = {
        "task": (
            "Score devotional mantra performance. Return JSON only. "
            "No markdown or prose."
        ),
        "scoring_axes": ["discipline", "resonance", "coherence", "composite"],
        "constraints": {
            "all_scores_range": [0.0, 1.0],
            "feedback_items_max": 4,
            "lineage_weights": {
                "discipline": lineage.weights.discipline,
                "resonance": lineage.weights.resonance,
                "coherence": lineage.weights.coherence,
            },
            "golden_profile": golden_profile,
        },
        "context": {
            "stage": stage,
            "lineage": lineage.id,
            "metrics": metrics.model_dump(),
            "aggregate_info": aggregate_info,
            "deterministic_baseline": {
                "discipline": deterministic_eval.discipline,
                "resonance": deterministic_eval.resonance,
                "coherence": deterministic_eval.coherence,
                "composite": deterministic_eval.composite,
                "passes_golden": deterministic_eval.passes_golden,
                "feedback": deterministic_eval.feedback,
            },
        },
        "response_schema": {
            "discipline": "float 0..1",
            "resonance": "float 0..1",
            "coherence": "float 0..1",
            "composite": "float 0..1",
            "passes_golden": "bool",
            "feedback": ["string"],
            "scorer_confidence": "float 0..1",
            "metrics_used": "object",
            "evidence_json": "object",
        },
    }

    try:
        client = genai.Client(api_key=cfg.api_key)
        response = client.models.generate_content(
            model=cfg.model,
            contents=json.dumps(prompt),
        )
        text = (response.text or "").strip()
    except Exception as exc:  # noqa: BLE001
        return None, {**meta, "reason": f"request_error:{str(exc)[:160]}"}

    if not text:
        return None, {**meta, "reason": "empty_response"}

    parsed = _extract_json(text)
    if parsed is None:
        return None, {**meta, "reason": "non_json_response"}

    normalized = _normalize_payload(
        parsed=parsed,
        deterministic_eval=deterministic_eval,
        lineage=lineage,
    )
    if normalized is None:
        return None, {**meta, "reason": "invalid_payload"}
    return normalized, {**meta, "reason": "ok"}
