from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GeminiAdaptationConfig:
    enabled: bool
    model: str
    api_key: str | None


def get_gemini_adaptation_config() -> GeminiAdaptationConfig:
    enabled = os.getenv("USE_GEMINI_ADAPTATION", "false").strip().lower() in {"1", "true", "yes"}
    model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    api_key = os.getenv("GEMINI_API_KEY")
    return GeminiAdaptationConfig(enabled=enabled, model=model, api_key=api_key)


def _validate_model(model: str) -> bool:
    return model.startswith("gemini-3-")


def try_gemini_adaptation(*, context: dict[str, Any]) -> dict[str, Any] | None:
    """
    Optional Gemini-backed adaptation path.
    Returns None when disabled/unavailable so caller can fall back to deterministic rules.
    """
    cfg = get_gemini_adaptation_config()
    if not cfg.enabled:
        return None
    if not cfg.api_key:
        return None
    if not _validate_model(cfg.model):
        return None

    try:
        from google import genai  # type: ignore
    except Exception:
        return None

    prompt = {
        "task": "Return devotional adaptation JSON for mantra/kirtan session.",
        "constraints": {
            "tempo_bpm_min": 48,
            "tempo_bpm_max": 128,
            "guidance_intensity_allowed": ["low", "medium", "high"],
            "key_center_allowed": ["C", "D", "E", "F", "G", "A", "B"],
        },
        "context": context,
        "response_schema": {
            "tempo_bpm": "int",
            "guidance_intensity": "low|medium|high",
            "key_center": "str",
            "reason": "str",
            "adaptation_json": "object",
        },
    }

    client = genai.Client(api_key=cfg.api_key)
    response = client.models.generate_content(
        model=cfg.model,
        contents=json.dumps(prompt),
    )
    text = (response.text or "").strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
    except Exception:
        return None

    required = {"tempo_bpm", "guidance_intensity", "key_center", "reason", "adaptation_json"}
    if not required.issubset(set(parsed.keys())):
        return None
    return parsed
