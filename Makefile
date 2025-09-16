.PHONY: install run test lint format clean

# Install dependencies
install:
	pip3 install -r requirements.txt

# Run the development server
run:
	source venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
test:
	pytest

# Run linting
lint:
	flake8 app tests
	black --check app tests
	isort --check-only app tests

# Format code
format:
	black app tests
	isort app tests

# Clean up generated files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info