.PHONY: help install install-dev type-check lint format test clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install the package in development mode
	pip install -e .

install-dev: ## Install the package with development dependencies
	pip install -e ".[dev]"

type-check: ## Run mypy type checking
	mypy optimizer/ analytics/ tests/

lint: ## Run ruff linter
	ruff check .

format: ## Format code with black and isort
	black .
	isort .

test: ## Run tests
	pytest tests/ -v

clean: ## Clean up build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".mypy_cache" -delete

check-all: type-check lint test ## Run all checks (type checking, linting, and tests)
