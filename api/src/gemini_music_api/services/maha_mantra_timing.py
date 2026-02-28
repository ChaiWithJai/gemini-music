from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


TIMING_MARKERS_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "maha_mantra_timing_markers.v1.json"
)


@lru_cache(maxsize=1)
def load_maha_mantra_timing_markers() -> dict[str, Any]:
    raw = json.loads(TIMING_MARKERS_PATH.read_text(encoding="utf-8"))

    required_top = {
        "track_id",
        "source",
        "video_id",
        "listen_stage",
        "guided_stage",
        "call_response_stage",
        "independent_stage",
    }
    missing = sorted(required_top - set(raw.keys()))
    if missing:
        raise ValueError(f"Missing timing marker fields: {', '.join(missing)}")

    return raw

