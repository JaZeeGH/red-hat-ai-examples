SHELL          := bash
AGENT_NAME     := $(shell python3 -c "import re; print(re.search(r'^name:\s*(.+)', open('agent.yaml').read(), re.M).group(1).strip())")
REPO_ROOT      := $(shell git rev-parse --show-toplevel 2>/dev/null || echo ../../../..)
CHART_DIR      := deployment
VALUES_FILE    := values.yaml
CONTAINER_CLI  := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)

.PHONY: init re-init run-app run-app-fresh run-cli build push build-openshift deploy undeploy deploy-guardrails undeploy-guardrails deploy-all undeploy-all test test-integration test-auth-integration dry-run help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

re-init: ## Activate venv and reload .env variables
	@source .venv/bin/activate && set -a && source .env && set +a && \
	  echo "Venv activated and .env variables loaded."

init: ## Copy .env.example to .env for configuration
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example - edit it with your configuration"; else echo ".env already exists - skipping"; fi

run-app: ## Run agent locally with hot-reload
	@source .venv/bin/activate && set -a && source .env && set +a && \
	  if lsof -ti:$${PORT:-8000} >/dev/null 2>&1; then \
	    echo "ERROR: Port $${PORT:-8000} is already in use." && \
	    echo "  Change PORT in .env or run: make run-app-fresh" && \
	    exit 1; \
	  fi && \
	  uv run $${MLFLOW_TRACKING_URI:+--extra tracing} uvicorn main:app --host 127.0.0.1 --port $${PORT:-8000} --reload --reload-exclude .venv

run-app-fresh: ## Kill existing process on port and run agent with hot-reload
	@source .venv/bin/activate && set -a && source .env && set +a && \
	  echo "==> Killing existing process on port $${PORT:-8000}..." && \
	  lsof -ti:$${PORT:-8000} | xargs kill -9 2>/dev/null; true && \
	  uv run $${MLFLOW_TRACKING_URI:+--extra tracing} uvicorn main:app --host 127.0.0.1 --port $${PORT:-8000} --reload --reload-exclude .venv

run-cli: ## Run interactive CLI chat (no web server)
	@source .venv/bin/activate && set -a && source .env && set +a && \
	  cd examples && uv run $${MLFLOW_TRACKING_URI:+--extra tracing} python execute_ai_service_locally.py

build: ## Build container image locally (podman/docker)
	@[ -n "$(CONTAINER_CLI)" ] || { echo "ERROR: neither podman nor docker found in PATH"; exit 1; } && \
	  source .env && \
	  [ -n "$${CONTAINER_IMAGE}" ] || { echo "ERROR: CONTAINER_IMAGE is not set in .env"; exit 1; } && \
	  $(CONTAINER_CLI) build --platform linux/amd64 -t "$${CONTAINER_IMAGE}" -f Dockerfile .

push: ## Push container image to registry
	@[ -n "$(CONTAINER_CLI)" ] || { echo "ERROR: neither podman nor docker found in PATH"; exit 1; } && \
	  source .env && \
	  [ -n "$${CONTAINER_IMAGE}" ] || { echo "ERROR: CONTAINER_IMAGE is not set in .env"; exit 1; } && \
	  $(CONTAINER_CLI) push "$${CONTAINER_IMAGE}"

build-openshift: ## Build image in-cluster via OpenShift BuildConfig (no podman/docker needed)
	@oc new-build --strategy=docker --binary --name=$(AGENT_NAME) --to=$(AGENT_NAME):latest 2>/dev/null || true && \
	  oc start-build $(AGENT_NAME) --from-dir=. --follow && \
	  NS=$$(oc project -q) && \
	  echo "" && \
	  echo "Image built. To deploy, set in .env:" && \
	  echo "  CONTAINER_IMAGE=image-registry.openshift-image-registry.svc:5000/$$NS/$(AGENT_NAME):latest"

_check-env:
	@set -a && source .env 2>/dev/null && set +a; \
	  missing=""; \
	  for var in $$(sed -n '/^ *required:/,/^ *[a-z]/{ /^ *- /s/^ *- *//p; }' agent.yaml); do \
	    eval val="\$$$$var"; \
	    [ -n "$$val" ] || missing="$$missing $$var"; \
	  done; \
	  [ -z "$$missing" ] || { echo "ERROR: Missing required env vars:$$missing"; exit 1; }

deploy: _check-env ## Deploy to OpenShift/K8s via Helm
	@source .env && \
	  AUTH_ALLOWLIST="$${AUTH_ALLOWED_SERVICEACCOUNTS:-$${AUTH_ALLOWED_SERVICEACCOUNT}}" && \
	  AUTH_ALLOWLIST_ARGS="" && \
	  if [ -n "$$AUTH_ALLOWLIST" ]; then \
	    IFS=',' read -r -a AUTH_ALLOWLIST_ITEMS <<< "$$AUTH_ALLOWLIST"; \
	    for idx in "$${!AUTH_ALLOWLIST_ITEMS[@]}"; do \
	      account="$${AUTH_ALLOWLIST_ITEMS[$$idx]}"; \
	      account="$$(echo -n "$$account" | tr -d '[:space:]')"; \
	      [ -n "$$account" ] || continue; \
	      AUTH_ALLOWLIST_ARGS="$$AUTH_ALLOWLIST_ARGS --set-string auth.allowedServiceAccounts[$$idx]=$$account"; \
	    done; \
	  fi && \
	  [ -n "$${CONTAINER_IMAGE}" ] || { echo "ERROR: CONTAINER_IMAGE is not set in .env"; exit 1; } && \
	  LAST_SEG="$${CONTAINER_IMAGE##*/}" && if [[ "$$LAST_SEG" == *:* ]]; then IMAGE_REPO="$${CONTAINER_IMAGE%:*}"; IMAGE_TAG="$${LAST_SEG##*:}"; else IMAGE_REPO="$${CONTAINER_IMAGE}"; IMAGE_TAG="latest"; fi && \
	  trap 'rm -f .helm-secrets.yaml' EXIT && \
	  umask 077 && \
	  { printf 'secrets:\n  apiKey: "%s"\n' "$${API_KEY}"; \
	    [ -z "$${MLFLOW_TRACKING_TOKEN}" ] || printf '  mlflowTrackingToken: "%s"\n' "$${MLFLOW_TRACKING_TOKEN}"; \
	  } > .helm-secrets.yaml && \
	  helm upgrade --install $(AGENT_NAME) $(CHART_DIR) \
	    -f $(VALUES_FILE) \
	    -f .helm-secrets.yaml \
	    --set image.repository="$${IMAGE_REPO}" \
	    --set image.tag="$${IMAGE_TAG}" \
	    --set env.BASE_URL="$${BASE_URL}" \
	    --set env.MODEL_ID="$${MODEL_ID}" \
	    $${AUTH_ENABLED:+--set "auth.enabled=$${AUTH_ENABLED}"} \
	    $${AUTH_ENABLED:+--set "serviceAccount.create=$${AUTH_ENABLED}"} \
	    $${AUTH_AUDIENCE:+--set-string "auth.audience=$${AUTH_AUDIENCE}"} \
	    $${AUTH_ALLOWLIST_ARGS} \
	    $${MLFLOW_TRACKING_URI:+--set env.MLFLOW_TRACKING_URI="$${MLFLOW_TRACKING_URI}"} \
	    $${MLFLOW_EXPERIMENT_NAME:+--set env.MLFLOW_EXPERIMENT_NAME="$${MLFLOW_EXPERIMENT_NAME}"} \
	    $${MLFLOW_TRACKING_AUTH:+--set env.MLFLOW_TRACKING_AUTH="$${MLFLOW_TRACKING_AUTH}"} \
	    $${MLFLOW_TRACKING_INSECURE_TLS:+--set env.MLFLOW_TRACKING_INSECURE_TLS="$${MLFLOW_TRACKING_INSECURE_TLS}"} \
	    $${MLFLOW_TRACKING_SERVER_CERT_PATH:+--set env.MLFLOW_TRACKING_SERVER_CERT_PATH="$${MLFLOW_TRACKING_SERVER_CERT_PATH}"} \
	    $${MLFLOW_WORKSPACE:+--set env.MLFLOW_WORKSPACE="$${MLFLOW_WORKSPACE}"} && \
	  if command -v oc >/dev/null 2>&1; then \
	    echo "" && echo "Waiting for rollout to complete..." && \
	    if oc rollout status deployment/$(AGENT_NAME) --timeout=120s; then \
	      ROUTE=$$(oc get route $(AGENT_NAME) -o jsonpath='{.spec.host}' 2>/dev/null || true); \
	      if [ -n "$$ROUTE" ]; then echo "" && echo "Agent is available at: https://$$ROUTE"; fi; \
	    else \
	      echo "" && echo "WARNING: Rollout did not complete successfully. Check pod status with:" && \
	      echo "  oc get pods -l app.kubernetes.io/name=$(AGENT_NAME)" && \
	      echo "  oc logs deployment/$(AGENT_NAME)"; \
	    fi; \
	  fi

dry-run: _check-env ## Render Helm templates without deploying
	@source .env && \
	  AUTH_ALLOWLIST="$${AUTH_ALLOWED_SERVICEACCOUNTS:-$${AUTH_ALLOWED_SERVICEACCOUNT}}" && \
	  AUTH_ALLOWLIST_ARGS="" && \
	  if [ -n "$$AUTH_ALLOWLIST" ]; then \
	    IFS=',' read -r -a AUTH_ALLOWLIST_ITEMS <<< "$$AUTH_ALLOWLIST"; \
	    for idx in "$${!AUTH_ALLOWLIST_ITEMS[@]}"; do \
	      account="$${AUTH_ALLOWLIST_ITEMS[$$idx]}"; \
	      account="$$(echo -n "$$account" | tr -d '[:space:]')"; \
	      [ -n "$$account" ] || continue; \
	      AUTH_ALLOWLIST_ARGS="$$AUTH_ALLOWLIST_ARGS --set-string auth.allowedServiceAccounts[$$idx]=$$account"; \
	    done; \
	  fi && \
	  [ -n "$${CONTAINER_IMAGE}" ] || { echo "ERROR: CONTAINER_IMAGE is not set in .env"; exit 1; } && \
	  LAST_SEG="$${CONTAINER_IMAGE##*/}" && if [[ "$$LAST_SEG" == *:* ]]; then IMAGE_REPO="$${CONTAINER_IMAGE%:*}"; IMAGE_TAG="$${LAST_SEG##*:}"; else IMAGE_REPO="$${CONTAINER_IMAGE}"; IMAGE_TAG="latest"; fi && \
	  helm template $(AGENT_NAME) $(CHART_DIR) \
	    -f $(VALUES_FILE) \
	    --set secrets.apiKey="REDACTED" \
	    --set image.repository="$${IMAGE_REPO}" \
	    --set image.tag="$${IMAGE_TAG}" \
	    --set env.BASE_URL="$${BASE_URL}" \
	    --set env.MODEL_ID="$${MODEL_ID}" \
	    $${AUTH_ENABLED:+--set "auth.enabled=$${AUTH_ENABLED}"} \
	    $${AUTH_ENABLED:+--set "serviceAccount.create=$${AUTH_ENABLED}"} \
	    $${AUTH_AUDIENCE:+--set-string "auth.audience=$${AUTH_AUDIENCE}"} \
	    $${AUTH_ALLOWLIST_ARGS} \
	    $${MLFLOW_TRACKING_URI:+--set env.MLFLOW_TRACKING_URI="$${MLFLOW_TRACKING_URI}"} \
	    $${MLFLOW_TRACKING_TOKEN:+--set secrets.mlflowTrackingToken="REDACTED"} \
	    $${MLFLOW_EXPERIMENT_NAME:+--set env.MLFLOW_EXPERIMENT_NAME="$${MLFLOW_EXPERIMENT_NAME}"} \
	    $${MLFLOW_TRACKING_AUTH:+--set env.MLFLOW_TRACKING_AUTH="$${MLFLOW_TRACKING_AUTH}"} \
	    $${MLFLOW_TRACKING_INSECURE_TLS:+--set env.MLFLOW_TRACKING_INSECURE_TLS="$${MLFLOW_TRACKING_INSECURE_TLS}"} \
	    $${MLFLOW_TRACKING_SERVER_CERT_PATH:+--set env.MLFLOW_TRACKING_SERVER_CERT_PATH="$${MLFLOW_TRACKING_SERVER_CERT_PATH}"} \
	    $${MLFLOW_WORKSPACE:+--set env.MLFLOW_WORKSPACE="$${MLFLOW_WORKSPACE}"}

undeploy: ## Remove deployment from cluster
	@helm uninstall $(AGENT_NAME) 2>/dev/null || echo "Release $(AGENT_NAME) not found — skipping." && \
	  oc delete buildconfig $(AGENT_NAME) --ignore-not-found && \
	  oc delete imagestream $(AGENT_NAME) --ignore-not-found && \
	  echo "Agent undeployed."

deploy-guardrails: ## Deploy NeMo Guardrails to the cluster
	@source .env && \
	  NS=$$(oc project -q) && \
	  echo "==> Deploying NeMo Guardrails to namespace $$NS..." && \
	  echo "==> Applying ConfigMap..." && \
	  sed -e "s|MODEL_ID_PLACEHOLDER|$${MODEL_ID}|g" \
	      -e "s|BASE_URL_PLACEHOLDER|$${LLM_BASE_URL:-$${BASE_URL}}|g" \
	      deploy/manifests/nemoguardrails-configmap.yaml | oc apply -f - && \
	  echo "==> Creating guardrails secret..." && \
	  oc create secret generic langgraph-react-agent-guardrails-secrets \
	    --from-literal=api-key="$${API_KEY}" \
	    --dry-run=client -o yaml | oc apply -f - && \
	  echo "==> Applying NemoGuardrails CR..." && \
	  oc apply -f deploy/manifests/nemoguardrails-cr.yaml && \
	  echo "" && \
	  echo "Waiting for guardrails pod to be ready (max 120s)..." && \
	  oc wait --for=condition=Available deployment/langgraph-react-agent-guardrails --timeout=120s 2>/dev/null || \
	    echo "WARNING: Guardrails deployment not ready yet. Check: oc get pods -l app.kubernetes.io/name=langgraph-react-agent-guardrails" && \
	  echo "" && \
	  echo "Guardrails deployed. Update .env to route through the guardrails proxy:" && \
	  echo "  BASE_URL=http://langgraph-react-agent-guardrails.$$NS.svc.cluster.local/v1" && \
	  echo "Then redeploy the agent: make deploy"

undeploy-guardrails: ## Remove NeMo Guardrails from the cluster
	@echo "==> Removing NeMo Guardrails..." && \
	  oc delete nemoguardrails langgraph-react-agent-guardrails --ignore-not-found && \
	  oc delete configmap langgraph-react-agent-guardrails-config --ignore-not-found && \
	  oc delete secret langgraph-react-agent-guardrails-secrets --ignore-not-found && \
	  echo "Guardrails resources removed."

deploy-all: deploy-guardrails deploy ## Deploy guardrails and agent together

undeploy-all: undeploy undeploy-guardrails ## Remove agent and guardrails

test: ## Run unit tests
	uv run --extra dev python -m pytest tests/ --ignore=tests/integration --ignore=tests/behavioral $(PYTEST_ARGS)

test-integration: ## Run integration deployment test
	PYTHONPATH=$$(git rev-parse --show-toplevel)/tests \
	  uv run --extra dev python -m pytest tests/integration/test_deployment.py \
	    -v --tb=long --junitxml=results.xml

test-auth-integration: ## Run auth-enabled integration deployment test
	PYTHONPATH=$$(git rev-parse --show-toplevel)/tests \
	  uv run --extra dev python -m pytest tests/integration/test_auth.py \
	    -v --tb=long --junitxml=results-auth.xml
