# Hackathon Submission Dossier

## 1. Product Narrative

Gemini Music is a real-time devotional learning platform that adapts mantra and AI-kirtan guidance from listener signals, optional biometrics, and environment context.

Core claims:
- Real-time adaptation improves outcomes versus static flow.
- Stage-based mantra progression is measurable and rubric-backed.
- Ecosystem integrations (wearable + content adapters) are production-shaped.
- Evidence and release governance are deterministic and reproducible.

## 2. Proof Pack Highlights

| Claim | Evidence Artifact |
|---|---|
| Adaptive beats static baseline with confidence | `api/evals/reports/adaptive_vs_static_benchmark.json` |
| Runtime reliability under concurrent load | `api/evals/reports/load_latency_benchmark.json` |
| Graceful degradation under failures | `api/evals/reports/chaos_reliability_report.json` |
| Stage mastery progression visibility | `api/evals/reports/latest_report.json` + `/poc/` flow |
| AI-kirtan payload reliability | `api/evals/reports/ai_kirtan_quality_report.json` |
| Ecosystem integration readiness | `api/evals/reports/adapter_starter_kit_verification.json` |
| Business signal and north-star trends | `api/evals/reports/weekly_kpi_report.json` |
| Reproducible eval rigor and drift controls | `api/evals/reports/seed_reproducibility_report.json`, `api/evals/reports/eval_drift_snapshot.json` |

## 3. RFC / Governance Credibility

- ADR evidence-gated release policy: `docs/adr/0003-evidence-gated-release-policy.md`
- RFC priority framework: `docs/rfc/RFC-001-priority-readiness-framework.md`
- RFC ecosystem leverage: `docs/rfc/RFC-001D-ecosystem-leverage.md`
- RFC business signal: `docs/rfc/RFC-001F-business-signal.md`
- RFC eval rigor: `docs/rfc/RFC-001G-eval-rigor.md`

## 4. Judge Mapping (A-G)

| Criterion | What we show |
|---|---|
| A Frontier product novelty | Real-time adaptive loop + context-aware guidance |
| B User value proof | Stage progression + adaptive uplift benchmark |
| C Scale readiness | Concurrency latency SLO + deterministic fallback |
| D Ecosystem leverage | Adapter starter kit + webhook processing telemetry |
| E Safety/privacy | Consent defaults, opt-in biometrics, fallback without hard dependency |
| F Measurable business signal | KPI trend deltas + versioned north-star contract |
| G Scientific eval rigor | Seed reproducibility, drift alarms, release gates |

## 5. Final Narrative (Pitch Draft)

1. We built not just a demo, but a measurable learning system.
2. We prove adaptation value with repeated confidence-bound benchmarks.
3. We prove reliability with load/chaos and resilient fallback behavior.
4. We prove ecosystem leverage with executable adapter references.
5. We prove business value with north-star traceability from events to KPI trends.
6. We prove governance with evidence-gated release automation.
