# Evaluation Framework (Scorecard-Aligned)

This framework borrows the key operating model from the Gemini CLI behavioral evals:

- Policy tiers: `ALWAYS_PASSES` and `USUALLY_PASSES`.
- Multi-attempt runs for non-deterministic cases.
- JSON report artifacts for trend tracking.
- Separation of behavioral validation from pure unit tests.

## What this evaluates

1. Core behavioral stories for mantra/kirtan API flows.
2. Automated indicators mapped to the leadership scorecard dimensions.
3. Weighted score output with dual lenses:
   - Demis lens
   - Sundar lens
4. Bhav composite quality for devotional sessions:
   - `discipline`
   - `resonance`
   - `coherence`
   - Maha Mantra golden pass/fail
   - Lineage-specific golden checks for:
     - `sadhguru`
     - `shree_vallabhacharya`
     - `vaishnavism`

## Files

- `evals/cases.py`: behavioral eval cases and assertions.
- `evals/framework.py`: scorecard model, weights, and rating functions.
- `evals/manual_evidence.json`: manually maintained evidence for dimensions not fully automatable yet.
- `evals/run_evals.py`: runner that executes evals and writes a report.
- `evals/reports/latest_report.json`: generated run artifact.

## Run

From `/Users/jaybhagat/projects/gemini-music/api`:

```bash
source .venv/bin/activate
PYTHONPATH=src:. python -m evals.run_evals
```

To include `USUALLY_PASSES` evals and run them 3 times:

```bash
source .venv/bin/activate
PYTHONPATH=src:. python -m evals.run_evals --include-usually-passes --usually-attempts 3
```

## Output

The runner produces:

- `run_status` based on `ALWAYS_PASSES` failures.
- Per-case pass rates and attempt details.
- Aggregated automated indicators.
- Weighted scorecard:
  - `total_score_0_to_100`
  - `demis_lens_score_0_to_50`
  - `sundar_lens_score_0_to_50`
  - `priority_ready` (true/false)

## Updating the scorecard

1. Keep adding automated indicators via new eval cases in `cases.py`.
2. Update manual evidence in `manual_evidence.json` when new proof exists.
3. Tighten dimensions or weights in `framework.py` as the product matures.
