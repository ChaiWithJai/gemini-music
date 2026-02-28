# Gemini Music API (Core Stories)

This service implements a working data + API layer for the core hackathon stories:
- Start a mantra session
- Ingest live session events (idempotent)
- Generate real-time adaptation decisions
- End session and project progress metrics
- Manage user consent for biometric/environmental data

## Why this data layer (DDIA-aligned)

- **Append-only event log**: `session_events` stores immutable facts from live sessions.
- **Materialized projections**: `sessions.summary_json` and `practice_progress` are derived views for fast reads.
- **Idempotency**: `client_event_id` with `(session_id, client_event_id)` uniqueness protects against retry duplicates.
- **Schema-first evolution**: explicit SQLAlchemy models and versionable payloads (`policy_version`, JSON payloads).

## Quick start

```bash
cd /Users/jaybhagat/projects/gemini-music/api
make bootstrap
make install
make run
```

Open docs: `http://localhost:8000/docs`

## Environment policy (DevOps guardrail)

- Canonical runtime: **Python 3.13**
- Canonical virtualenv path: **`.venv`**
- If `.venv` exists with the wrong Python minor version, `make bootstrap` auto-recreates it.
- Use `make doctor` for a fail-fast environment check before demos or releases.

## DevOps + DDIA Ops Commands

```bash
cd /Users/jaybhagat/projects/gemini-music/api
make ci                 # full local CI-equivalent gate set
make recompute_projections
make drift_snapshot
make data_quality
make weekly_kpi
make release_gate
```

Migration workflow:

```bash
cd /Users/jaybhagat/projects/gemini-music/api
DATABASE_URL=sqlite:///./gemini_music.db PYTHONPATH=src .venv/bin/alembic upgrade head
```

## Core API flow (curl)

### 1) Create user
```bash
curl -s -X POST http://localhost:8000/v1/users \
  -H 'Content-Type: application/json' \
  -d '{"display_name":"Jay"}'
```

### 2) Update consent
```bash
curl -s -X PUT http://localhost:8000/v1/users/<USER_ID>/consent \
  -H 'Content-Type: application/json' \
  -d '{
    "biometric_enabled": true,
    "environmental_enabled": true,
    "raw_audio_storage_enabled": false,
    "policy_version": "v1"
  }'
```

### 3) Start session
```bash
curl -s -X POST http://localhost:8000/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id":"<USER_ID>",
    "intention":"Evening grounding",
    "mantra_key":"om_namah_shivaya",
    "mood":"anxious",
    "target_duration_minutes":10
  }'
```

### 4) Ingest live event (idempotent)
```bash
curl -s -X POST http://localhost:8000/v1/sessions/<SESSION_ID>/events \
  -H 'Content-Type: application/json' \
  -d '{
    "event_type":"voice_window",
    "client_event_id":"evt-001",
    "payload":{
      "cadence_bpm":78,
      "pronunciation_score":0.61,
      "flow_score":0.52,
      "practice_seconds":420,
      "heart_rate":114,
      "noise_level_db":48
    }
  }'
```

### 5) Request adaptation
```bash
curl -s -X POST http://localhost:8000/v1/sessions/<SESSION_ID>/adaptations \
  -H 'Content-Type: application/json' \
  -d '{"explicit_mood":"anxious"}'
```

### 6) End session + get summary
```bash
curl -s -X POST http://localhost:8000/v1/sessions/<SESSION_ID>/end \
  -H 'Content-Type: application/json' \
  -d '{"user_value_rating":5,"completed_goal":true}'
```

### 7) Get user progress projection
```bash
curl -s http://localhost:8000/v1/users/<USER_ID>/progress
```

### 8) Bhav composite + Maha Mantra golden eval
```bash
curl -s -X POST http://localhost:8000/v1/sessions/<SESSION_ID>/bhav \
  -H 'Content-Type: application/json' \
  -d '{"golden_profile":"maha_mantra_v1","lineage":"vaishnavism","persist":true}'
```

### 9) Maha Mantra stage scoring (POC)
```bash
curl -s -X POST http://localhost:8000/v1/maha-mantra/evaluate \
  -H 'Content-Type: application/json' \
  -d '{
    "stage":"call_response",
    "lineage":"vaishnavism",
    "golden_profile":"maha_mantra_v1",
    "metrics":{
      "duration_seconds":40,
      "voice_ratio_total":0.55,
      "voice_ratio_student":0.74,
      "voice_ratio_guru":0.17,
      "pitch_stability":0.83,
      "cadence_bpm":73,
      "cadence_consistency":0.79,
      "avg_energy":0.49
    }
  }'
```

Supported lineage values:
- `sadhguru`
- `shree_vallabhacharya`
- `vaishnavism` (alias: `vashnavism`)

## Test

```bash
cd /Users/jaybhagat/projects/gemini-music/api
make test
```

POC readiness test for Maha Mantra web flow:

```bash
cd /Users/jaybhagat/projects/gemini-music/api
make poc_test
```

POC report artifact: `evals/reports/maha_mantra_poc_status.json`

## Scorecard Evals

Run scorecard-aligned behavioral evals:

```bash
cd /Users/jaybhagat/projects/gemini-music/api
make evals
```

Run all evals including `USUALLY_PASSES` with 3 attempts:

```bash
cd /Users/jaybhagat/projects/gemini-music/api
make evals_all
```

Report output: `evals/reports/latest_report.json`

## Gemini Skill Verification

Verify Gemini usage against `google-gemini/gemini-skills` guidance:

```bash
cd /Users/jaybhagat/projects/gemini-music/api
make verify_gemini
```

Verification report: `evals/reports/gemini_skill_verification.json`

## Demo Spin-up

Run a full local demo flow (creates demo artifact):

```bash
cd /Users/jaybhagat/projects/gemini-music/api
make demo
```

Demo artifact: `demo/latest_demo_output.json`

## Maha Mantra Web POC

After running the API server, open:

- `http://localhost:8000/poc/`

Flow implemented in UI:

- 30s listen
- guided follow-along with scoring
- call-response with student turn mute/scoring
- performance recap
- independent performance + final scoring + Bhav check

## Goal Test

Run a single script that evaluates current status against the full project goal:

```bash
cd /Users/jaybhagat/projects/gemini-music/api
make goal_test
```

Goal status artifact: `evals/reports/project_goal_status.json`

## Table summary

- `users`: user identity
- `consent_records`: consent history (append-only)
- `sessions`: session lifecycle and summary projection
- `session_events`: immutable event log
- `adaptation_decisions`: adaptation outputs used by real-time clients
- `practice_progress`: materialized aggregate for dashboards
