from __future__ import annotations

import math
from dataclasses import dataclass


def clamp01(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _norm_rating_1_to_5(value: float | int | None) -> float:
    if value is None:
        return 0.5
    return clamp01((float(value) - 1.0) / 4.0)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values: list[float], mean: float) -> float:
    if len(values) <= 1:
        return 0.0
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


def _cadence_consistency(cadences: list[float]) -> float:
    """
    Converts cadence variability to [0,1], optimized for lightweight hackathon evals.
    """
    if not cadences:
        return 0.5
    if len(cadences) == 1:
        return 0.8
    m = _mean(cadences)
    if m <= 0:
        return 0.5
    cv = _std(cadences, m) / m
    return clamp01(1.0 - (cv * 2.0))


@dataclass(frozen=True)
class BhavWeights:
    discipline: float
    resonance: float
    coherence: float


@dataclass(frozen=True)
class LineageProfile:
    id: str
    aliases: set[str]
    mantra_aliases: set[str]
    thresholds: dict[str, float]
    weights: BhavWeights


LINEAGE_PROFILES: dict[str, LineageProfile] = {
    "vaishnavism": LineageProfile(
        id="vaishnavism",
        aliases={"vaishnavism", "vashnavism", "vaishnava"},
        mantra_aliases={
            "maha_mantra",
            "hare_krishna_hare_rama",
            "maha_mantra_hare_krishna_hare_rama",
        },
        thresholds={
            "discipline": 0.75,
            "resonance": 0.72,
            "coherence": 0.72,
            "composite": 0.75,
        },
        weights=BhavWeights(discipline=0.34, resonance=0.33, coherence=0.33),
    ),
    "sadhguru": LineageProfile(
        id="sadhguru",
        aliases={"sadhguru", "isha", "isha_foundation"},
        mantra_aliases={
            "maha_mantra",
            "hare_krishna_hare_rama",
            "maha_mantra_hare_krishna_hare_rama",
        },
        thresholds={
            "discipline": 0.78,
            "resonance": 0.70,
            "coherence": 0.70,
            "composite": 0.76,
        },
        weights=BhavWeights(discipline=0.40, resonance=0.30, coherence=0.30),
    ),
    "shree_vallabhacharya": LineageProfile(
        id="shree_vallabhacharya",
        aliases={"shree_vallabhacharya", "vallabhacharya", "pushtimarg"},
        mantra_aliases={
            "maha_mantra",
            "hare_krishna_hare_rama",
            "maha_mantra_hare_krishna_hare_rama",
        },
        thresholds={
            "discipline": 0.73,
            "resonance": 0.76,
            "coherence": 0.72,
            "composite": 0.76,
        },
        weights=BhavWeights(discipline=0.30, resonance=0.40, coherence=0.30),
    ),
}


DEFAULT_LINEAGE_ID = "vaishnavism"
DEFAULT_GOLDEN_PROFILE = "maha_mantra_v1"


def resolve_lineage(lineage_name: str | None) -> LineageProfile:
    if not lineage_name:
        return LINEAGE_PROFILES[DEFAULT_LINEAGE_ID]
    key = lineage_name.strip().lower()
    for profile in LINEAGE_PROFILES.values():
        if key in profile.aliases:
            return profile
    raise ValueError(f"Unsupported lineage: {lineage_name}")


def _is_maha_mantra_profile_match(mantra_key: str | None, profile: LineageProfile) -> bool:
    if not mantra_key:
        return False
    return mantra_key.strip().lower() in profile.mantra_aliases


def compute_bhav(
    *,
    mantra_key: str | None,
    target_duration_minutes: int,
    summary: dict,
    event_payloads: list[dict],
    lineage: LineageProfile,
    golden_profile: str = DEFAULT_GOLDEN_PROFILE,
) -> dict:
    practice_minutes = float(summary.get("practice_minutes", 0.0))
    completed_goal = bool(summary.get("completed_goal", False))
    flow_score = clamp01(summary.get("avg_flow_score", 0.0))
    pronunciation_score = clamp01(summary.get("avg_pronunciation_score", 0.0))
    user_value_norm = _norm_rating_1_to_5(summary.get("user_value_rating"))

    cadence_values = []
    adaptation_helpfulness = []
    for payload in event_payloads:
        if payload.get("cadence_bpm") is not None:
            cadence_values.append(float(payload["cadence_bpm"]))
        if payload.get("adaptation_helpful") is not None:
            adaptation_helpfulness.append(1.0 if bool(payload["adaptation_helpful"]) else 0.0)

    cadence_consistency = _cadence_consistency(cadence_values)
    adaptation_acceptance = _mean(adaptation_helpfulness) if adaptation_helpfulness else 0.5
    duration_ratio = clamp01(practice_minutes / max(1.0, float(target_duration_minutes)))

    discipline = clamp01((0.45 * duration_ratio) + (0.35 * (1.0 if completed_goal else 0.0)) + (0.20 * cadence_consistency))
    resonance = clamp01((0.55 * flow_score) + (0.25 * user_value_norm) + (0.20 * adaptation_acceptance))
    coherence = clamp01((0.70 * pronunciation_score) + (0.30 * cadence_consistency))

    composite = clamp01(
        (lineage.weights.discipline * discipline)
        + (lineage.weights.resonance * resonance)
        + (lineage.weights.coherence * coherence)
    )

    profile_match = golden_profile == DEFAULT_GOLDEN_PROFILE and _is_maha_mantra_profile_match(
        mantra_key, lineage
    )
    thresholds = lineage.thresholds if profile_match else {}

    gaps: dict[str, float] = {}
    passes_golden = False
    if profile_match:
        gaps = {
            "discipline": round(discipline - thresholds["discipline"], 3),
            "resonance": round(resonance - thresholds["resonance"], 3),
            "coherence": round(coherence - thresholds["coherence"], 3),
            "composite": round(composite - thresholds["composite"], 3),
        }
        passes_golden = all(v >= 0.0 for v in gaps.values())

    return {
        "discipline": round(discipline, 3),
        "resonance": round(resonance, 3),
        "coherence": round(coherence, 3),
        "composite": round(composite, 3),
        "passes_golden": passes_golden,
        "detail_json": {
            "lineage_id": lineage.id,
            "golden_profile": golden_profile,
            "profile_match": profile_match,
            "thresholds": thresholds,
            "gaps": gaps,
            "signals": {
                "duration_ratio": round(duration_ratio, 3),
                "completed_goal": completed_goal,
                "cadence_consistency": round(cadence_consistency, 3),
                "flow_score": round(flow_score, 3),
                "pronunciation_score": round(pronunciation_score, 3),
                "user_value_norm": round(user_value_norm, 3),
                "adaptation_acceptance": round(adaptation_acceptance, 3),
            },
            "weights": {
                "discipline": lineage.weights.discipline,
                "resonance": lineage.weights.resonance,
                "coherence": lineage.weights.coherence,
            },
        },
    }
