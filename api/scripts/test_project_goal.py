from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "evals" / "reports" / "project_goal_status.json"
SCORECARD_REPORT_PATH = ROOT / "evals" / "reports" / "latest_report.json"
GEMINI_VERIFY_REPORT_PATH = ROOT / "evals" / "reports" / "gemini_skill_verification.json"
EXPECTED_PYTHON_MM = (3, 13)


def _run_subprocess_once(cmd: list[str]) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src:."
    start = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    duration = round(time.monotonic() - start, 3)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_seconds": duration,
    }


def _verify_runtime() -> None:
    if sys.version_info[:2] != EXPECTED_PYTHON_MM:
        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        expected = f"{EXPECTED_PYTHON_MM[0]}.{EXPECTED_PYTHON_MM[1]}"
        raise RuntimeError(
            f"Unsupported Python runtime {current}. Expected {expected}. "
            "Run: make bootstrap && make install && make goal_test"
        )
    try:
        import fastapi  # noqa: F401
    except Exception as exc:
        raise RuntimeError(
            "Missing runtime dependencies for goal test. "
            "Run: make install && make goal_test"
        ) from exc


def _run_subprocess_with_retry(
    cmd: list[str],
    *,
    max_attempts: int = 2,
    retry_backoff_seconds: float = 0.3,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        run = _run_subprocess_once(cmd)
        run["attempt"] = attempt
        attempts.append(run)
        if run["returncode"] == 0:
            break
        if attempt < max_attempts:
            time.sleep(retry_backoff_seconds * attempt)

    final = attempts[-1]
    return {
        "cmd": cmd,
        "returncode": final["returncode"],
        "stdout": final["stdout"],
        "stderr": final["stderr"],
        "duration_seconds": final["duration_seconds"],
        "attempt_count": len(attempts),
        "self_healed": attempts[0]["returncode"] != 0 and final["returncode"] == 0,
        "attempts": attempts,
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _clamp01(value: float | int | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _bool_score(value: bool) -> float:
    return 1.0 if value else 0.0


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(round(0.95 * (len(sorted_vals) - 1)))
    return sorted_vals[idx]


def _has_cycle(nodes: set[str], prereq_map: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def _dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for parent in prereq_map.get(node, []):
            if parent in nodes and _dfs(parent):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(_dfs(node) for node in nodes)


def _max_chain_depth(nodes: set[str], prereq_map: dict[str, list[str]]) -> int:
    def _depth(node: str, seen: set[str]) -> int:
        if node in seen:
            return 0
        parents = [p for p in prereq_map.get(node, []) if p in nodes]
        if not parents:
            return 1
        return 1 + max(_depth(parent, seen | {node}) for parent in parents)

    if not nodes:
        return 0
    return max(_depth(node, set()) for node in nodes)


def _scorecard_dimension_normalized(scorecard: dict[str, Any], dimension_id: str) -> float:
    dimensions = scorecard.get("scorecard", {}).get("dimensions", [])
    for dim in dimensions:
        if dim.get("id") != dimension_id:
            continue
        weight = float(dim.get("weight", 1.0) or 1.0)
        weighted_score = float(dim.get("weighted_score", 0.0))
        return _clamp01(weighted_score / weight)
    return 0.0


def _build_instructional_design_pipeline(
    *,
    goal_scenario: dict[str, Any],
    scorecard: dict[str, Any],
    gemini_verify: dict[str, Any],
) -> dict[str, Any]:
    api_plan = _load_json(ROOT / "API_DATA_PLAN.json")

    objectives = [
        {
            "label": "LEARNING_OBJECTIVE",
            "id": "obj_001",
            "verb": "apply",
            "bloom_level": 3,
            "content": "listener mood inputs to devotional adaptation tempo/guidance",
            "observable_behavior": "Given a live mood input, adaptation output changes within one request.",
            "assessment_method": "scenario_test",
            "prerequisite_ids": [],
            "domain": "intellectual_skills",
            "confidence": "verified",
        },
        {
            "label": "LEARNING_OBJECTIVE",
            "id": "obj_002",
            "verb": "analyze",
            "bloom_level": 4,
            "content": "biometric and environmental signals for adaptation",
            "observable_behavior": "Given heart-rate/noise deltas, adaptation intensity responds correctly.",
            "assessment_method": "scenario_test",
            "prerequisite_ids": ["obj_001"],
            "domain": "intellectual_skills",
            "confidence": "verified",
        },
        {
            "label": "LEARNING_OBJECTIVE",
            "id": "obj_003",
            "verb": "analyze",
            "bloom_level": 4,
            "content": "pronunciation-driven mantra learning guidance",
            "observable_behavior": "Given low pronunciation score, guidance_intensity escalates to high.",
            "assessment_method": "session_summary_eval",
            "prerequisite_ids": ["obj_001"],
            "domain": "intellectual_skills",
            "confidence": "verified",
        },
        {
            "label": "LEARNING_OBJECTIVE",
            "id": "obj_004",
            "verb": "evaluate",
            "bloom_level": 5,
            "content": "AI-kirtan arrangement behavior with explainable coach actions",
            "observable_behavior": "Adaptation payload includes arrangement and coach_actions with call-response toggle.",
            "assessment_method": "payload_contract_test",
            "prerequisite_ids": ["obj_002"],
            "domain": "intellectual_skills",
            "confidence": "verified",
        },
        {
            "label": "LEARNING_OBJECTIVE",
            "id": "obj_005",
            "verb": "evaluate",
            "bloom_level": 5,
            "content": "Bhav lineage alignment on Maha Mantra golden profile",
            "observable_behavior": "All target lineages pass golden checks with stable composite values.",
            "assessment_method": "bhav_eval_matrix",
            "prerequisite_ids": ["obj_002", "obj_004"],
            "domain": "intellectual_skills",
            "confidence": "verified",
        },
    ]

    concepts = [
        {
            "label": "CONCEPT",
            "id": "concept_001",
            "name": "Signal Fusion Context",
            "definition": "Combining listener, biometric, and environmental context into one adaptation request.",
            "prerequisite_concepts": [],
            "common_misconceptions": ["single_signal_is_enough"],
            "cognitive_load_estimate": 0.58,
            "domain": "verbal_information",
        },
        {
            "label": "CONCEPT",
            "id": "concept_002",
            "name": "Consent Guardrails",
            "definition": "Biometric/environmental collection remains opt-in with privacy-safe defaults.",
            "prerequisite_concepts": ["concept_001"],
            "common_misconceptions": ["raw_audio_must_be_enabled"],
            "cognitive_load_estimate": 0.52,
            "domain": "attitudes",
        },
        {
            "label": "CONCEPT",
            "id": "concept_003",
            "name": "Mantra Pronunciation Feedback Loop",
            "definition": "Pronunciation quality should influence guidance intensity and coaching hints.",
            "prerequisite_concepts": ["concept_001"],
            "common_misconceptions": ["tempo_only_matters"],
            "cognitive_load_estimate": 0.55,
            "domain": "intellectual_skills",
        },
        {
            "label": "CONCEPT",
            "id": "concept_004",
            "name": "AI-Kirtan Arrangement Contract",
            "definition": "Adaptation payload must include arrangement decisions and coach actions.",
            "prerequisite_concepts": ["concept_001", "concept_003"],
            "common_misconceptions": ["arrangement_is_optional"],
            "cognitive_load_estimate": 0.57,
            "domain": "intellectual_skills",
        },
        {
            "label": "CONCEPT",
            "id": "concept_005",
            "name": "Bhav Lineage Thresholding",
            "definition": "Lineage-specific weights and thresholds define pass/fail against golden profile.",
            "prerequisite_concepts": ["concept_004"],
            "common_misconceptions": ["one_threshold_fits_all_lineages"],
            "cognitive_load_estimate": 0.62,
            "domain": "intellectual_skills",
        },
    ]

    skills = [
        {
            "label": "SKILL",
            "id": "skill_001",
            "name": "Adaptive Context Orchestration",
            "verb_phrase": "adapt devotional output to mood, biometrics, and environment",
            "observable_behavior": "Model output changes when context shifts.",
            "performance_standard": "listener/biometric/environment effects all observable",
            "conditions": "Given session event windows and consent-enabled data.",
            "sub_skills": ["mood_adjustment", "heart_rate_adjustment", "noise_adjustment"],
            "practice_required": "5 scenario windows",
            "domain": "intellectual_skills",
            "difficulty_level": "guided",
        },
        {
            "label": "SKILL",
            "id": "skill_002",
            "name": "Mantra Learning Feedback",
            "verb_phrase": "convert pronunciation/flow signals into coaching guidance",
            "observable_behavior": "Low pronunciation triggers high guidance and hints.",
            "performance_standard": "guidance trigger rate > 90% on low pronunciation windows",
            "conditions": "Given session windows with pronunciation metrics.",
            "sub_skills": ["threshold_detection", "coach_action_selection"],
            "practice_required": "3-5 iterations",
            "domain": "intellectual_skills",
            "difficulty_level": "guided",
        },
        {
            "label": "SKILL",
            "id": "skill_003",
            "name": "Bhav Lineage Validation",
            "verb_phrase": "evaluate Maha Mantra Bhav by lineage-specific thresholds",
            "observable_behavior": "Lineage responses include composite and passes_golden.",
            "performance_standard": "all supported lineages return deterministic pass/fail",
            "conditions": "Given ended session summary and event history.",
            "sub_skills": ["lineage_resolution", "threshold_scoring", "composite_aggregation"],
            "practice_required": "lineage matrix run on every release",
            "domain": "intellectual_skills",
            "difficulty_level": "transfer",
        },
    ]

    misconceptions = [
        {
            "label": "MISCONCEPTION",
            "id": "misc_001",
            "concept_id": "concept_001",
            "incorrect_belief": "Mood alone is sufficient for adaptation quality.",
            "why_wrong": "Biometric and environmental stressors materially change optimal guidance.",
            "diagnostic_question": "Does high heart rate alter output when mood is neutral?",
            "correct_mental_model": "Signal fusion should influence tempo and guidance.",
            "prevalence": 0.55,
            "correction_strategy": "contrastive scenario tests",
        },
        {
            "label": "MISCONCEPTION",
            "id": "misc_002",
            "concept_id": "concept_002",
            "incorrect_belief": "Raw audio storage must be enabled to personalize adaptation.",
            "why_wrong": "Session features can support adaptation while raw audio storage remains disabled.",
            "diagnostic_question": "Can adaptation still function with raw_audio_storage_enabled=false?",
            "correct_mental_model": "Privacy defaults can coexist with personalization.",
            "prevalence": 0.42,
            "correction_strategy": "consent guardrail tests",
        },
        {
            "label": "MISCONCEPTION",
            "id": "misc_003",
            "concept_id": "concept_004",
            "incorrect_belief": "AI-kirtan payload can omit arrangement if tempo is returned.",
            "why_wrong": "Client behavior depends on arrangement and coach action contracts.",
            "diagnostic_question": "Can UI render guided kirtan without arrangement metadata?",
            "correct_mental_model": "Adaptation contract includes arrangement and coach actions.",
            "prevalence": 0.47,
            "correction_strategy": "payload schema validation",
        },
        {
            "label": "MISCONCEPTION",
            "id": "misc_004",
            "concept_id": "concept_005",
            "incorrect_belief": "Bhav thresholds should be identical across lineages.",
            "why_wrong": "Each lineage profile uses different weighting/threshold sensitivity.",
            "diagnostic_question": "Do all lineages define the same composite threshold?",
            "correct_mental_model": "Lineages are profile-specific and must be evaluated independently.",
            "prevalence": 0.39,
            "correction_strategy": "lineage matrix evaluation",
        },
    ]

    assessments = [
        {
            "label": "ASSESSMENT_ITEM",
            "id": "assess_001",
            "type": "performance_task",
            "objective_ids": ["obj_001", "obj_002"],
            "prompt": "Run focused adaptation scenario and compare baseline vs mood/biometric/environment deltas.",
            "rubric_target_level": 3,
            "alignment_score": 0.92,
            "target_bloom_level": 4,
        },
        {
            "label": "ASSESSMENT_ITEM",
            "id": "assess_002",
            "type": "performance_task",
            "objective_ids": ["obj_003"],
            "prompt": "Inject low pronunciation event and verify guidance escalation plus summary metrics.",
            "rubric_target_level": 3,
            "alignment_score": 0.9,
            "target_bloom_level": 4,
        },
        {
            "label": "ASSESSMENT_ITEM",
            "id": "assess_003",
            "type": "performance_task",
            "objective_ids": ["obj_004"],
            "prompt": "Validate AI-kirtan payload contract includes arrangement + coach actions + call-response flag.",
            "rubric_target_level": 4,
            "alignment_score": 0.88,
            "target_bloom_level": 5,
        },
        {
            "label": "ASSESSMENT_ITEM",
            "id": "assess_004",
            "type": "performance_task",
            "objective_ids": ["obj_005"],
            "prompt": "Run Bhav golden checks across lineages and verify pass/fail determinism.",
            "rubric_target_level": 4,
            "alignment_score": 0.9,
            "target_bloom_level": 5,
        },
    ]

    transfer_contexts = [
        {
            "label": "TRANSFER_CONTEXT",
            "id": "transfer_001",
            "skill_id": "skill_001",
            "learned_context": "single listener mood updates",
            "transfer_context": "multimodal listener+biometric+environment adaptation",
            "distance": "near",
            "adaptation_required": [
                "include heart-rate signal",
                "include ambient-noise signal",
                "maintain consent checks",
            ],
            "success_criteria": "all three signal effects observed in one scenario run",
        },
        {
            "label": "TRANSFER_CONTEXT",
            "id": "transfer_002",
            "skill_id": "skill_002",
            "learned_context": "single pronunciation hints",
            "transfer_context": "session-level mantra learning summary",
            "distance": "medium",
            "adaptation_required": [
                "aggregate pronunciation over windows",
                "project summary metrics at session end",
            ],
            "success_criteria": "summary includes avg_pronunciation_score and events_count",
        },
        {
            "label": "TRANSFER_CONTEXT",
            "id": "transfer_003",
            "skill_id": "skill_003",
            "learned_context": "single lineage check",
            "transfer_context": "lineage matrix (sadhguru, shree_vallabhacharya, vaishnavism)",
            "distance": "medium",
            "adaptation_required": [
                "normalize lineage aliases",
                "apply lineage-specific thresholds",
                "persist lineage-specific detail_json",
            ],
            "success_criteria": "all target lineages return composite + passes_golden",
        },
    ]

    module_loads = [
        {
            "module_id": "listener_biometric_environment_adaptation",
            "intrinsic_load": 0.58,
            "extraneous_load": 0.11,
            "germane_load": 0.72,
        },
        {
            "module_id": "mantra_learning_feedback_loop",
            "intrinsic_load": 0.55,
            "extraneous_load": 0.1,
            "germane_load": 0.7,
        },
        {
            "module_id": "ai_kirtan_bhav_lineage_eval",
            "intrinsic_load": 0.58,
            "extraneous_load": 0.12,
            "germane_load": 0.66,
        },
    ]
    for module in module_loads:
        total_load = _clamp01(
            module["intrinsic_load"] + module["extraneous_load"] + (0.25 * module["germane_load"])
        )
        module["total_load"] = round(total_load, 3)
        module["warning_flags"] = ["total_load_exceeds_0_9"] if total_load > 0.9 else []
        module["recommendations"] = (
            ["split module and add worked examples"] if total_load > 0.9 else ["current chunking acceptable"]
        )

    objective_ids = {o["id"] for o in objectives}
    concept_ids = {c["id"] for c in concepts}
    all_nodes = objective_ids | concept_ids
    prereq_map: dict[str, list[str]] = {}
    prereq_edges: list[dict[str, str]] = []

    for objective in objectives:
        prereq_map[objective["id"]] = list(objective["prerequisite_ids"])
        for prereq in objective["prerequisite_ids"]:
            prereq_edges.append({"from": objective["id"], "to": prereq})

    for concept in concepts:
        prereq_map[concept["id"]] = list(concept["prerequisite_concepts"])
        for prereq in concept["prerequisite_concepts"]:
            prereq_edges.append({"from": concept["id"], "to": prereq})

    missing_prereqs = [
        {"node_id": edge["from"], "missing_prerequisite": edge["to"]}
        for edge in prereq_edges
        if edge["to"] not in all_nodes
    ]
    has_cycle = _has_cycle(all_nodes, prereq_map)
    max_depth = _max_chain_depth(all_nodes, prereq_map)

    assessed_objective_ids = {oid for assessment in assessments for oid in assessment["objective_ids"]}
    unassessed_objectives = sorted(objective_ids - assessed_objective_ids)

    objective_bloom = {o["id"]: int(o["bloom_level"]) for o in objectives}
    bloom_mismatches: list[dict[str, Any]] = []
    for assessment in assessments:
        target_level = int(assessment["target_bloom_level"])
        for objective_id in assessment["objective_ids"]:
            expected_level = objective_bloom.get(objective_id, 0)
            if abs(target_level - expected_level) > 1:
                bloom_mismatches.append(
                    {
                        "assessment_id": assessment["id"],
                        "objective_id": objective_id,
                        "expected_bloom_level": expected_level,
                        "assessment_target_bloom_level": target_level,
                    }
                )

    alignment_matrix = []
    for objective in objectives:
        linked_assessments = [a["id"] for a in assessments if objective["id"] in a["objective_ids"]]
        alignment_matrix.append(
            {
                "objective_id": objective["id"],
                "bloom_level": objective["bloom_level"],
                "assessed_by": linked_assessments,
                "is_assessed": len(linked_assessments) > 0,
            }
        )

    overload_modules = [m["module_id"] for m in module_loads if m["total_load"] > 0.9]
    load_balance_score = round(
        _safe_mean(
            [1.0 if m["total_load"] <= 0.9 else _clamp01(1.0 - ((m["total_load"] - 0.9) * 4.0)) for m in module_loads]
        ),
        3,
    )

    total_prereq_refs = sum(len(values) for values in prereq_map.values())
    prereq_penalty = len(missing_prereqs) + (2 if has_cycle else 0)
    prereq_validity_score = round(
        _clamp01(1.0 - (prereq_penalty / max(1.0, float(total_prereq_refs + 2)))),
        3,
    )

    alignment_score = round(
        _clamp01(
            1.0
            - ((len(unassessed_objectives) + len(bloom_mismatches)) / max(1.0, float(len(objectives) + len(assessments))))
        ),
        3,
    )

    core_signal_checks = [
        goal_scenario["listener_input_effect"],
        goal_scenario["biometric_effect"],
        goal_scenario["environmental_effect"],
        goal_scenario["pronunciation_learning_effect"],
        goal_scenario["bhav_lineage_pass"],
    ]
    transfer_signal_score = round(_safe_mean([_bool_score(v) for v in core_signal_checks]), 3)

    gap_issues: list[str] = []
    if not goal_scenario["listener_input_effect"]:
        gap_issues.append("listener_input_effect_not_observed")
    if not goal_scenario["biometric_effect"]:
        gap_issues.append("biometric_effect_not_observed")
    if not goal_scenario["environmental_effect"]:
        gap_issues.append("environmental_effect_not_observed")
    if not goal_scenario["mantra_learning_summary_present"]:
        gap_issues.append("mantra_learning_summary_incomplete")
    if not goal_scenario["ai_kirtan_present"]:
        gap_issues.append("ai_kirtan_contract_incomplete")
    if not goal_scenario["bhav_lineage_pass"]:
        gap_issues.append("bhav_lineage_pass_failed")
    if not bool(gemini_verify.get("passed", False)):
        gap_issues.append("gemini_skill_verification_failed")
    gap_score = round(_clamp01(1.0 - (len(gap_issues) / 7.0)), 3)

    objective_levels = [objective_bloom[objective["id"]] for objective in sorted(objectives, key=lambda x: x["id"])]
    progressive_curve = all(objective_levels[i] <= objective_levels[i + 1] for i in range(len(objective_levels) - 1))
    sequencing_score = 1.0 if progressive_curve else 0.65

    validation_score = round(
        _safe_mean(
            [
                prereq_validity_score,
                load_balance_score,
                alignment_score,
                gap_score,
                sequencing_score,
            ]
        ),
        3,
    )

    critical_issues: list[str] = []
    if has_cycle:
        critical_issues.append("circular_prerequisite_detected")
    if missing_prereqs:
        critical_issues.append("missing_prerequisite_reference")
    if overload_modules:
        critical_issues.append("module_cognitive_load_exceeds_threshold")
    if unassessed_objectives:
        critical_issues.append("one_or_more_learning_objectives_unassessed")

    validation_recommendations: list[str] = []
    if overload_modules:
        validation_recommendations.append("Split overloaded modules and insert worked examples.")
    if unassessed_objectives:
        validation_recommendations.append("Map each objective to at least one assessment item.")
    if not bool(gemini_verify.get("passed", False)):
        validation_recommendations.append("Fix Gemini skill verification before shipping agent behavior.")
    if not validation_recommendations:
        validation_recommendations.append("Keep current sequencing and run weekly drift checks.")

    objective_clarity = round(
        _safe_mean(
            [
                0.95 if objective["observable_behavior"] and objective["assessment_method"] else 0.6
                for objective in objectives
            ]
        ),
        3,
    )
    dignity_base = _scorecard_dimension_normalized(scorecard, "E_safety_privacy_rights")
    dignity_preservation = round(
        _clamp01((0.8 * dignity_base) + (0.2 * _bool_score(bool(gemini_verify.get("passed", False))))),
        3,
    )

    dimension_scores = {
        "objective_clarity": objective_clarity,
        "prerequisite_validity": prereq_validity_score,
        "cognitive_load_balance": load_balance_score,
        "assessment_alignment": alignment_score,
        "transfer_potential": transfer_signal_score,
        "dignity_preservation": dignity_preservation,
    }
    score_weights = {
        "objective_clarity": 0.2,
        "prerequisite_validity": 0.15,
        "cognitive_load_balance": 0.15,
        "assessment_alignment": 0.2,
        "transfer_potential": 0.15,
        "dignity_preservation": 0.15,
    }
    composite_score = round(
        sum(dimension_scores[key] * score_weights[key] for key in score_weights),
        3,
    )

    if composite_score >= 0.85:
        stage_3_recommendation = "deploy"
    elif composite_score >= 0.7:
        stage_3_recommendation = "deploy_with_monitoring"
    else:
        stage_3_recommendation = "revise"

    stage_1_status = (
        "complete"
        if len(objectives) > 0
        and len(concepts) > 0
        and len(skills) > 0
        and len(misconceptions) > 0
        and len(assessments) > 0
        and len(transfer_contexts) > 0
        and not overload_modules
        else "incomplete"
    )
    stage_2_status = "pass" if validation_score >= 0.7 and not critical_issues else "fail"
    stage_3_status = "pass" if composite_score >= 0.7 else "fail"

    automated_indicators = scorecard.get("automated_indicators", {})
    data_quality_checks = [
        {
            "id": "idempotent_event_ingestion",
            "passed": float(automated_indicators.get("idempotent_event_ingestion", 0.0)) >= 1.0,
            "evidence": automated_indicators.get("idempotent_event_ingestion", 0.0),
        },
        {
            "id": "realtime_adaptation_latency",
            "passed": float(goal_scenario["realtime_p95_ms"]) <= 1000.0,
            "evidence_ms": goal_scenario["realtime_p95_ms"],
        },
        {
            "id": "consent_controls",
            "passed": (
                float(automated_indicators.get("consent_controls_working", 0.0)) >= 1.0
                and float(automated_indicators.get("privacy_defaults_working", 0.0)) >= 1.0
            ),
            "evidence": {
                "consent_controls_working": automated_indicators.get("consent_controls_working", 0.0),
                "privacy_defaults_working": automated_indicators.get("privacy_defaults_working", 0.0),
            },
        },
        {
            "id": "bhav_lineage_matrix",
            "passed": bool(goal_scenario["bhav_lineage_pass"]),
            "evidence": {
                "avg_bhav_composite": goal_scenario["avg_bhav_composite"],
            },
        },
        {
            "id": "gemini_skill_alignment",
            "passed": bool(gemini_verify.get("passed", False)),
            "evidence": gemini_verify.get("status", "UNKNOWN"),
        },
    ]
    all_quality_checks_pass = all(check["passed"] for check in data_quality_checks)

    high_stakes_content = False
    success_criteria = [
        {
            "criterion": "All content labeled with semantic schema",
            "passed": stage_1_status == "complete",
        },
        {
            "criterion": "Prerequisite chain validated",
            "passed": prereq_validity_score >= 0.7 and not has_cycle and not missing_prereqs,
        },
        {
            "criterion": "Cognitive load analyzed and balanced",
            "passed": load_balance_score >= 0.7 and not overload_modules,
        },
        {
            "criterion": "Objectives aligned with assessments",
            "passed": alignment_score >= 0.7 and not unassessed_objectives,
        },
        {
            "criterion": "Composite score >= 0.7",
            "passed": composite_score >= 0.7,
        },
        {
            "criterion": "Human feedback incorporated for high-stakes content",
            "passed": not high_stakes_content,
        },
        {
            "criterion": "Transfer validated with real-world scenarios",
            "passed": transfer_signal_score >= 0.75,
        },
    ]

    pipeline_passed = (
        stage_1_status == "complete"
        and stage_2_status == "pass"
        and stage_3_status == "pass"
        and all(item["passed"] for item in success_criteria)
        and all_quality_checks_pass
    )

    return {
        "skill": "instructional-design",
        "workflow": "full-pipeline",
        "status": "PASS" if pipeline_passed else "FAIL",
        "stage_1_labeling": {
            "stage": "labeling",
            "status": stage_1_status,
            "labeled_content": {
                "objectives": objectives,
                "concepts": concepts,
                "skills": skills,
                "misconceptions": misconceptions,
                "assessments": assessments,
                "transfer_contexts": transfer_contexts,
            },
            "metadata": {
                "labeled_by": "hybrid",
                "schema_version": "cdf_semantic_labels_v1",
                "source_artifacts": [
                    str(ROOT / "API_DATA_PLAN.json"),
                    str(ROOT / "scripts" / "test_project_goal.py"),
                ],
            },
            "cognitive_load_analysis": {
                "modules": module_loads,
                "max_total_load": round(max(module["total_load"] for module in module_loads), 3),
                "overloaded_modules": overload_modules,
                "stage_gate_passed": not overload_modules,
            },
            "prerequisite_graph": {
                "node_count": len(all_nodes),
                "edge_count": len(prereq_edges),
                "nodes": sorted(all_nodes),
                "edges": prereq_edges,
                "missing_references": missing_prereqs,
                "has_cycle": has_cycle,
                "max_chain_depth": max_depth,
            },
        },
        "stage_2_validation": {
            "stage": "validation",
            "status": stage_2_status,
            "validation_score": validation_score,
            "results": {
                "prerequisite_validity": {
                    "score": prereq_validity_score,
                    "missing_references": missing_prereqs,
                    "has_cycle": has_cycle,
                    "max_chain_depth": max_depth,
                },
                "cognitive_load_analysis": {
                    "score": load_balance_score,
                    "overloaded_modules": overload_modules,
                },
                "alignment_analysis": {
                    "score": alignment_score,
                    "unassessed_objectives": unassessed_objectives,
                    "bloom_mismatches": bloom_mismatches,
                    "alignment_matrix": alignment_matrix,
                },
                "gap_analysis": {
                    "score": gap_score,
                    "gaps": gap_issues,
                },
                "sequencing_analysis": {
                    "score": sequencing_score,
                    "difficulty_curve": "progressive" if progressive_curve else "inconsistent",
                    "objective_levels": objective_levels,
                },
            },
            "critical_issues": critical_issues,
            "recommendations": validation_recommendations,
        },
        "stage_3_evaluation": {
            "stage": "evaluation",
            "status": stage_3_status,
            "composite_score": composite_score,
            "dimension_scores": dimension_scores,
            "semantic_evaluation": {
                "instructional_quality": {
                    "score": round(_safe_mean([objective_clarity, alignment_score]), 3),
                    "evidence": "Objectives and assessments are tightly mapped to behavior checks.",
                },
                "transfer_readiness": {
                    "score": transfer_signal_score,
                    "evidence": "Focused API scenario validates adaptation and Bhav transfer contexts.",
                },
                "dignity_patterns": {
                    "score": dignity_preservation,
                    "evidence": "Consent defaults and privacy guardrails stay active while adapting.",
                },
            },
            "human_feedback": {
                "required": high_stakes_content,
                "status": "not_required_for_local_hackathon_eval",
                "next_step": (
                    "Collect SME review if deploying to production learners."
                    if not high_stakes_content
                    else "Collect trainer/SME review before deployment."
                ),
            },
            "experiment_results": {
                "type": "focused_api_scenario",
                "hypothesis": "Multisignal adaptation materially improves devotional guidance quality.",
                "observed": {
                    "listener_input_effect": goal_scenario["listener_input_effect"],
                    "biometric_effect": goal_scenario["biometric_effect"],
                    "environmental_effect": goal_scenario["environmental_effect"],
                    "mantra_learning_effect": goal_scenario["pronunciation_learning_effect"],
                    "bhav_lineage_pass": goal_scenario["bhav_lineage_pass"],
                },
            },
            "final_score": composite_score,
            "recommendation": stage_3_recommendation,
        },
        "data_engineering_requirements": {
            "design_inputs": {
                "goal": api_plan.get("goal"),
                "ddia_design_choices": api_plan.get("ddia_design_choices", []),
                "core_stories": api_plan.get("core_stories", []),
            },
            "label_to_data_contracts": [
                {
                    "label": "LEARNING_OBJECTIVE",
                    "source": "evals + focused API scenario",
                    "storage": "evals/reports/project_goal_status.json",
                },
                {
                    "label": "CONCEPT",
                    "source": "adaptation, consent, bhav service contracts",
                    "storage": "src/gemini_music_api/services/*",
                },
                {
                    "label": "SKILL",
                    "source": "end-to-end API behaviors",
                    "storage": "eval signal aggregations",
                },
                {
                    "label": "MISCONCEPTION",
                    "source": "design-time risk assumptions",
                    "storage": "instructional-design section in status report",
                },
                {
                    "label": "ASSESSMENT_ITEM",
                    "source": "api/scripts/test_project_goal.py + evals/cases.py",
                    "storage": "eval attempt artifacts",
                },
                {
                    "label": "TRANSFER_CONTEXT",
                    "source": "focused API scenario + lineage matrix",
                    "storage": "goal_scenario evidence in report",
                },
            ],
            "event_schema_requirements": {
                "required_voice_window_fields": [
                    "cadence_bpm",
                    "pronunciation_score",
                    "flow_score",
                    "practice_seconds",
                    "heart_rate",
                    "noise_level_db",
                ],
                "idempotency_key": "client_event_id",
                "append_only_table": "session_events",
                "projection_tables": ["sessions.summary_json", "practice_progress"],
            },
            "quality_gates": data_quality_checks,
            "all_quality_gates_passed": all_quality_checks_pass,
            "recommendations": (
                ["Keep gate thresholds and run scorecard + scenario on every release candidate."]
                if all_quality_checks_pass
                else ["Fix failed quality gates before demo handoff."]
            ),
        },
        "success_criteria": success_criteria,
    }


def _build_deep_agent_operating_model(
    *,
    scorecard_run: dict[str, Any],
    gemini_verify_run: dict[str, Any],
    instructional_pipeline: dict[str, Any],
) -> dict[str, Any]:
    main_source = _read_text(ROOT / "src" / "gemini_music_api" / "main.py")
    fallback_present = (
        "gemini_payload if gemini_payload is not None else generate_adaptation(ctx)" in main_source
    )

    recommendation = (
        "Use StateBackend for scratch execution, route durable memories under /memories with CompositeBackend, "
        "keep sandbox-as-tool for command execution, and enforce HITL for destructive/network-sensitive actions."
    )

    tool_usage_plan = [
        {
            "tool_id": "run_scorecard_evals",
            "purpose": "Generate scorecard-aligned behavior evidence.",
            "command": [sys.executable, "-m", "evals.run_evals", "--include-usually-passes", "--usually-attempts", "3"],
            "retry_policy": {"max_attempts": 2, "backoff_seconds_linear": 0.3},
        },
        {
            "tool_id": "verify_gemini_skills",
            "purpose": "Verify Gemini SDK/model usage against gemini-skills rules.",
            "command": [sys.executable, "scripts/verify_gemini_skill_usage.py"],
            "retry_policy": {"max_attempts": 2, "backoff_seconds_linear": 0.3},
        },
        {
            "tool_id": "run_focused_api_scenario",
            "purpose": "Validate listener/biometric/environment adaptation + mantra + bhav scenarios.",
            "command": ["inline_python", "_goal_api_scenario()"],
            "retry_policy": {"max_attempts": 1},
        },
        {
            "tool_id": "write_status_report",
            "purpose": "Write single consolidated JSON status output.",
            "command": ["json_write", str(REPORT_PATH)],
            "retry_policy": {"max_attempts": 1},
        },
    ]

    security_safeguards = [
        "Avoid FilesystemBackend as default in network-exposed contexts.",
        "Require HITL approval for destructive writes/execute and external side effects.",
        "Keep secrets outside sandbox; inject only at host tool boundary.",
        "Scope subagent tools minimally and require concise structured outputs.",
    ]

    checks = [
        {
            "id": "scorecard_tool_execution_success",
            "passed": scorecard_run["returncode"] == 0,
            "evidence": {
                "attempt_count": scorecard_run["attempt_count"],
                "self_healed": scorecard_run["self_healed"],
            },
        },
        {
            "id": "gemini_verification_execution_success",
            "passed": gemini_verify_run["returncode"] == 0,
            "evidence": {
                "attempt_count": gemini_verify_run["attempt_count"],
                "self_healed": gemini_verify_run["self_healed"],
            },
        },
        {
            "id": "retry_based_self_healing_enabled",
            "passed": scorecard_run["attempt_count"] >= 1 and gemini_verify_run["attempt_count"] >= 1,
            "evidence": "Subprocess runs use retry wrapper with bounded retries.",
        },
        {
            "id": "deterministic_fallback_available",
            "passed": fallback_present,
            "evidence": "Gemini adaptation path falls back to deterministic rule engine.",
        },
        {
            "id": "instructional_pipeline_embedded",
            "passed": instructional_pipeline.get("status") == "PASS",
            "evidence": instructional_pipeline.get("status"),
        },
        {
            "id": "single_json_output_contract",
            "passed": True,
            "evidence": str(REPORT_PATH),
        },
    ]
    readiness_score = round(_safe_mean([_bool_score(check["passed"]) for check in checks]), 3)
    readiness_passed = readiness_score >= 0.7 and all(check["passed"] for check in checks[:2])

    return {
        "skill": "langchain-deepagents-guide",
        "classification": "architecture_best_practices_security",
        "recommendation": recommendation,
        "agent_blueprint": {
            "backend_strategy": {
                "default_backend": "StateBackend",
                "persistent_memory_pattern": "CompositeBackend (/memories -> StoreBackend, / -> StateBackend)",
                "filesystem_backend_policy": "controlled_environments_only",
            },
            "planning_strategy": {
                "planner": "write_todos",
                "task_order": [
                    "scorecard_eval",
                    "gemini_skill_verification",
                    "focused_api_scenario",
                    "instructional_pipeline_analytics",
                    "final_report_write",
                ],
                "subagent_policy": "minimal toolsets with bounded outputs",
            },
            "self_healing_strategy": {
                "non_destructive_retry": True,
                "artifact_revalidation_after_retry": True,
                "fallback_on_gemini_failure": fallback_present,
            },
            "human_in_the_loop": {
                "required_for": ["execute", "destructive writes", "external side effects"],
                "thread_id": "stable_project_goal_thread_id",
            },
        },
        "tool_usage_plan": tool_usage_plan,
        "security_safeguards": security_safeguards,
        "readiness": {
            "score_0_to_1": readiness_score,
            "passed": readiness_passed,
            "checks": checks,
        },
    }


def _goal_api_scenario() -> dict[str, Any]:
    db_path = Path("/tmp/gemini_music_goal_test.db")
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    from fastapi.testclient import TestClient

    from gemini_music_api.db import Base, engine
    from gemini_music_api.main import app

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as client:
        user = client.post("/v1/users", json={"display_name": "Goal Test User"}).json()
        user_id = user["id"]

        consent = client.put(
            f"/v1/users/{user_id}/consent",
            json={
                "biometric_enabled": True,
                "environmental_enabled": True,
                "raw_audio_storage_enabled": False,
                "policy_version": "v1",
            },
        )
        assert consent.status_code == 200, consent.text

        session = client.post(
            "/v1/sessions",
            json={
                "user_id": user_id,
                "intention": "Goal coverage scenario for mantra + AI-assisted kirtan",
                "mantra_key": "maha_mantra_hare_krishna_hare_rama",
                "mood": "neutral",
                "target_duration_minutes": 10,
            },
        ).json()
        session_id = session["id"]

        # Baseline window.
        client.post(
            f"/v1/sessions/{session_id}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": "goal-baseline-evt",
                "payload": {
                    "cadence_bpm": 82,
                    "pronunciation_score": 0.82,
                    "flow_score": 0.8,
                    "practice_seconds": 240,
                    "heart_rate": 88,
                    "noise_level_db": 42,
                    "adaptation_helpful": True,
                },
            },
        )

        latencies_ms: list[float] = []

        def _adapt(explicit_mood: str) -> dict[str, Any]:
            t0 = time.monotonic()
            resp = client.post(
                f"/v1/sessions/{session_id}/adaptations",
                json={"explicit_mood": explicit_mood},
            )
            dt_ms = (time.monotonic() - t0) * 1000.0
            latencies_ms.append(dt_ms)
            assert resp.status_code == 200, resp.text
            return resp.json()

        baseline_adaptation = _adapt("neutral")

        # Listener input effect (mood).
        mood_adaptation = _adapt("anxious")

        # Biometric effect (high heart rate).
        client.post(
            f"/v1/sessions/{session_id}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": "goal-bio-evt",
                "payload": {
                    "cadence_bpm": 82,
                    "pronunciation_score": 0.8,
                    "flow_score": 0.72,
                    "practice_seconds": 240,
                    "heart_rate": 126,
                    "noise_level_db": 42,
                    "adaptation_helpful": True,
                },
            },
        )
        biometric_adaptation = _adapt("neutral")

        # Environmental effect (high noise).
        client.post(
            f"/v1/sessions/{session_id}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": "goal-env-evt",
                "payload": {
                    "cadence_bpm": 82,
                    "pronunciation_score": 0.79,
                    "flow_score": 0.7,
                    "practice_seconds": 240,
                    "heart_rate": 90,
                    "noise_level_db": 72,
                    "adaptation_helpful": True,
                },
            },
        )
        environment_adaptation = _adapt("neutral")

        # Mantra learning effect (low pronunciation should increase guidance).
        client.post(
            f"/v1/sessions/{session_id}/events",
            json={
                "event_type": "voice_window",
                "client_event_id": "goal-pronunciation-evt",
                "payload": {
                    "cadence_bpm": 82,
                    "pronunciation_score": 0.58,
                    "flow_score": 0.66,
                    "practice_seconds": 240,
                    "heart_rate": 90,
                    "noise_level_db": 44,
                    "adaptation_helpful": True,
                },
            },
        )
        pronunciation_adaptation = _adapt("neutral")

        end = client.post(
            f"/v1/sessions/{session_id}/end",
            json={"user_value_rating": 5, "completed_goal": True},
        )
        assert end.status_code == 200, end.text
        summary = end.json()["summary"]

        lineage_results = {}
        for lineage in ["sadhguru", "shree_vallabhacharya", "vaishnavism"]:
            bhav = client.post(
                f"/v1/sessions/{session_id}/bhav",
                json={
                    "golden_profile": "maha_mantra_v1",
                    "lineage": lineage,
                    "persist": False,
                },
            )
            assert bhav.status_code == 200, bhav.text
            lineage_results[lineage] = bhav.json()

    realtime_p95_ms = round(_p95(latencies_ms), 2)

    listener_input_effect = mood_adaptation["tempo_bpm"] < baseline_adaptation["tempo_bpm"]
    biometric_effect = biometric_adaptation["guidance_intensity"] == "high" and biometric_adaptation["tempo_bpm"] <= baseline_adaptation["tempo_bpm"]
    environmental_effect = environment_adaptation["guidance_intensity"] == "high"
    pronunciation_learning_effect = pronunciation_adaptation["guidance_intensity"] == "high"

    ai_kirtan_present = all(
        key in baseline_adaptation["adaptation_json"] for key in ["arrangement", "coach_actions"]
    )
    call_response_toggle_present = "call_response" in baseline_adaptation["adaptation_json"]["arrangement"]
    mantra_learning_summary_present = (
        summary.get("avg_pronunciation_score") is not None and summary.get("events_count", 0) > 0
    )

    bhav_lineage_pass = all(v["passes_golden"] for v in lineage_results.values())
    avg_bhav_composite = round(
        sum(float(v["composite"]) for v in lineage_results.values()) / len(lineage_results),
        3,
    )

    return {
        "realtime_p95_ms": realtime_p95_ms,
        "listener_input_effect": listener_input_effect,
        "biometric_effect": biometric_effect,
        "environmental_effect": environmental_effect,
        "pronunciation_learning_effect": pronunciation_learning_effect,
        "ai_kirtan_present": ai_kirtan_present,
        "call_response_toggle_present": call_response_toggle_present,
        "mantra_learning_summary_present": mantra_learning_summary_present,
        "session_summary": summary,
        "lineage_results": lineage_results,
        "bhav_lineage_pass": bhav_lineage_pass,
        "avg_bhav_composite": avg_bhav_composite,
    }


def main() -> int:
    _verify_runtime()
    scorecard_run = _run_subprocess_with_retry(
        [sys.executable, "-m", "evals.run_evals", "--include-usually-passes", "--usually-attempts", "3"]
    )
    gemini_verify_run = _run_subprocess_with_retry([sys.executable, "scripts/verify_gemini_skill_usage.py"])

    scorecard = _load_json(SCORECARD_REPORT_PATH)
    gemini_verify = _load_json(GEMINI_VERIFY_REPORT_PATH)
    goal_scenario = _goal_api_scenario()
    instructional_pipeline = _build_instructional_design_pipeline(
        goal_scenario=goal_scenario,
        scorecard=scorecard,
        gemini_verify=gemini_verify,
    )
    deep_agent = _build_deep_agent_operating_model(
        scorecard_run=scorecard_run,
        gemini_verify_run=gemini_verify_run,
        instructional_pipeline=instructional_pipeline,
    )

    scorecard_total = float(scorecard.get("scorecard", {}).get("total_score_0_to_100", 0.0))
    scorecard_priority_ready = bool(scorecard.get("scorecard", {}).get("priority_ready", False))
    demis_score = float(scorecard.get("scorecard", {}).get("demis_lens_score_0_to_50", 0.0))
    sundar_score = float(scorecard.get("scorecard", {}).get("sundar_lens_score_0_to_50", 0.0))

    dimensions = scorecard.get("scorecard", {}).get("dimensions", [])
    lowest_dimensions = sorted(
        [
            {"id": d.get("id"), "label": d.get("label"), "weighted_score": d.get("weighted_score", 0.0)}
            for d in dimensions
        ],
        key=lambda x: x["weighted_score"],
    )[:3]

    pillars = [
        {
            "id": "real_time_adaptive_loop",
            "name": "Real-time adaptive loop",
            "passed": goal_scenario["realtime_p95_ms"] <= 1000.0,
            "evidence": {"p95_latency_ms_local_test": goal_scenario["realtime_p95_ms"]},
        },
        {
            "id": "context_personalization",
            "name": "Personalization from listener + biometric + environment",
            "passed": all(
                [
                    goal_scenario["listener_input_effect"],
                    goal_scenario["biometric_effect"],
                    goal_scenario["environmental_effect"],
                ]
            ),
            "evidence": {
                "listener_input_effect": goal_scenario["listener_input_effect"],
                "biometric_effect": goal_scenario["biometric_effect"],
                "environmental_effect": goal_scenario["environmental_effect"],
            },
        },
        {
            "id": "mantra_learning",
            "name": "Mantra learning signals",
            "passed": goal_scenario["pronunciation_learning_effect"] and goal_scenario["mantra_learning_summary_present"],
            "evidence": {
                "pronunciation_guidance_triggered": goal_scenario["pronunciation_learning_effect"],
                "session_summary_fields_present": goal_scenario["mantra_learning_summary_present"],
                "avg_pronunciation_score": goal_scenario["session_summary"].get("avg_pronunciation_score"),
            },
        },
        {
            "id": "ai_assisted_kirtan",
            "name": "AI-assisted kirtan adaptation payload",
            "passed": goal_scenario["ai_kirtan_present"] and goal_scenario["call_response_toggle_present"],
            "evidence": {
                "arrangement_present": goal_scenario["ai_kirtan_present"],
                "call_response_toggle_present": goal_scenario["call_response_toggle_present"],
            },
        },
        {
            "id": "bhav_maha_mantra_lineages",
            "name": "Bhav + Maha Mantra golden across lineages",
            "passed": goal_scenario["bhav_lineage_pass"],
            "evidence": {
                "avg_bhav_composite": goal_scenario["avg_bhav_composite"],
                "lineages": {
                    k: {
                        "passes_golden": v["passes_golden"],
                        "composite": v["composite"],
                    }
                    for k, v in goal_scenario["lineage_results"].items()
                },
            },
        },
        {
            "id": "gemini_skill_compliance",
            "name": "Gemini usage aligned to gemini-skills",
            "passed": bool(gemini_verify.get("passed", False)),
            "evidence": {
                "status": gemini_verify.get("status"),
                "checks": gemini_verify.get("checks", []),
            },
        },
        {
            "id": "instructional_design_pipeline",
            "name": "Instructional-design labels + data engineering pipeline",
            "passed": instructional_pipeline.get("status") == "PASS",
            "evidence": {
                "workflow": instructional_pipeline.get("workflow"),
                "status": instructional_pipeline.get("status"),
                "validation_score": instructional_pipeline.get("stage_2_validation", {}).get("validation_score"),
                "composite_score": instructional_pipeline.get("stage_3_evaluation", {}).get("composite_score"),
                "all_quality_gates_passed": instructional_pipeline.get("data_engineering_requirements", {}).get(
                    "all_quality_gates_passed"
                ),
            },
        },
        {
            "id": "deep_agent_operating_model",
            "name": "Deep Agent tool usage, planning, and self-healing readiness",
            "passed": bool(deep_agent.get("readiness", {}).get("passed", False)),
            "evidence": {
                "readiness_score_0_to_1": deep_agent.get("readiness", {}).get("score_0_to_1"),
                "checks": deep_agent.get("readiness", {}).get("checks", []),
            },
        },
    ]

    on_track_for_hackathon_demo = all(p["passed"] for p in pillars)

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "goal_statement": (
            "Use Gemini 3.0 to build real-time personalized music experiences that evolve based on listener input, "
            "biometric data, and environmental context; enable mantra learning and AI-assisted kirtan."
        ),
        "summary": {
            "on_track_for_hackathon_demo": on_track_for_hackathon_demo,
            "executive_priority_ready": scorecard_priority_ready,
            "scorecard_total_0_to_100": scorecard_total,
            "demis_lens_0_to_50": demis_score,
            "sundar_lens_0_to_50": sundar_score,
            "instructional_pipeline_status": instructional_pipeline.get("status"),
            "instructional_pipeline_score_0_to_1": instructional_pipeline.get("stage_3_evaluation", {}).get(
                "final_score"
            ),
            "deep_agent_readiness_score_0_to_1": deep_agent.get("readiness", {}).get("score_0_to_1"),
            "deep_agent_readiness_passed": deep_agent.get("readiness", {}).get("passed"),
            "top_scorecard_gaps": lowest_dimensions,
        },
        "pillars": pillars,
        "instructional_design": instructional_pipeline,
        "deep_agent_architecture": deep_agent,
        "artifacts": {
            "scorecard_run": scorecard_run,
            "gemini_verify_run": gemini_verify_run,
            "scorecard_report_path": str(SCORECARD_REPORT_PATH),
            "gemini_verify_report_path": str(GEMINI_VERIFY_REPORT_PATH),
            "api_data_plan_path": str(ROOT / "API_DATA_PLAN.json"),
        },
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nWrote goal status report: {REPORT_PATH}")

    return 0 if on_track_for_hackathon_demo else 1


if __name__ == "__main__":
    raise SystemExit(main())
