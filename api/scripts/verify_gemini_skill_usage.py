from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "verification" / "gemini_skill_rules.json"
REPORT_PATH = ROOT / "evals" / "reports" / "gemini_skill_verification.json"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def iter_code_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part.startswith(".venv") for part in path.parts):
            continue
        if any(part in {".pytest_cache", "__pycache__", "evals", "reports"} for part in path.parts):
            continue
        if path.suffix.lower() in {".py", ".md", ".json", ".ts", ".tsx", ".js"}:
            out.append(path)
    return out


def first_hits(files: list[Path], pattern: str, limit: int = 10) -> list[str]:
    hits: list[str] = []
    p = pattern.lower()
    for f in files:
        text = read_text(f).lower()
        if p in text:
            hits.append(str(f.relative_to(ROOT)))
            if len(hits) >= limit:
                break
    return hits


def main() -> int:
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    files = iter_code_files(ROOT / "src") + iter_code_files(ROOT / "scripts") + iter_code_files(ROOT / "demo")
    # Keep stable ordering for deterministic reports.
    files = sorted(set(files))

    required_patterns: list[str] = rules["required_code_patterns_any"]
    forbidden_sdk: list[str] = rules["forbidden_sdk_patterns"]
    forbidden_models: list[str] = rules["forbidden_model_patterns"]
    recommended_prefix: str = rules["recommended_models_prefix"]

    required_hits: dict[str, list[str]] = {
        p: first_hits(files, p) for p in required_patterns
    }
    required_ok = any(required_hits[p] for p in required_patterns)

    forbidden_sdk_hits: dict[str, list[str]] = {
        p: first_hits(files, p) for p in forbidden_sdk
    }
    forbidden_model_hits: dict[str, list[str]] = {
        p: first_hits(files, p) for p in forbidden_models
    }
    forbidden_ok = not any(forbidden_sdk_hits[p] for p in forbidden_sdk) and not any(
        forbidden_model_hits[p] for p in forbidden_models
    )

    # Recommended model prefix check: ensure at least one reference exists.
    recommended_model_hits = first_hits(files, recommended_prefix)
    recommended_ok = len(recommended_model_hits) > 0

    checks: list[dict[str, Any]] = [
        {
            "name": "required_sdk_or_api_pattern_present",
            "passed": required_ok,
            "details": required_hits,
        },
        {
            "name": "no_deprecated_sdk_usage",
            "passed": not any(forbidden_sdk_hits[p] for p in forbidden_sdk),
            "details": forbidden_sdk_hits,
        },
        {
            "name": "no_legacy_model_usage",
            "passed": not any(forbidden_model_hits[p] for p in forbidden_models),
            "details": forbidden_model_hits,
        },
        {
            "name": "recommended_model_prefix_used",
            "passed": recommended_ok,
            "details": {
                "prefix": recommended_prefix,
                "hits": recommended_model_hits,
            },
        },
    ]

    passed = required_ok and forbidden_ok and recommended_ok
    status = "PASS" if passed else "FAIL"

    report: dict[str, Any] = {
        "status": status,
        "passed": passed,
        "source": rules["source"],
        "skill": rules["skill"],
        "checks": checks,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote report: {REPORT_PATH}")
    print(f"Gemini skill compliance: {status}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
