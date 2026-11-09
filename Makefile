PYTHON ?= .venv/bin/python

.PHONY: help check docs-check boundaries-check evidence-index-check experiments-check research-index test dependencies doctor

help:
	@echo "check: offline documentation, dependency, and behavior checks"
	@echo "doctor: local engine and observer configuration check"

check: docs-check boundaries-check evidence-index-check experiments-check dependencies test

boundaries-check:
	$(PYTHON) scripts/check_boundaries.py

docs-check:
	$(PYTHON) scripts/check_docs.py

dependencies:
	$(PYTHON) -m pip check

test:
	$(PYTHON) -m unittest discover -s tests -v

doctor:
	$(PYTHON) scripts/paper.py doctor

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

experiments-check:
	$(PYTHON) scripts/experiments.py check

evidence-index-check:
	$(PYTHON) scripts/current/research_index.py --check

research-index:
	$(PYTHON) scripts/current/research_index.py --write
