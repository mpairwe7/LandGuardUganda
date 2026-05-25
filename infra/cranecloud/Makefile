# Crane Cloud deploy wrappers — LandGuard Uganda
#
# Usage:
#   make -C infra/cranecloud init                ENV=pilot
#   make -C infra/cranecloud deploy              ENV=pilot
#   make -C infra/cranecloud update-backend      ENV=pilot
#   make -C infra/cranecloud update-frontend     ENV=pilot
#   make -C infra/cranecloud list                ENV=pilot
#
# Or from infra/cranecloud/:
#   make deploy ENV=pilot
#
# Defaults to ENV=staging. Source of truth for what gets deployed is
# `manifest.yaml`; per-environment values live in `environments/<env>.env`.

ENV          ?= staging
ENV_FILE     := environments/$(ENV).env
ENV_TEMPLATE := environments/$(ENV).env.example

# Colour helpers — terminals without colour see no escape codes (TERM=dumb).
ifeq ($(shell test -t 1 && echo tty),tty)
  C_GREEN  := \033[32m
  C_RED    := \033[31m
  C_YELLOW := \033[33m
  C_BLUE   := \033[34m
  C_RESET  := \033[0m
else
  C_GREEN  :=
  C_RED    :=
  C_YELLOW :=
  C_BLUE   :=
  C_RESET  :=
endif

.PHONY: help init env-check deploy deploy-backend deploy-frontend \
        update-backend update-frontend list info logout clean

help:  ## Show this help (default target)
	@echo "$(C_BLUE)LandGuard Uganda — Crane Cloud deploy$(C_RESET)"
	@echo "Usage:  make <target> ENV=<staging|pilot|production>"
	@echo "Current ENV: $(C_YELLOW)$(ENV)$(C_RESET)"
	@echo
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  $(C_GREEN)%-22s$(C_RESET) %s\n", $$1, $$2}'

init:  ## First-time guidance for a new environment
	@echo "$(C_BLUE)One-time setup for ENV=$(ENV):$(C_RESET)"
	@echo
	@echo "  1. From your interactive shell (not from CI / non-tty):"
	@echo "     $(C_YELLOW)cranecloud auth user$(C_RESET)                # confirm authentication"
	@echo "     $(C_YELLOW)cranecloud projects list$(C_RESET)            # find or create the project"
	@echo
	@echo "  2. If the project doesn't exist yet, create it once:"
	@echo "     $(C_YELLOW)cranecloud projects create$(C_RESET)"
	@echo "     # follow prompts; suggested name: landguard-uganda-$(ENV)"
	@echo
	@echo "  3. Copy the env template and fill in real values:"
	@echo "     $(C_YELLOW)cp $(ENV_TEMPLATE) $(ENV_FILE)$(C_RESET)"
	@echo "     # then edit $(ENV_FILE) — set CRANECLOUD_PROJECT_ID,"
	@echo "     # JWT_HS256_SECRET (32+ chars), PII_ENCRYPTION_KEY (base64 ≥ 32B),"
	@echo "     # DATABASE_URL, REDIS_URL, NIRA_*, OTEL_*, blockchain settings."
	@echo
	@echo "  4. Then:"
	@echo "     $(C_YELLOW)make deploy ENV=$(ENV)$(C_RESET)"
	@echo

env-check:  ## Verify the env file exists and is readable
	@if [ ! -f "$(ENV_FILE)" ]; then \
	  printf "$(C_RED)Missing $(ENV_FILE)$(C_RESET)\n"; \
	  printf "Copy the template: $(C_YELLOW)cp $(ENV_TEMPLATE) $(ENV_FILE)$(C_RESET) and fill in values.\n"; \
	  exit 1; \
	fi
	@if [ ! -r "$(ENV_FILE)" ]; then \
	  printf "$(C_RED)$(ENV_FILE) is not readable.$(C_RESET)\n"; \
	  exit 1; \
	fi
	@printf "$(C_GREEN)✓$(C_RESET) $(ENV_FILE) present\n"

deploy: env-check deploy-backend deploy-frontend  ## Deploy backend + frontend
	@printf "$(C_GREEN)✓$(C_RESET) Deploy complete for ENV=$(ENV)\n"
	@printf "Capture the returned APP_IDs above into $(ENV_FILE) as\n"
	@printf "  BACKEND_APP_ID=<uuid>\n  FRONTEND_APP_ID=<uuid>\n"
	@printf "Subsequent rollouts use $(C_YELLOW)make update-backend$(C_RESET) / $(C_YELLOW)make update-frontend$(C_RESET).\n"

deploy-backend: env-check  ## Deploy the FastAPI backend (one-time per env)
	@printf "$(C_BLUE)→ Deploying backend (ENV=$(ENV))$(C_RESET)\n"
	@set -a; . ./$(ENV_FILE); set +a; \
	 cranecloud apps deploy \
	   --project_id "$$CRANECLOUD_PROJECT_ID" \
	   --name "$$BACKEND_APP_NAME" \
	   --image "$$BACKEND_IMAGE:$$BACKEND_IMAGE_TAG" \
	   --port "$$BACKEND_PORT" \
	   --replicas "$$BACKEND_REPLICAS" \
	   -e "APP_ENV=$$APP_ENV" \
	   -e "APP_NAME=$$APP_NAME" \
	   -e "LOG_LEVEL=$$LOG_LEVEL" \
	   -e "DEMO_MODE=$$DEMO_MODE" \
	   -e "DB_BACKEND=$$DB_BACKEND" \
	   -e "POSTGRES_DSN=$$POSTGRES_DSN" \
	   -e "REDIS_URL=$$REDIS_URL" \
	   -e "AUTH_MODE=$$AUTH_MODE" \
	   -e "JWT_HS256_SECRET=$$JWT_HS256_SECRET" \
	   -e "JWT_ISSUER=$$JWT_ISSUER" \
	   -e "JWT_AUDIENCE=$$JWT_AUDIENCE" \
	   -e "OIDC_JWKS_URL=$$OIDC_JWKS_URL" \
	   -e "BLOCKCHAIN_PROVIDER=$$BLOCKCHAIN_PROVIDER" \
	   -e "SEPOLIA_RPC_URL=$$SEPOLIA_RPC_URL" \
	   -e "SEPOLIA_CHAIN_ID=$$SEPOLIA_CHAIN_ID" \
	   -e "REGISTRAR_PRIVATE_KEY=$$REGISTRAR_PRIVATE_KEY" \
	   -e "CONTRACT_ADDRESS_FILE=$$CONTRACT_ADDRESS_FILE" \
	   -e "ANCHOR_FLUSH_INTERVAL_SECONDS=$$ANCHOR_FLUSH_INTERVAL_SECONDS" \
	   -e "ANCHOR_FLUSH_BATCH_SIZE=$$ANCHOR_FLUSH_BATCH_SIZE" \
	   -e "MULTISIG_ENABLED=$$MULTISIG_ENABLED" \
	   -e "NIRA_PROVIDER=$$NIRA_PROVIDER" \
	   -e "NIRA_BASE_URL=$$NIRA_BASE_URL" \
	   -e "NIRA_API_KEY=$$NIRA_API_KEY" \
	   -e "PII_ENCRYPTION_KEY=$$PII_ENCRYPTION_KEY" \
	   -e "RATE_LIMIT_PUBLIC_VERIFY=$$RATE_LIMIT_PUBLIC_VERIFY" \
	   -e "OTEL_ENABLED=$$OTEL_ENABLED" \
	   -e "OTEL_EXPORTER_OTLP_ENDPOINT=$$OTEL_EXPORTER_OTLP_ENDPOINT" \
	   -e "OTEL_SERVICE_NAME=$$OTEL_SERVICE_NAME" \
	   -e "CORS_ALLOW_ORIGINS=$$CORS_ALLOW_ORIGINS"

deploy-frontend: env-check  ## Deploy the Next.js frontend (one-time per env)
	@printf "$(C_BLUE)→ Deploying frontend (ENV=$(ENV))$(C_RESET)\n"
	@set -a; . ./$(ENV_FILE); set +a; \
	 cranecloud apps deploy \
	   --project_id "$$CRANECLOUD_PROJECT_ID" \
	   --name "$$FRONTEND_APP_NAME" \
	   --image "$$FRONTEND_IMAGE:$$FRONTEND_IMAGE_TAG" \
	   --port "$$FRONTEND_PORT" \
	   --replicas "$$FRONTEND_REPLICAS" \
	   -e "BACKEND_URL=$$BACKEND_URL" \
	   -e "NEXT_PUBLIC_APP_NAME=$$NEXT_PUBLIC_APP_NAME" \
	   -e "NEXT_PUBLIC_DEMO_MODE=$$NEXT_PUBLIC_DEMO_MODE" \
	   -e "NEXT_PUBLIC_DEFAULT_DISTRICT_ID=$$NEXT_PUBLIC_DEFAULT_DISTRICT_ID" \
	   -e "DEMO_TOKEN=$$DEMO_TOKEN"

update-backend: env-check  ## Roll out a new backend image to the existing app
	@set -a; . ./$(ENV_FILE); set +a; \
	 if [ -z "$$BACKEND_APP_ID" ]; then \
	   printf "$(C_RED)BACKEND_APP_ID is not set in $(ENV_FILE).$(C_RESET)\n"; \
	   printf "Run $(C_YELLOW)make list ENV=$(ENV)$(C_RESET) to find it, then add to the env file.\n"; \
	   exit 1; \
	 fi; \
	 printf "$(C_BLUE)→ Updating backend $$BACKEND_APP_ID (ENV=$(ENV))$(C_RESET)\n"; \
	 cranecloud apps update "$$BACKEND_APP_ID" \
	   --image "$$BACKEND_IMAGE:$$BACKEND_IMAGE_TAG" \
	   --replicas "$$BACKEND_REPLICAS"

update-frontend: env-check  ## Roll out a new frontend image to the existing app
	@set -a; . ./$(ENV_FILE); set +a; \
	 if [ -z "$$FRONTEND_APP_ID" ]; then \
	   printf "$(C_RED)FRONTEND_APP_ID is not set in $(ENV_FILE).$(C_RESET)\n"; \
	   printf "Run $(C_YELLOW)make list ENV=$(ENV)$(C_RESET) to find it, then add to the env file.\n"; \
	   exit 1; \
	 fi; \
	 printf "$(C_BLUE)→ Updating frontend $$FRONTEND_APP_ID (ENV=$(ENV))$(C_RESET)\n"; \
	 cranecloud apps update "$$FRONTEND_APP_ID" \
	   --image "$$FRONTEND_IMAGE:$$FRONTEND_IMAGE_TAG" \
	   --replicas "$$FRONTEND_REPLICAS"

list: env-check  ## List apps in the configured Crane Cloud project
	@set -a; . ./$(ENV_FILE); set +a; \
	 cranecloud apps list --project_id "$$CRANECLOUD_PROJECT_ID"

info: env-check  ## Get details of one app (pass APP_ID=...)
	@if [ -z "$(APP_ID)" ]; then \
	  printf "$(C_RED)APP_ID required.$(C_RESET) Example: make info ENV=$(ENV) APP_ID=<uuid>\n"; \
	  exit 1; \
	fi
	@cranecloud apps info $(APP_ID)

logout:  ## Log out of the Crane Cloud CLI session
	@cranecloud auth logout

clean:  ## Remove any locally cached deploy artefacts (does not affect Crane Cloud)
	@find . -name "*.deploy.log" -type f -delete 2>/dev/null || true
	@printf "$(C_GREEN)✓$(C_RESET) Local cleanup done\n"

.DEFAULT_GOAL := help
