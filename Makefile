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

# Docker and InfluxDB management
.PHONY: influxdb-up influxdb-down influxdb-logs influxdb-shell backup restore sync

# Start local InfluxDB and Chronograf
influxdb-up:
	docker-compose up -d influxdb chronograf
	@echo "Waiting for InfluxDB to be ready..."
	@until curl -s http://localhost:8086/ping > /dev/null; do sleep 1; done
	@echo "InfluxDB is ready!"
	@echo "Chronograf web interface available at: http://localhost:8888"

# Stop local InfluxDB and Chronograf
influxdb-down:
	docker-compose down

# View InfluxDB logs
influxdb-logs:
	docker-compose logs -f influxdb

# View Chronograf logs
chronograf-logs:
	docker-compose logs -f chronograf

# Access InfluxDB shell
influxdb-shell:
	docker exec -it ha-optimizer-influxdb influx

# Backup all measurements from production
backup-all:
	python scripts/influx-sync/backup_all.py

# List available measurements
list-measurements:
	python scripts/influx-sync/backup_all.py --list-measurements

# Restore all measurements to local InfluxDB
restore-all:
	python scripts/influx-sync/restore_all.py

# List available measurements in backup
list-backup-measurements:
	python scripts/influx-sync/restore_all.py --list-available

# Sync new data from production to local
sync:
	python scripts/influx-sync/sync_all.py

# Check sync status
sync-status:
	python scripts/influx-sync/status.py

# Dry run sync (see what would be synced)
sync-dry-run:
	python scripts/influx-sync/sync_all.py --dry-run

# Full setup: start InfluxDB, backup production data, and restore to local
setup-local-influxdb: influxdb-up
	@echo "Backing up production data..."
	@python scripts/influx-sync/backup_all.py
	@echo "Restoring data to local InfluxDB..."
	@python scripts/influx-sync/restore_all.py
	@echo "Local InfluxDB setup complete!"

# Full setup with all measurements: start InfluxDB, backup all production data, and restore to local
setup-local-influxdb-all: influxdb-up
	@echo "Backing up all production measurements..."
	@python scripts/influx-sync/backup_all.py
	@echo "Restoring all data to local InfluxDB..."
	@python scripts/influx-sync/restore_all.py
	@echo "Local InfluxDB setup complete with all measurements!"

# Test local InfluxDB setup
test-influxdb:
	python scripts/test_local_influxdb.py

# Show InfluxDB environment
show-influxdb-env:
	python scripts/show_influxdb_env.py
