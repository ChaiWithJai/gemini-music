from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Literal

from fastapi.testclient import TestClient

EvalPolicy = Literal["ALWAYS_PASSES", "USUALLY_PASSES"]


@dataclass(frozen=True)
class EvalCase:
    name: str
    policy: EvalPolicy
    run: Callable[[TestClient], dict[str, float]]


@dataclass(frozen=True)
class DimensionConfig:
    id: str
    label: str
    weight: int
    automated_keys: list[str]
    manual_key: str | None = None
    automated_weight: float = 1.0
    manual_weight: float = 0.0


DIMENSIONS: list[DimensionConfig] = [
    DimensionConfig(
        id="A_frontier_product_novelty",
        label="Frontier product novelty",
        weight=20,
        automated_keys=[
            "realtime_loop_working",
            "multi_signal_adaptation",
            "adaptation_explainability",
        ],
        manual_key="frontier_novelty_manual",
        automated_weight=0.8,
        manual_weight=0.2,
    ),
    DimensionConfig(
        id="B_user_value_proof",
        label="User value proof",
        weight=15,
        automated_keys=[
            "baseline_comparison_harness",
            "adaptive_delta_observed",
            "user_metric_projection",
            "bhav_composite_eval",
        ],
        manual_key="user_value_proof_manual",
        automated_weight=0.6,
        manual_weight=0.4,
    ),
    DimensionConfig(
        id="C_scale_readiness",
        label="Scale readiness",
        weight=15,
        automated_keys=[
            "idempotent_event_ingestion",
            "reliable_event_log",
            "realtime_loop_working",
        ],
        manual_key="scale_readiness_manual",
        automated_weight=0.8,
        manual_weight=0.2,
    ),
    DimensionConfig(
        id="D_ecosystem_leverage",
        label="Ecosystem leverage",
        weight=15,
        automated_keys=[
            "ecosystem_partner_ingestion",
            "ecosystem_webhook_surface",
            "ecosystem_export_surface",
            "ecosystem_wearable_adapter",
            "ecosystem_content_adapter",
        ],
        manual_key="ecosystem_leverage_manual",
        automated_weight=0.9,
        manual_weight=0.1,
    ),
    DimensionConfig(
        id="E_safety_privacy_rights",
        label="Safety, privacy, and rights",
        weight=15,
        automated_keys=[
            "consent_controls_working",
            "privacy_defaults_working",
            "adaptation_explainability",
        ],
        manual_key="safety_manual",
        automated_weight=0.8,
        manual_weight=0.2,
    ),
    DimensionConfig(
        id="F_measurable_business_signal",
        label="Measurable business signal",
        weight=10,
        automated_keys=[
            "business_signal_projection",
            "user_metric_projection",
            "business_kpi_projection",
            "business_experiment_ci",
            "business_cohort_export",
        ],
        manual_key="business_signal_manual",
        automated_weight=0.9,
        manual_weight=0.1,
    ),
    DimensionConfig(
        id="G_scientific_eval_rigor",
        label="Scientific/eval rigor",
        weight=10,
        automated_keys=[
            "baseline_comparison_harness",
            "idempotent_event_ingestion",
            "reliable_event_log",
            "maha_mantra_golden_pass",
            "bhav_lineage_sadhguru_pass",
            "bhav_lineage_shree_vallabhacharya_pass",
            "bhav_lineage_vaishnavism_pass",
            "eval_confidence_bounds",
            "eval_variance_reporting",
            "eval_drift_guard",
        ],
        manual_key="eval_rigor_manual",
        automated_weight=0.9,
        manual_weight=0.1,
    ),
]


DEFAULT_MANUAL_EVIDENCE: dict[str, float] = {
    "frontier_novelty_manual": 0.6,
    "user_value_proof_manual": 0.2,
    "scale_readiness_manual": 0.3,
    "ecosystem_leverage_manual": 0.2,
    "safety_manual": 0.5,
    "business_signal_manual": 0.2,
    "eval_rigor_manual": 0.5,
}


def clamp01(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(mean(values))


def load_manual_evidence(path: Path) -> dict[str, float]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(DEFAULT_MANUAL_EVIDENCE, indent=2), encoding="utf-8")
        return DEFAULT_MANUAL_EVIDENCE.copy()

    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    out: dict[str, float] = DEFAULT_MANUAL_EVIDENCE.copy()
    for k, v in raw.items():
        out[k] = clamp01(v)
    return out


def rating_from_evidence(evidence_01: float) -> float:
    return round(1.0 + (4.0 * clamp01(evidence_01)), 2)


def weighted_dimension_score(rating: float, weight: int) -> float:
    return round(weight * (rating / 5.0), 2)


def compute_scorecard(
    *,
    automated_indicators: dict[str, float],
    manual_evidence: dict[str, float],
) -> dict[str, Any]:
    dimensions: list[dict[str, Any]] = []
    total_score = 0.0

    for dim in DIMENSIONS:
        auto_values = [clamp01(automated_indicators.get(k, 0.0)) for k in dim.automated_keys]
        automated_component = safe_mean(auto_values)
        manual_component = clamp01(manual_evidence.get(dim.manual_key, 0.0)) if dim.manual_key else 0.0
        combined = (automated_component * dim.automated_weight) + (manual_component * dim.manual_weight)

        rating = rating_from_evidence(combined)
        score = weighted_dimension_score(rating, dim.weight)
        total_score += score

        dimensions.append(
            {
                "id": dim.id,
                "label": dim.label,
                "weight": dim.weight,
                "rating_1_to_5": rating,
                "weighted_score": score,
                "evidence": {
                    "automated_component_0_to_1": round(automated_component, 3),
                    "manual_component_0_to_1": round(manual_component, 3),
                    "combined_0_to_1": round(combined, 3),
                    "automated_keys": dim.automated_keys,
                    "manual_key": dim.manual_key,
                },
            }
        )

    dim_index = {d["id"]: d for d in dimensions}
    demis_score = round(
        dim_index["A_frontier_product_novelty"]["weighted_score"]
        + dim_index["G_scientific_eval_rigor"]["weighted_score"]
        + dim_index["E_safety_privacy_rights"]["weighted_score"],
        2,
    )
    sundar_score = round(
        dim_index["B_user_value_proof"]["weighted_score"]
        + dim_index["C_scale_readiness"]["weighted_score"]
        + dim_index["D_ecosystem_leverage"]["weighted_score"]
        + dim_index["F_measurable_business_signal"]["weighted_score"],
        2,
    )

    total_score = round(total_score, 2)
    priority_ready = total_score >= 85 and demis_score >= 40 and sundar_score >= 40

    return {
        "dimensions": dimensions,
        "total_score_0_to_100": total_score,
        "demis_lens_score_0_to_50": demis_score,
        "sundar_lens_score_0_to_50": sundar_score,
        "thresholds": {
            "overall_priority_min": 85,
            "demis_lens_min": 40,
            "sundar_lens_min": 40,
        },
        "priority_ready": priority_ready,
    }
