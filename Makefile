.PHONY: help install install-dev test test-cov format lint type-check clean build docs serve-docs

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       Install package in production mode"
	@echo "  make install-dev   Install package in development mode with all extras"
	@echo "  make test          Run tests"
	@echo "  make test-cov      Run tests with coverage report"
	@echo "  make format        Format code with black and isort"
	@echo "  make lint          Run all linters (flake8, pylint, bandit)"
	@echo "  make type-check    Run mypy type checking"
	@echo "  make clean         Remove build artifacts and cache files"
	@echo "  make build         Build distribution packages"
	@echo "  make docs          Build documentation"
	@echo "  make serve-docs    Serve documentation locally"

# Installation targets
install:
	pip install -e .

install-dev:
	pip install -e ".[dev,docs,analysis]"
	pre-commit install

# Testing targets
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=mendi_ble --cov-report=html --cov-report=term

# Code quality targets
format:
	black src/ tests/ examples/ scripts/
	isort src/ tests/ examples/ scripts/

lint:
	flake8 src/ tests/ examples/
	pylint src/
	bandit -r src/

type-check:
	mypy src/

# Cleaning targets
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Build targets
build: clean
	python -m build

# Documentation targets
docs:
	cd docs && sphinx-build -b html . _build/html

serve-docs: docs
	cd docs/_build/html && python -m http.server

# Development workflow shortcuts
check: format lint type-check test
	@echo "All checks passed!"

# Quick test during development
quick-test:
	pytest tests/ -v -x --tb=short

# Update dependencies
update-deps:
	pip install --upgrade pip setuptools wheel
	pip install --upgrade -r requirements.txt
	pip install --upgrade -r requirements-dev.txt

# Create example capture directory
setup-captures:
	mkdir -p data/captures
	@echo "Created data/captures directory for BLE packet captures"