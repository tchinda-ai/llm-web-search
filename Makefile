SHELL :=/bin/bash

.PHONY: clean check setup docker-up docker-down docker-logs
.DEFAULT_GOAL=help
VENV_DIR = .venv
PYTHON_VERSION = python3.11

check: # Ruff check
	@ruff check .
	@echo "✅ Check complete!"

fix: # Fix auto-fixable linting issues
	@ruff check app.py --fix

clean: # Clean temporary files
	@rm -rf __pycache__ .pytest_cache
	@find . -name '*.pyc' -exec rm -r {} +
	@find . -name '__pycache__' -exec rm -r {} +
	@rm -rf build dist
	@find . -name '*.egg-info' -type d -exec rm -r {} +

run: # Run the application
	@streamlit run app.py

setup: # Initial project setup
	@echo "Creating virtual env at: $(VENV_DIR)"
	@$(PYTHON_VERSION) -m venv $(VENV_DIR)
	@echo "Installing dependencies..."
	@source $(VENV_DIR)/bin/activate && pip install -r requirements/requirements-dev.txt && pip install -r requirements/requirements.txt
	@echo -e "\n✅ Done.\n🎉 Run the following commands to get started:\n\n ➡️ source $(VENV_DIR)/bin/activate\n ➡️ make run\n"

docker-up: # Build and start the full stack (Ollama + Streamlit app)
	@docker compose up --build -d
	@echo "✅ Stack is up! Open http://localhost:8501"

docker-down: # Stop and remove containers
	@docker compose down

docker-logs: # Follow logs from all containers
	@docker compose logs -f


help: # Show this help
	@egrep -h '\s#\s' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?# "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
