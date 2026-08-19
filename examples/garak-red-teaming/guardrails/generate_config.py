#!/usr/bin/env python3
"""Generate guardrails/config/local/config.yaml from config.yaml.example.

Reads MODEL_ID, LLM_BASE_URL, and API_KEY from the environment (or .env)
and injects them into the config template. The generated config.yaml is
gitignored to prevent accidental credential commits.

Invoked by Makefile targets that start the guardrails server locally.
For cluster deployment, use the ConfigMap in deploy/manifests/ instead.
"""

import os

import yaml


def generate_config(config_path: str, *, omit_api_key: bool = False) -> list[str]:
    """Rewrite config_path in place with env-driven model overrides.

    Returns a human-readable summary of what was applied.

    When omit_api_key is True, api_key is omitted so cluster ConfigMaps
    do not embed secrets; runtime auth uses the NemoGuardrails CR env
    (OPENAI_API_KEY) instead.
    """
    model_id = os.environ.get("MODEL_ID") or "llama3.1:8b"
    base_url = os.environ.get("LLM_BASE_URL") or "http://localhost:11434/v1"
    api_key = os.environ.get("API_KEY") or "not-needed"

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if "models" not in config:
        raise ValueError(f"Malformed {config_path}: missing top-level 'models' list")

    summary = []
    for model in config["models"]:
        role = model.get("type", "unknown")
        if "parameters" not in model:
            raise ValueError(
                f"Malformed {config_path}: model role={role!r} missing 'parameters'"
            )

        model["model"] = model_id
        model["parameters"]["base_url"] = base_url

        if omit_api_key:
            model["parameters"].pop("api_key", None)
            model["api_key_env_var"] = "OPENAI_API_KEY"  # pragma: allowlist secret
        else:
            model.pop("api_key_env_var", None)
            model["parameters"]["api_key"] = api_key

        summary.append(f"{role}={model_id}@{base_url}")

    tracing = config.get("tracing")
    if isinstance(tracing, dict):
        enabled = os.environ.get("GUARDRAILS_TRACING_ENABLED", "") == "true"
        tracing["enabled"] = enabled
        tracing["enable_content_capture"] = False
        summary.append(f"tracing={'enabled' if enabled else 'disabled'}")

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return summary


def main() -> None:
    config_path = "guardrails/config/local/config.yaml"
    summary = generate_config(config_path)
    print("Config generated:\n  " + "\n  ".join(summary))


if __name__ == "__main__":
    main()
