from __future__ import annotations

import math
from statistics import mean


def _sample_variance(values: list[float], center: float) -> float:
    if len(values) <= 1:
        return 0.0
    return sum((value - center) ** 2 for value in values) / (len(values) - 1)


def compare_adaptive_vs_static(*, adaptive_values: list[float], static_values: list[float]) -> dict[str, float | bool]:
    adaptive_mean = float(mean(adaptive_values))
    static_mean = float(mean(static_values))
    uplift = adaptive_mean - static_mean

    var_adaptive = _sample_variance(adaptive_values, adaptive_mean)
    var_static = _sample_variance(static_values, static_mean)
    se = math.sqrt((var_adaptive / len(adaptive_values)) + (var_static / len(static_values)))
    margin = 1.96 * se

    ci_low = uplift - margin
    ci_high = uplift + margin
    significant = ci_low > 0.0

    return {
        "adaptive_mean": round(adaptive_mean, 4),
        "static_mean": round(static_mean, 4),
        "uplift": round(uplift, 4),
        "ci95_low": round(ci_low, 4),
        "ci95_high": round(ci_high, 4),
        "significant": significant,
    }
