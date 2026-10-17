.PHONY: help install install-ml test lint format clean

PYTHON ?= python

help:
	@echo "SignalGate - Shift-Aware Fraud Triage Development Makefile"
	@echo "Available commands:"
	@echo "  make install      Install core deterministic dependencies"
	@echo "  make install-ml   Install ML modeling and simulation dependencies"
	@echo "  make test         Execute test suite"
	@echo "  make lint         Run static analysis (ruff and mypy)"
	@echo "  make format       Auto-format code using ruff"
	@echo "  make clean        Remove build artifacts and bytecode caches"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

install-ml:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-ml.txt

test:
	$(PYTHON) -m pytest tests/

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m mypy agents schemas models

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
