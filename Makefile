PYTHON ?= .venv/bin/python

.PHONY: help check docs-check test dependencies doctor

help:
	@echo "check: offline documentation, dependency, and behavior checks"
	@echo "doctor: local engine and observer configuration check"

check: docs-check dependencies test

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
	$(PYTHON) scripts/leverage_comparison.py
