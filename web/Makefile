.PHONY: dev test lint format sync-csvs pull-csvs

# Development server
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
test:
	pytest -q

# Lint and format
lint:
	ruff check .

format:
	ruff format .

# Export CSVs to CSV_EXPORT_DIR (default: ../data on Mac, /opt/pascal-web/exports on Pi)
sync-csvs:
	python -m app.scripts.export_csvs

# Pull CSVs from the Pi to the local data directory
# Usage: make pull-csvs
pull-csvs:
	rsync -avz pi@pascal.local:/opt/pascal-web/exports/*.csv ../data/
