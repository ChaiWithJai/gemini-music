# Runbook: 7-Minute Executive Demo Rehearsal

## One-Command Rehearsal

From repo root:

```bash
./scripts/rehearse_demo.sh
```

Fallback mode for degraded environments:

```bash
./scripts/rehearse_demo.sh --degraded
```

Artifacts:

- `api/evals/reports/demo_rehearsal_report.json`
- `api/evals/reports/release_evidence_summary.md`

## Time-Boxed Script (7 Minutes)

1. Minute 0-1: Problem + Product thesis.
2. Minute 1-2: Real-time adaptation loop (`project_goal_status.json`).
3. Minute 2-3: Run `/demo/` stage mastery and adaptation flows live, then pivot to `/poc/` for product UX.
4. Minute 3-4: AI-kirtan contract/rubric evidence (`ai_kirtan_quality_report.json`).
5. Minute 4-5: Ecosystem leverage demo (wearable + content adapters + webhooks).
6. Minute 5-6: Benchmark and reliability proof (`adaptive_vs_static`, `load_latency`, `chaos`).
7. Minute 6-7: Business signal + north-star + governance summary.

## Judge Criteria Mapping

- A Frontier novelty: adaptive context loop + Gemini orchestration.
- B User value: adaptive-vs-static uplift and stage progression.
- C Scale readiness: load latency SLO and idempotent event handling.
- D Ecosystem leverage: adapter starter kit + webhook reliability.
- E Safety/privacy: consent defaults + fallback behavior.
- F Business signal: weekly KPI trends + north-star contract.
- G Eval rigor: seeded reproducibility + drift alarms + release gates.
