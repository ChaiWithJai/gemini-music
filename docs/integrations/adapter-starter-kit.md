# Adapter Starter Kit (Wearable + Content)

This starter kit provides executable reference patterns for partner adapters that integrate with Gemini Music.

## Contracts

- Inbound partner event endpoint: `POST /v1/integrations/events`
- Webhook subscription endpoint: `POST /v1/integrations/webhooks`
- Ecosystem export: `GET /v1/integrations/exports/ecosystem-usage/daily`

## Reference Adapters

- Wearable stream adapter: `api/adapters/wearable_stream_adapter.py`
- Content playlist adapter: `api/adapters/content_playlist_adapter.py`

## Quick Start

1. Start API:

```bash
cd api
make run
```

2. Create a user/session (see `api/README.md` examples) and capture `session_id`.

3. Emit wearable signal:

```bash
cd api
PYTHONPATH=src:. .venv/bin/python adapters/wearable_stream_adapter.py \
  --base-url http://127.0.0.1:8000 \
  --session-id <SESSION_ID>
```

4. Emit content signal + register webhook:

```bash
cd api
PYTHONPATH=src:. .venv/bin/python adapters/content_playlist_adapter.py \
  --base-url http://127.0.0.1:8000 \
  --session-id <SESSION_ID>
```

5. Verify ecosystem export:

```bash
curl -s http://127.0.0.1:8000/v1/integrations/exports/ecosystem-usage/daily | jq .
```

## Automated Verification

Run the built-in verification:

```bash
cd api
make adapter_verify
```

Artifact:
- `api/evals/reports/adapter_starter_kit_verification.json`
