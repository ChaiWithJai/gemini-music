# ADR 0002: Pin Runtime to Python 3.13

- Status: Accepted
- Date: 2026-02-28
- Decision owners: DevOps + API engineering

## Context

Local development saw breakage from venv/runtime drift, especially where `.venv` pointed at Python 3.14 and dependency builds were incompatible with the current stack.

## Decision

Pin the runtime to Python 3.13 for both local and CI execution.

Implemented controls:

- `api/Makefile` sets `PYTHON_VERSION ?= 3.13`
- `make doctor` fails fast on interpreter mismatch
- `make bootstrap` recreates mismatched `.venv`
- GitHub Actions uses `actions/setup-python@v5` with `python-version: '3.13'`

## Consequences

Positive:

- Reproducible local and CI behavior
- Fewer onboarding failures
- Faster root-cause analysis when failures happen

Tradeoffs:

- Contributors must install Python 3.13 explicitly
- Future Python upgrades require a coordinated change

## Follow-up

- Keep monthly dependency refresh workflow active
- Reassess Python version quarterly with compatibility tests
