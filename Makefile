.PHONY: install run run-prod test test-cov lint format clean setup help

# Default target
help:
	@echo "Available targets:"
	@echo "  setup     - Create virtual environment and install dependencies"
	@echo "  install   - Install dependencies in existing environment"
	@echo "  run       - Run development server with hot reload"
	@echo "  run-prod  - Run production server"
	@echo "  test      - Run all tests"
	@echo "  test-cov  - Run tests with coverage report"
	@echo "  lint      - Run linting checks"
	@echo "  format    - Format code with black and isort"
	@echo "  clean     - Clean up generated files"
	@echo "  sample    - Load sample data"

# Setup virtual environment and install dependencies
setup:
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	@echo "Setup complete! Run 'source venv/bin/activate' to activate the environment"

# Install dependencies (assumes virtual environment is active)
install:
	pip install -r requirements.txt

# Run the development server
run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run production server
run-prod:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Run all tests
test:
	pytest -v

# Run tests with coverage
test-cov:
	pytest --cov=app --cov-report=html --cov-report=term -v

# Run linting checks
lint:
	@echo "Running flake8..."
	@flake8 app tests || echo "flake8 not installed, skipping..."
	@echo "Checking code formatting with black..."
	@black --check app tests || echo "black not installed, skipping..."
	@echo "Checking import sorting with isort..."
	@isort --check-only app tests || echo "isort not installed, skipping..."

# Format code
format:
	@echo "Formatting code with black..."
	@black app tests || echo "black not installed, skipping..."
	@echo "Sorting imports with isort..."
	@isort app tests || echo "isort not installed, skipping..."

# Load sample data
sample:
	@echo "Loading sample data..."
	curl -X POST "http://localhost:8000/v1/transactions/import" \
		-H "x-tenant-id: 123e4567-e89b-12d3-a456-426614174000" \
		-F "file=@tests/data/transactions.csv" || echo "Server not running or sample file not found"

# Clean up generated files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	rm -f dev.db