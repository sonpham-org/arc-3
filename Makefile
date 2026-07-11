.DEFAULT_GOAL := help

.PHONY: help check-workspace a108-check-ssh a108-sync a108-check-env a108-install a108-download-model a108-server a108-check-server a108-stop-server a108-server-log-path a108-tail-server a108-smoke-chat a108-smoke-tool a108-smoke-game a108-score-run a108-score-latest a108-bootstrap-report

A108_HOST ?= gx10-a108.tail57a229.ts.net
A108_SSH_OPTS ?= -o BatchMode=yes -o ConnectTimeout=10
A108_ROOT ?= $$HOME/GitHub/arc-3
A108_CONFIG ?= configs/a108.qwen36.json
A108_SMOKE_GAME ?= ft09
A108_SMOKE_RUN ?= a108-smoke-ft09
A108_SCORE_RUN_DIR ?=
A108_SERVER_START_TIMEOUT ?= 3600
A108_SERVER_TAIL_ON_WAIT ?= true
RSYNC_RSH ?= ssh $(A108_SSH_OPTS)

RSYNC_EXCLUDES := \
	--exclude .git \
	--exclude .venv \
	--exclude .cache \
	--exclude runs \
	--exclude reports \
	--exclude __pycache__ \
	--exclude '*.pyc' \
	--exclude example-run

help:
	@echo "a108 targets:"
	@echo "  make check-workspace    Validate local configs/scripts/a108 dry-runs"
	@echo "  make a108-check-ssh     Verify SSH/DNS access to A108_HOST=$(A108_HOST)"
	@echo "  make a108-sync          Rsync this workspace to A108_ROOT=$(A108_ROOT)"
	@echo "  make a108-check-env     Run target-side hardware/software checks"
	@echo "  make a108-install       Install harness dependencies on a108"
	@echo "  make a108-download-model Pre-cache the configured model on a108"
	@echo "  make a108-server        Start local vLLM server on a108"
	@echo "  make a108-check-server  Check local vLLM server health on a108"
	@echo "  make a108-stop-server   Stop the managed vLLM server on a108"
	@echo "  make a108-tail-server   Tail the managed vLLM server log on a108"
	@echo "  make a108-smoke-chat    Run one simple chat request"
	@echo "  make a108-smoke-tool    Run the tool-calling smoke test"
	@echo "  make a108-smoke-game    Run one ARC-AGI-3 smoke game"
	@echo "  make a108-score-latest  Score the newest run under ARC3-Inference/runs"
	@echo "  make a108-score-run A108_SCORE_RUN_DIR=... Score a specific run directory"
	@echo "  make a108-bootstrap-report Run sync/install/server/smoke sequence with logs"

check-workspace:
	A108_HOST="$(A108_HOST)" A108_SSH_OPTS="$(A108_SSH_OPTS)" A108_CONFIG="$(A108_CONFIG)" scripts/check_workspace.sh

a108-check-ssh:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'hostname && uname -a'

a108-sync:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'mkdir -p "$(A108_ROOT)"'
	rsync -e "$(RSYNC_RSH)" -az --delete $(RSYNC_EXCLUDES) ./ "$(A108_HOST):$(A108_ROOT)/"

a108-check-env:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)" && bash scripts/check_a108_env.sh'

a108-install:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && CONFIG_PATH="$(A108_CONFIG)" make install-a108'

a108-download-model:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && CONFIG_PATH="$(A108_CONFIG)" make download-model'

a108-server:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && CONFIG_PATH="$(A108_CONFIG)" SERVER_START_TIMEOUT="$(A108_SERVER_START_TIMEOUT)" SERVER_TAIL_ON_WAIT="$(A108_SERVER_TAIL_ON_WAIT)" make server'

a108-check-server:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && CONFIG_PATH="$(A108_CONFIG)" make check-server'

a108-stop-server:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && CONFIG_PATH="$(A108_CONFIG)" make stop-server'

a108-server-log-path:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && CONFIG_PATH="$(A108_CONFIG)" make server-log-path'

a108-tail-server:
	ssh $(A108_SSH_OPTS) -t "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && CONFIG_PATH="$(A108_CONFIG)" make tail-server-log'

a108-smoke-chat:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && CONFIG_PATH="$(A108_CONFIG)" make chat PROMPT="Answer in one sentence: what is 2+2?"'

a108-smoke-tool:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && CONFIG_PATH="$(A108_CONFIG)" make smoke-tool'

a108-smoke-game:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && CONFIG_PATH="$(A108_CONFIG)" make interactive GAME="$(A108_SMOKE_GAME)" N_PASSES=1 CONCURRENT_JOBS=1 MAX_RUNTIME_MINUTES=10 RUN_NAME="$(A108_SMOKE_RUN)"'

a108-score-run:
	@if [ -z "$(strip $(A108_SCORE_RUN_DIR))" ]; then \
		echo "A108_SCORE_RUN_DIR is required, for example: make a108-score-run A108_SCORE_RUN_DIR=runs/20260704_120000_a108-smoke-ft09"; \
		exit 1; \
	fi
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && CONFIG_PATH="$(A108_CONFIG)" make score_run SCORE_RUN_DIR="$(A108_SCORE_RUN_DIR)"'

a108-score-latest:
	ssh $(A108_SSH_OPTS) "$(A108_HOST)" 'cd "$(A108_ROOT)/ARC3-Inference" && latest="$$(ls -dt runs/*/ 2>/dev/null | head -n 1)" && if [ -z "$$latest" ]; then echo "No run directories under runs/"; exit 1; fi; echo "Scoring $$latest"; CONFIG_PATH="$(A108_CONFIG)" make score_run SCORE_RUN_DIR="$$latest"'

a108-bootstrap-report:
	A108_HOST="$(A108_HOST)" A108_SSH_OPTS="$(A108_SSH_OPTS)" A108_ROOT="$(A108_ROOT)" A108_CONFIG="$(A108_CONFIG)" A108_SMOKE_GAME="$(A108_SMOKE_GAME)" A108_SMOKE_RUN="$(A108_SMOKE_RUN)" A108_SERVER_START_TIMEOUT="$(A108_SERVER_START_TIMEOUT)" A108_SERVER_TAIL_ON_WAIT="$(A108_SERVER_TAIL_ON_WAIT)" scripts/a108_bootstrap_report.sh
