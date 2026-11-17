# ==============================================================================
# Pharma R&D & Regulatory Radar — Local Demo & GCP Deployment Makefile
# Supports: Local ADK Modes | Google Cloud Run | Vertex AI Agent Engine
# ==============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Load variables from .env if present (can be overridden via CLI: make target PROJECT_ID=...)
-include .env

# Python & ADK binaries (auto-detect local .venv if present)
VENV_DIR ?= .venv
PYTHON := $(shell [ -x "$(VENV_DIR)/bin/python" ] && echo "$(VENV_DIR)/bin/python" || echo "python3")
PIP := $(shell [ -x "$(VENV_DIR)/bin/pip" ] && echo "$(VENV_DIR)/bin/pip" || echo "pip3")
ADK := $(shell [ -x "$(VENV_DIR)/bin/adk" ] && echo "$(VENV_DIR)/bin/adk" || echo "adk")

# Directory & Agent Paths
AGENTS_DIR ?= agents
AGENT_NAME ?= pharma_agent
AGENT_PATH := $(AGENTS_DIR)/$(AGENT_NAME)
RUNNER_SCRIPT := runners/run_programmatic.py
VERTEX_DEPLOY_SCRIPT := deployment/vertex_ai/agent_engine.py
PROMPT ?=
STREAM ?= true

# Google Cloud Configuration
PROJECT_ID ?= $(GOOGLE_CLOUD_PROJECT)
REGION ?= $(if $(GOOGLE_CLOUD_LOCATION),$(GOOGLE_CLOUD_LOCATION),us-central1)
RAW_STAGING_BUCKET := $(strip $(STAGING_BUCKET))
RESOLVED_STAGING_BUCKET := $(if $(filter-out gs://your-gcp-project-id-adk-staging,$(RAW_STAGING_BUCKET)),$(RAW_STAGING_BUCKET),gs://$(PROJECT_ID)-adk-staging)

# Cloud Run Configuration
CLOUD_RUN_SERVICE_NAME ?= pharma-rd-radar
CLOUD_RUN_MEMORY ?= 2Gi
CLOUD_RUN_CPU ?= 2
CLOUD_RUN_AUTH_FLAG ?= --allow-unauthenticated
SERVE_WEB_UI ?= true
LOCAL_DOCKER_PORT ?= 8080

# Vertex AI Agent Engine Configuration
AGENT_ENGINE_DISPLAY_NAME ?= Pharma R&D Regulatory Radar
AGENT_ENGINE_ID ?=
AGENT_ENGINE_UPDATE_FLAG := $(if $(strip $(AGENT_ENGINE_ID)),--agent_engine_id="$(strip $(AGENT_ENGINE_ID))",)

REQUIRED_GCP_APIS := \
	aiplatform.googleapis.com \
	run.googleapis.com \
	cloudbuild.googleapis.com \
	artifactregistry.googleapis.com \
	storage.googleapis.com \
	cloudtrace.googleapis.com

.PHONY: help install env check-gcp gcp-setup \
	web cli run \
	deploy-cloud-run deploy-cloud-run-docker docker-build docker-run-local delete-cloud-run \
	deploy-agent-engine deploy-agent-engine-sdk list-agent-engines delete-agent-engine \
	clean

##@ Help

help: ## Display available local demo and Google Cloud deployment targets
	@awk 'BEGIN {FS = ":.*##"; printf "\n\033[1mPharma R&D & Regulatory Radar — Makefile Targets\033[0m\n"} \
		/^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ""

##@ Local Setup & 3 Demo Modes

install: ## Create .venv and install Python dependencies
	@test -d "$(VENV_DIR)" || python3 -m venv "$(VENV_DIR)"
	"$(VENV_DIR)/bin/pip" install --upgrade pip
	"$(VENV_DIR)/bin/pip" install -r requirements.txt
	@echo "[OK] Virtual environment ready at $(VENV_DIR)"

env: ## Create .env from .env.example if it does not exist
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "[OK] Created .env from .env.example. Update your credentials before running."; \
	else \
		echo "[INFO] .env already exists (skipped)."; \
	fi

web: ## Mode 1: Launch ADK Web UI & Trace Inspector (http://localhost:8000)
	"$(ADK)" web "$(AGENTS_DIR)"

cli: ## Mode 2: Run interactive terminal session (adk run agents/pharma_agent)
	"$(ADK)" run "$(AGENT_PATH)"

run: ## Mode 3: Run async streaming Python Runner (options: PROMPT="..." STREAM=false)
	@if [ -n "$(PROMPT)" ]; then \
		PYTHONUNBUFFERED=1 STREAM="$(STREAM)" "$(PYTHON)" -u "$(RUNNER_SCRIPT)" "$(PROMPT)"; \
	else \
		PYTHONUNBUFFERED=1 STREAM="$(STREAM)" "$(PYTHON)" -u "$(RUNNER_SCRIPT)"; \
	fi

##@ Google Cloud Bootstrap

check-gcp: ## Validate PROJECT_ID and active gcloud CLI installation
	@if [ -z "$(PROJECT_ID)" ] || [ "$(PROJECT_ID)" = "your-gcp-project-id" ]; then \
		echo "[ERROR] GOOGLE_CLOUD_PROJECT / PROJECT_ID is not set."; \
		echo "Set GOOGLE_CLOUD_PROJECT in .env or pass PROJECT_ID=your-project-id."; \
		exit 1; \
	fi
	@command -v gcloud >/dev/null 2>&1 || { echo "[ERROR] gcloud CLI is not installed."; exit 1; }

gcp-setup: check-gcp ## Enable required GCP APIs and create GCS staging bucket if missing
	gcloud config set project "$(PROJECT_ID)"
	gcloud services enable $(REQUIRED_GCP_APIS) --project="$(PROJECT_ID)"
	@BUCKET_URI="$(RESOLVED_STAGING_BUCKET)"; \
	if [[ "$$BUCKET_URI" != gs://* ]]; then BUCKET_URI="gs://$$BUCKET_URI"; fi; \
	if ! gcloud storage buckets describe "$$BUCKET_URI" --project="$(PROJECT_ID)" >/dev/null 2>&1; then \
		echo "Creating staging bucket $$BUCKET_URI in $(REGION)..."; \
		gcloud storage buckets create "$$BUCKET_URI" --project="$(PROJECT_ID)" --location="$(REGION)" --uniform-bucket-level-access; \
	else \
		echo "[OK] Staging bucket $$BUCKET_URI already exists."; \
	fi

##@ Cloud Run Deployment

deploy-cloud-run: check-gcp ## Deploy to Cloud Run via native ADK CLI (includes Web UI & Cloud Trace)
	"$(ADK)" deploy cloud_run \
		--project="$(PROJECT_ID)" \
		--region="$(REGION)" \
		--service_name="$(CLOUD_RUN_SERVICE_NAME)" \
		--app_name="$(AGENT_NAME)" \
		--with_ui \
		--trace_to_cloud \
		"./$(AGENT_PATH)" \
		-- $(CLOUD_RUN_AUTH_FLAG) --memory="$(CLOUD_RUN_MEMORY)" --cpu="$(CLOUD_RUN_CPU)"

deploy-cloud-run-docker: check-gcp ## Deploy custom FastAPI + Dockerfile container to Cloud Run via gcloud
	gcloud run deploy "$(CLOUD_RUN_SERVICE_NAME)" \
		--source . \
		--project="$(PROJECT_ID)" \
		--region="$(REGION)" \
		--platform=managed \
		--memory="$(CLOUD_RUN_MEMORY)" \
		--cpu="$(CLOUD_RUN_CPU)" \
		--port=8080 \
		--set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$(PROJECT_ID),GOOGLE_CLOUD_LOCATION=$(REGION),SERVE_WEB_UI=$(SERVE_WEB_UI)" \
		$(CLOUD_RUN_AUTH_FLAG)

docker-build: ## Build production Cloud Run Docker image locally
	docker build -t "$(CLOUD_RUN_SERVICE_NAME):local" .

docker-run-local: docker-build ## Run the Cloud Run container locally on http://localhost:8080
	docker run --rm -it \
		-p "$(LOCAL_DOCKER_PORT):8080" \
		--env-file .env \
		-e PORT=8080 \
		-e SERVE_WEB_UI="$(SERVE_WEB_UI)" \
		"$(CLOUD_RUN_SERVICE_NAME):local"

delete-cloud-run: check-gcp ## Delete the deployed Cloud Run service
	gcloud run services delete "$(CLOUD_RUN_SERVICE_NAME)" \
		--project="$(PROJECT_ID)" \
		--region="$(REGION)" \
		--quiet

##@ Vertex AI Agent Engine Deployment

deploy-agent-engine: check-gcp ## Deploy to Vertex AI Agent Engine via native ADK CLI
	"$(ADK)" deploy agent_engine \
		--project="$(PROJECT_ID)" \
		--region="$(REGION)" \
		--staging_bucket="$(RESOLVED_STAGING_BUCKET)" \
		--display_name="$(AGENT_ENGINE_DISPLAY_NAME)" \
		--otel_to_cloud \
		$(AGENT_ENGINE_UPDATE_FLAG) \
		"./$(AGENT_PATH)"

deploy-agent-engine-sdk: check-gcp ## Deploy to Vertex AI Agent Engine programmatically via Python SDK
	GOOGLE_CLOUD_PROJECT="$(PROJECT_ID)" \
	GOOGLE_CLOUD_LOCATION="$(REGION)" \
	STAGING_BUCKET="$(RESOLVED_STAGING_BUCKET)" \
	AGENT_ENGINE_DISPLAY_NAME="$(AGENT_ENGINE_DISPLAY_NAME)" \
	"$(PYTHON)" "$(VERTEX_DEPLOY_SCRIPT)" --action deploy

list-agent-engines: check-gcp ## List active Vertex AI Agent Engine instances in the project/region
	GOOGLE_CLOUD_PROJECT="$(PROJECT_ID)" \
	GOOGLE_CLOUD_LOCATION="$(REGION)" \
	"$(PYTHON)" "$(VERTEX_DEPLOY_SCRIPT)" --action list

delete-agent-engine: check-gcp ## Delete a Vertex AI Agent Engine instance (uses AGENT_ENGINE_ID or saved metadata)
	GOOGLE_CLOUD_PROJECT="$(PROJECT_ID)" \
	GOOGLE_CLOUD_LOCATION="$(REGION)" \
	AGENT_ENGINE_ID="$(AGENT_ENGINE_ID)" \
	"$(PYTHON)" "$(VERTEX_DEPLOY_SCRIPT)" --action delete

##@ Maintenance

clean: ## Remove Python caches and temporary ADK build artifacts
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache .adk
