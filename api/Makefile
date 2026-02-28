PYTHON_VERSION ?= 3.13
PYTHON_CANDIDATE := $(shell command -v python3.13 2>/dev/null || command -v python3 2>/dev/null || command -v python 2>/dev/null)
PYTHON ?= $(PYTHON_CANDIDATE)
VENV ?= .venv
PYTHON_BIN := $(VENV)/bin/python
PIP_BIN := $(PYTHON_BIN) -m pip

.PHONY: doctor bootstrap venv install lock run test evals evals_all verify_gemini demo goal_test poc_test recompute_projections drift_snapshot data_quality weekly_kpi release_gate release_evidence_summary bench_adaptive load_benchmark chaos_reliability seed_repro ai_kirtan_quality adapter_verify ci

doctor:
	@echo "== Python toolchain check =="
	@if [ -z "$(PYTHON)" ]; then \
		echo "No Python interpreter found on PATH. Install Python $(PYTHON_VERSION) and/or set PYTHON=/path/to/python."; \
		exit 1; \
	fi
	@if ! command -v "$(PYTHON)" >/dev/null 2>&1; then \
		echo "Missing $(PYTHON). Install Python $(PYTHON_VERSION)."; \
		exit 1; \
	fi
	@actual="$$( $(PYTHON) -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' )"; \
	if [ "$$actual" != "$(PYTHON_VERSION)" ]; then \
		echo "$(PYTHON) is $$actual; expected $(PYTHON_VERSION)."; \
		exit 1; \
	fi
	@if [ -x "$(PYTHON_BIN)" ]; then \
		venv_actual="$$( $(PYTHON_BIN) -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' )"; \
		echo "venv interpreter: $$venv_actual"; \
		if [ "$$venv_actual" != "$(PYTHON_VERSION)" ]; then \
			echo "Venv version mismatch detected at $(VENV). Run: make bootstrap"; \
			exit 1; \
		fi; \
	else \
		echo "No venv detected at $(VENV) yet."; \
	fi

bootstrap:
	@if [ -x "$(PYTHON_BIN)" ]; then \
		venv_actual="$$( $(PYTHON_BIN) -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' )"; \
		if [ "$$venv_actual" != "$(PYTHON_VERSION)" ]; then \
			echo "Recreating $(VENV): found Python $$venv_actual, need $(PYTHON_VERSION)."; \
			rm -rf "$(VENV)"; \
		fi; \
	fi
	@if [ ! -x "$(PYTHON_BIN)" ]; then \
		if [ -z "$(PYTHON)" ]; then \
			echo "No Python interpreter found on PATH. Install Python $(PYTHON_VERSION) and/or set PYTHON=/path/to/python."; \
			exit 1; \
		fi; \
		if ! command -v "$(PYTHON)" >/dev/null 2>&1; then \
			echo "Missing $(PYTHON). Install Python $(PYTHON_VERSION)."; \
			exit 1; \
		fi; \
		actual="$$( $(PYTHON) -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' )"; \
		if [ "$$actual" != "$(PYTHON_VERSION)" ]; then \
			echo "$(PYTHON) is $$actual; expected $(PYTHON_VERSION)."; \
			exit 1; \
		fi; \
		"$(PYTHON)" -m venv "$(VENV)"; \
	fi

venv: bootstrap

install: bootstrap
	$(PIP_BIN) install -r requirements.txt

lock: install
	$(PYTHON_BIN) -m pip freeze --disable-pip-version-check | sort > requirements.lock

run: install
	PYTHONPATH=src $(PYTHON_BIN) -m uvicorn gemini_music_api.main:app --reload --port 8000

test: install
	PYTHONPATH=src $(PYTHON_BIN) -m pytest -q

evals: install
	PYTHONPATH=src:. $(PYTHON_BIN) -m evals.run_evals

evals_all: install
	PYTHONPATH=src:. $(PYTHON_BIN) -m evals.run_evals --include-usually-passes --usually-attempts 10

verify_gemini: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/verify_gemini_skill_usage.py

demo: install
	PYTHONPATH=src:. $(PYTHON_BIN) demo/spinup_demo.py

goal_test: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/test_project_goal.py

poc_test: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/test_maha_mantra_poc.py

recompute_projections: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/recompute_projections.py

drift_snapshot: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/capture_eval_drift_snapshot.py

data_quality: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/data_quality_checks.py

weekly_kpi: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/generate_weekly_kpi_report.py

release_evidence_summary: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/build_release_evidence_summary.py

bench_adaptive: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/benchmark_adaptive_vs_static.py --runs 30 --seed 202603

load_benchmark: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/benchmark_load_latency.py --concurrency 20 --rounds 2 --p95-target-ms 250 --max-error-rate 0.05

chaos_reliability: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/run_chaos_reliability.py

seed_repro: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/check_eval_seed_reproducibility.py --seed 1337 --attempts 30 --tolerance 1e-6

ai_kirtan_quality: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/verify_ai_kirtan_quality.py

adapter_verify: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/verify_adapter_starter_kit.py

release_gate: install
	PYTHONPATH=src:. $(PYTHON_BIN) scripts/check_release_gates.py

ci: doctor test evals_all verify_gemini goal_test poc_test bench_adaptive load_benchmark chaos_reliability seed_repro ai_kirtan_quality adapter_verify recompute_projections drift_snapshot data_quality weekly_kpi release_gate release_evidence_summary
