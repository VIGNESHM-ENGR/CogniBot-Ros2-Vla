# CogniBot-ROS2-VLA developer commands. Run `make help`.
COMPOSE     := docker compose -f cognibot_ws/docker/docker-compose.yml
COMPOSE_DEV := $(COMPOSE) -f cognibot_ws/docker/compose.dev.yaml
PROFILES    := vlm vla twin full

.DEFAULT_GOAL := help
.PHONY: help env deps build build-all config sim sim-dev demo moveit test vlm vla full twin down logs ps shell-sim

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

env: ## Create cognibot_ws/docker/.env from the example (host UID/GID filled in)
	@test -f cognibot_ws/docker/.env || sed -e "s/^HOST_UID=.*/HOST_UID=$$(id -u)/" -e "s/^HOST_GID=.*/HOST_GID=$$(id -g)/" \
		cognibot_ws/docker/.env.example > cognibot_ws/docker/.env && echo "cognibot_ws/docker/.env ready"

deps: ## Fetch pinned third-party ROS sources into cognibot_ws/src/third_party (host, for sim-dev)
	uvx --from vcstool==0.3.0 --with "setuptools<81" vcs import cognibot_ws/src/third_party < cognibot_ws/third_party.repos

build: ## Build the core, vlm and vla images
	$(COMPOSE) --profile full build sim vlm-agent vla-client

build-all: ## Build every image including the dashboard (requires dashboard sources, P3)
	$(COMPOSE) --profile full build

config: ## Validate the compose file for every profile
	@$(COMPOSE) config -q && echo "core: ok"
	@for p in $(PROFILES); do $(COMPOSE) --profile $$p config -q && echo "$$p: ok"; done

# motion and dashboard join `sim` once their launch files and sources exist.
sim: ## Headless simulation + browser bridge (rosbridge :9090, MJPEG :8080)
	$(COMPOSE) up -d sim bridge

sim-dev: ## Simulation with the MuJoCo viewer over X11 and live source mounts (run `make deps` first)
	xhost +si:localuser:$$(whoami) >/dev/null
	$(COMPOSE_DEV) up sim

demo: ## Open the MuJoCo viewer and run the scripted SO-101 pick-and-place (run `make deps` first)
	xhost +si:localuser:$$(whoami) >/dev/null
	$(COMPOSE_DEV) run --rm --no-deps sim bash -c '\
	  ros2 launch cognibot_bringup sim.launch.py robot:=so101 headless:=false > /tmp/sim.log 2>&1 & \
	  sleep 12 && python3 /ws/src/cognibot_motion/scripts/demo_pick_place.py; \
	  echo "Demo finished; close the viewer or press Ctrl+C to exit"; wait'

moveit: ## MuJoCo viewer + move_group + RViz: drag the goal marker, Plan & Execute (run `make deps` first)
	xhost +si:localuser:$$(whoami) >/dev/null
	$(COMPOSE_DEV) run --rm --no-deps sim bash -c '\
	  ros2 launch cognibot_bringup sim.launch.py robot:=so101 headless:=false > /tmp/sim.log 2>&1 & \
	  sleep 10 && ros2 launch cognibot_motion move_group.launch.py robot:=so101 rviz:=true'

test: ## Build and run every workspace test (incl. GPU launch tests) in the core image
	$(COMPOSE) run --rm --no-deps -v $(CURDIR)/cognibot_ws/src:/src:ro --entrypoint bash sim -c '\
	  source /opt/ros/jazzy/setup.bash && source /opt/cognibot/underlay/setup.bash && \
	  mkdir -p /tmp/w && cd /tmp/w && ln -s /src src && \
	  colcon build --packages-up-to cognibot_common cognibot_sim cognibot_bringup cognibot_motion \
	    --packages-skip cognibot_interfaces --event-handlers console_cohesion- && \
	  source install/setup.bash && \
	  colcon test --packages-select cognibot_common cognibot_sim cognibot_motion && colcon test-result --verbose'

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
