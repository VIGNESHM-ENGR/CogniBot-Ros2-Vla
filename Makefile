# CogniBot-ROS2-VLA developer commands. Run `make help`.
COMPOSE     := docker compose -f cognibot_ws/docker/docker-compose.yml
COMPOSE_DEV := $(COMPOSE) -f cognibot_ws/docker/compose.dev.yaml
PROFILES    := vlm vla twin full

.DEFAULT_GOAL := help
.PHONY: help env build build-all config sim sim-dev vlm vla full twin down logs ps shell-sim

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

env: ## Create cognibot_ws/docker/.env from the example (host UID/GID filled in)
	@test -f cognibot_ws/docker/.env || sed -e "s/^HOST_UID=.*/HOST_UID=$$(id -u)/" -e "s/^HOST_GID=.*/HOST_GID=$$(id -g)/" \
		cognibot_ws/docker/.env.example > cognibot_ws/docker/.env && echo "cognibot_ws/docker/.env ready"

build: ## Build the core, vlm and vla images
	$(COMPOSE) --profile full build sim vlm-agent vla-client

build-all: ## Build every image including the dashboard (requires dashboard sources, P3)
	$(COMPOSE) --profile full build

config: ## Validate the compose file for every profile
	@$(COMPOSE) config -q && echo "core: ok"
	@for p in $(PROFILES); do $(COMPOSE) --profile $$p config -q && echo "$$p: ok"; done

sim: ## Start the core stack (sim, motion, bridge, dashboard)
	$(COMPOSE) up -d

sim-dev: ## Core stack with GUI and live source mounts
	$(COMPOSE_DEV) up -d

vlm: ## Core + llama-swap + VLM agent
	$(COMPOSE) --profile vlm up -d

vla: ## Core + LeRobot policy server + VLA client
	$(COMPOSE) --profile vla up -d

full: ## Everything except the twin
	$(COMPOSE) --profile full up -d

twin: ## Core + digital twin connector (mock hardware by default)
	$(COMPOSE) --profile twin up -d

down: ## Stop all services in every profile
	$(COMPOSE) --profile full --profile twin down

logs: ## Follow logs (SERVICE=name to filter)
	$(COMPOSE) --profile full --profile twin logs -f $(SERVICE)

ps: ## Show service status
	$(COMPOSE) --profile full --profile twin ps

shell-sim: ## Interactive shell in the core image
	$(COMPOSE) run --rm --no-deps sim bash
