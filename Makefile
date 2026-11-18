# Interpreter: the local .venv when present (CI, main checkout), otherwise the main
# checkout's .venv (git worktrees). Override with `make PYTHON=...`.
MAIN_CHECKOUT := $(abspath $(dir $(abspath $(shell git rev-parse --git-common-dir 2>/dev/null))))
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,$(MAIN_CHECKOUT)/.venv/bin/python)

.PHONY: help check docs-check boundaries-check evidence-index-check experiments-check stages-check readiness-check artifacts-check progress progress-check research-index test dependencies doctor

help:
	@echo "check: offline documentation, dependency, and behavior checks"
	@echo "doctor: local engine and observer configuration check"

check: docs-check boundaries-check evidence-index-check experiments-check stages-check readiness-check artifacts-check progress-check dependencies test

boundaries-check:
	$(PYTHON) scripts/check_boundaries.py

docs-check:
	$(PYTHON) scripts/check_docs.py

dependencies:
	$(PYTHON) -m pip check

test:
	$(PYTHON) scripts/run_tests.py --max-seconds 30 --start tests

doctor:
	$(PYTHON) scripts/paper.py doctor

# Local only (not part of check): the issuer-qualified sector-ETF derivative is private
# data in the main checkout; see docs/tasks/2026-11-17-engine-parity.md.
PARITY_DATA ?= /Users/kenfuliang/git/quant-trading-lab/data/normalized
PARITY_BARS ?= $(PARITY_DATA)/alpaca-sector-etfs-2016-2025-v1.json
PARITY_ACTIONS ?= $(PARITY_DATA)/alpaca-sector-etfs-2016-2025-v1-issuer-actions-v2.json

.PHONY: parity-local
parity-local:
	$(PYTHON) scripts/current/engine_parity.py run --bars $(PARITY_BARS) --actions $(PARITY_ACTIONS) --instruments SPY,XLB,XLE,XLF

.PHONY: performance performance-stop
performance:
	$(PYTHON) scripts/performance.py start

performance-stop:
	$(PYTHON) scripts/performance.py stop

.PHONY: leverage-comparison
leverage-comparison: performance
	$(PYTHON) scripts/current/leverage_comparison.py

.PHONY: strategy-suite
strategy-suite: performance
	$(PYTHON) scripts/current/strategy_suite.py

progress-check:
	$(PYTHON) scripts/progress.py check

progress:
	$(PYTHON) scripts/progress.py build

stages-check:
	$(PYTHON) scripts/stages.py check

.PHONY: stages
stages:
	$(PYTHON) scripts/stages.py build
	$(PYTHON) scripts/dashboard.py

readiness-check:
	$(PYTHON) scripts/readiness.py check

.PHONY: artifacts-check
artifacts-check:
	$(PYTHON) scripts/artifacts.py check

.PHONY: artifacts
artifacts:
	$(PYTHON) scripts/artifacts.py render

.PHONY: readiness
readiness:
	$(PYTHON) scripts/readiness.py render
	$(PYTHON) scripts/readiness.py build
	$(PYTHON) scripts/dashboard.py

experiments-check:
	$(PYTHON) scripts/experiments.py check

evidence-index-check:
	$(PYTHON) scripts/current/research_index.py --check

research-index:
	$(PYTHON) scripts/current/research_index.py --write
