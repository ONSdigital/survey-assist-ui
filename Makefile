.PHONY: all
all: ## Show the available make targets.
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@fgrep "##" Makefile | fgrep -v fgrep

.PHONY: clean
clean: ## Clean the temporary files.
	rm -rf .mypy_cache
	rm -rf .ruff_cache	

load-design-system-templates:  ## Load the design system templates
	./get_design_system.sh

run-ui: ## Run the UI
	APP_BUILD_DATE=$(BUILD_DATE) \
	poetry run flask --app survey_assist_ui run --debug -p 8000

run-docs: ## Run the mkdocs
	poetry run mkdocs serve

check-python: ## Format the python code (auto fix)
	poetry run isort . --verbose
	poetry run black .
	poetry run ruff check . --fix
	poetry run mypy --follow-untyped-imports  . 
	poetry run pylint --verbose .
	poetry run bandit -r utils survey_assist_ui scripts

check-python-nofix: ## Format the python code (no fix)
	poetry run isort . --check --verbose
	poetry run black . --check
	poetry run ruff check .
	poetry run mypy --follow-untyped-imports  . 
	poetry run pylint --verbose .
	poetry run bandit -r utils survey_assist_ui scripts

black: ## Run black
	poetry run black .

all-tests: ## Run all unit tests
	poetry run pytest --cov=utils --cov=survey_assist_ui --cov-report=term-missing --cov-fail-under=75

route-tests: ## Run the route tests
	poetry run pytest -m route --cov=utils --cov=survey_assist_ui --cov-report=term-missing --cov-fail-under=75

utils-tests: ## Run the route tests
	poetry run pytest -m utils --cov=utils --cov=survey_assist_ui --cov-report=term-missing --cov-fail-under=75

install: ## Install the dependencies
	poetry install --only main --no-root

install-dev: ## Install the dev dependencies
	poetry install --no-root

.PHONY: colima-start
colima-start: ## Start Colima
	colima start --cpu 2 --memory 4 --disk 100

.PHONY: colima-stop
colima-stop: ## Stop Colima
	colima stop

# Set version from pyproject.toml - VERSION=$(poetry version -s)
# Set git sha - GIT_SHA=$(git rev-parse --short=12 HEAD)
# Set build date - BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VERSION ?= $(shell poetry version -s 2>/dev/null || echo 0.0.0+unknown)
GIT_SHA ?= $(shell git rev-parse --short=12 HEAD 2>/dev/null || echo unknown)
BUILD_DATE ?= $(shell date -u '+%Y-%m-%dT%H:%M:%SZ')

.PHONY: show-docker-build
show-docker-build:
	@echo VERSION=$(VERSION)
	@echo GIT_SHA=$(GIT_SHA)
	@echo BUILD_DATE=$(BUILD_DATE)

.PHONY: docker-build
docker-build: ## Build the Docker image
	DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock" docker build \
		--build-arg VERSION=$(VERSION) \
		--build-arg GIT_SHA=$(GIT_SHA) \
		--build-arg BUILD_DATE=$(BUILD_DATE) \
		-t survey-assist-ui .

# Allow CRED_FILE to be specified as part of make command
# e.g make docker-run CRED_FILE=/path/to/service-account.json
CRED_FILE ?= $(HOME)/gcp-project-creds-ui.json

# Runs as user id to mount file for dev purposes only, in production
# CRED_FILE is not used, instead GCP application default credentials are used.
.PHONY: docker-run
docker-run: ## Run the Docker container
	DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock" docker run \
		-p 8000:8000 \
		--user "$(id -u):$(id -g)" \
  		--mount type=bind,src=$(CRED_FILE),target=/run/secrets/gcp-key.json,readonly \
		-e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp-key.json \
		-e FLASK_SECRET_KEY=$(FLASK_SECRET_KEY) \
		-e BACKEND_API_URL=$(BACKEND_API_URL) \
		-e BACKEND_API_VERSION=$(BACKEND_API_VERSION) \
		-e SA_EMAIL=$(SA_EMAIL) \
		survey-assist-ui

.PHONY: docker-clean
docker-clean: ## Clean Docker resources
	DOCKER_HOST="unix://${HOME}/.colima/default/docker.sock" docker system prune -f

.PHONY: colima-status
colima-status: ## Check Colima status
	colima status
