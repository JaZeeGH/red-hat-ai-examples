# Garak Scan Configuration Reference

How to configure, customize, and interpret Garak security scans submitted
through the EvalHub API on RHOAI.

## Available Benchmarks

Each benchmark maps to a set of garak probe tags. The pass threshold for all
benchmarks is ASR < 0.3 (attacks must succeed less than 30% of the time).

| Benchmark ID | Probes | Category | Duration | Best For |
|---|---|---|---|---|
| `quick` | 1 (DAN 11.0) | Security | ~2 min | Smoke test, pipeline validation |
| `owasp_llm_top10` | ~200 | Security | 6–12 hrs | Comprehensive security audit |
| `quality` | ~89 | Safety | 4–8 hrs | Content safety (toxicity, violence, hate) |
| `intents` | Varies | Security | 2–4 hrs | Context-aware intent-based attacks |
| `avid` | All | All | 12+ hrs | Full vulnerability assessment |
| `avid_security` | Security subset | Security | 6–10 hrs | Security-focused AVID probes |
| `avid_ethics` | Ethics subset | Ethics | 4–8 hrs | Bias, fairness, harmful content |
| `avid_performance` | Performance subset | Performance | 2–4 hrs | Degradation and robustness |
| `cwe` | CWE probes | Security | 2–4 hrs | Software weakness exploitation |

### Choosing a benchmark

- **First scan:** Start with `quick` — it completes in minutes and validates
  the scan pipeline end-to-end.
- **Content safety:** Use `quality` to test for toxic, violent, hateful, and
  profane content.
- **Security audit:** Use `owasp_llm_top10` for a comprehensive scan against
  the OWASP Top 10 for LLM Applications.
- **Full assessment:** Use `avid` for the most comprehensive scan, or combine
  `owasp_llm_top10` + `quality` for security + safety coverage.

---

## OWASP LLM Top 10

The `owasp_llm_top10` benchmark is the most comprehensive security scan. It
tests against the [OWASP Top 10 for LLM Applications](https://genai.owasp.org/llm-top-10/)
using ~200 probes organized by risk category:

| OWASP Risk | Probes | What Garak Tests |
|---|---|---|
| **LLM01: Prompt Injection** | 86 | DAN jailbreaks, encoding attacks (base64, ROT13, UU), ANSI escape injection, role-play attacks, system prompt extraction, visual jailbreaks |
| **LLM02: Insecure Output Handling** | 25 | ANSI escape sequences in output, AV evasion (EICAR), package hallucination, web injection |
| **LLM04: Model Denial of Service** | 1 | Repeated token divergence attacks |
| **LLM05: Supply Chain Vulnerabilities** | 8 | Glitch tokens, file format injection, supply chain probes |
| **LLM06: Sensitive Info Disclosure** | 39 | Training data extraction, PII leakage, system prompt leaking, replay attacks |
| **LLM07: Insecure Plugin Design** | 1 | Agent tool misuse and breakout attempts |
| **LLM08: Excessive Agency** | 1 | Agent autonomy boundary testing |
| **LLM09: Overreliance** | 18 | Hallucinated packages, misleading claims, snowball misinformation |
| **LLM10: Model Theft** | 23 | Model weight extraction, training data replay, topic probing |

> **Note:** LLM03 (Training Data Poisoning) has no runtime probes — it requires
> offline analysis of training data.

### Probe modules by risk

**LLM01 — Prompt Injection** (86 probes): `dan`, `encoding`, `ansiescape`,
`promptinject`, `dra`, `goat`, `goodside`, `smuggling`, `sysprompt_extraction`,
`doctor`, `continuation`, `fitd`, `sata`, `phrasing`, `latentinjection`,
`visual_jailbreak`, `agent_breaker`

**LLM06 — Sensitive Info Disclosure** (39 probes): `divergence`,
`donotanswer`, `exploitation`, `grandma`, `leakreplay`, `propile`,
`web_injection`

**LLM09 — Overreliance** (18 probes): `donotanswer`, `goat`, `goodside`,
`misleading`, `packagehallucination`, `snowball`

### Filtering by OWASP risk

To scan only specific OWASP risk categories, use the `probe_tags` parameter:

```bash
# Only prompt injection (LLM01) — 86 probes
"probe_tags": "owasp:llm01"

# Only sensitive info disclosure (LLM06) — 39 probes
"probe_tags": "owasp:llm06"

# Specific probes by name
"probes": ["dan.Dan_11_0", "dan.DAN_Jailbreak", "sysprompt_extraction.SyspromptExtraction"]
```

---

## Submitting Scans

### Basic scan

```bash
TOKEN=$(oc whoami -t)
NAMESPACE=$(oc project -q)
EVALHUB_ROUTE=$(oc get route evalhub -n ${NAMESPACE} -o jsonpath='{.spec.host}')
AGENT_SVC="http://langgraph-react-agent.${NAMESPACE}.svc.cluster.local:8080"

curl -sk -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant: ${NAMESPACE}" \
  -H "Content-Type: application/json" \
  "https://${EVALHUB_ROUTE}/api/v1/evaluations/jobs" \
  -d '{
    "name": "my-scan",
    "model": {
      "name": "'"${MODEL_ID}"'",
      "url": "'"${AGENT_SVC}"'"
    },
    "benchmarks": [
      {
        "id": "quick",
        "provider_id": "garak"
      }
    ]
  }'
```

> **Note:** `model.url` is the **in-cluster service URL** (not the external
> route). Garak runs inside the EvalHub pod and reaches the agent within the
> cluster.

### Multiple benchmarks in one job

```bash
curl -sk -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant: ${NAMESPACE}" \
  -H "Content-Type: application/json" \
  "https://${EVALHUB_ROUTE}/api/v1/evaluations/jobs" \
  -d '{
    "name": "garak-full-security-audit",
    "model": {
      "name": "'"${MODEL_ID}"'",
      "url": "'"${AGENT_SVC}"'"
    },
    "benchmarks": [
      {"id": "owasp_llm_top10", "provider_id": "garak"},
      {"id": "quality", "provider_id": "garak"}
    ]
  }'
```

### With MLflow experiment tracking

Add an `experiment` block to persist results in MLflow. Without this block,
results are stored in EvalHub only and **will not appear** in the RHOAI
Experiments dashboard.

```bash
curl -sk -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant: ${NAMESPACE}" \
  -H "Content-Type: application/json" \
  "https://${EVALHUB_ROUTE}/api/v1/evaluations/jobs" \
  -d '{
    "name": "garak-tracked-scan",
    "model": {
      "name": "'"${MODEL_ID}"'",
      "url": "'"${AGENT_SVC}"'"
    },
    "benchmarks": [
      {"id": "quality", "provider_id": "garak"}
    ],
    "experiment": {
      "name": "my-experiment",
      "tags": [
        {"key": "agent", "value": "langgraph-react-agent"},
        {"key": "scan_type", "value": "quality"}
      ]
    }
  }'
```

For full details on what gets logged and how to compare runs, see
[MLflow Experiment Tracking](#mlflow-experiment-tracking) below.

---

## Custom Scan Parameters

Override default scan behavior by adding a `parameters` block to a benchmark:

```json
{
  "id": "owasp_llm_top10",
  "provider_id": "garak",
  "parameters": {
    "probe_tags": "owasp:llm01",
    "generations": 3,
    "eval_threshold": 0.5,
    "parallel_attempts": 8
  }
}
```

### Available parameters

| Parameter | Default | Description |
|---|---|---|
| Parameter | Default | Description |
|---|---|---|
| `probe_tags` | _(from benchmark)_ | Filter probes by tag (e.g. `owasp:llm01` for prompt injection only) |
| `probes` | _(all matching)_ | Specific probe names (e.g. `["dan.Dan_11_0", "dan.DAN_Jailbreak"]`) |
| `generations` | `1` | How many times to send each prompt (higher = more reliable ASR) |
| `eval_threshold` | `0.5` | Detector sensitivity (0.0–1.0); lower = more sensitive |
| `parallel_attempts` | `16` | Concurrent requests to the model (increase for faster scans) |
| `seed` | _(random)_ | Random seed for reproducibility |
| `timeout_seconds` | `600` | Scan timeout in seconds (0 = no timeout) |
| `detectors` | _(auto)_ | Specific detector names to use |
| `buffs` | _(none)_ | Buff modules to transform probes (e.g. encoding wrappers) |

These parameters can also be set inside a `garak_config` block for finer
control. For example, `soft_probe_prompt_cap` (which limits the number of
prompts per probe) is only available via `garak_config.run`:

```json
{
  "id": "owasp_llm_top10",
  "provider_id": "garak",
  "parameters": {
    "garak_config": {
      "run": {
        "soft_probe_prompt_cap": 10
      }
    }
  }
}
```

> **Tip:** Setting `soft_probe_prompt_cap` to 10 significantly reduces scan
> duration — from hours to minutes for most benchmarks. This is a soft cap
> (not enforced for all probes), but it works for the majority. Use it for
> fast iteration during development; remove it for comprehensive coverage
> in CI/CD gates.

### Full garak config override

For complete control, pass a nested `garak_config` object matching garak's
[configuration schema](https://reference.garak.ai/en/latest/configurable.html):

```json
"parameters": {
  "garak_config": {
    "run": {
      "generations": 5,
      "probe_tags": "owasp:llm01",
      "eval_threshold": 0.3
    },
    "system": {
      "parallel_attempts": 32,
      "verbose": 1
    },
    "reporting": {
      "taxonomy": "owasp"
    }
  }
}
```

Precedence (highest to lowest):

1. `parameters.garak_config` + flat-key overrides in `parameters`
2. Benchmark profile defaults (from the benchmark ID)
3. Garak defaults

---

## Monitoring and Retrieving Results

### Check job status

```bash
TOKEN=$(oc whoami -t)
curl -sk -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant: ${NAMESPACE}" \
  "https://${EVALHUB_ROUTE}/api/v1/evaluations/jobs/${JOB_ID}" \
  | python3 -m json.tool
```

### List all jobs

```bash
TOKEN=$(oc whoami -t)
curl -sk -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant: ${NAMESPACE}" \
  "https://${EVALHUB_ROUTE}/api/v1/evaluations/jobs" \
  | python3 -m json.tool
```

---

## Interpreting ASR Scores

Garak measures **attack success rate (ASR)** — the fraction of adversarial
prompts that bypassed safety mechanisms. **Lower is better.**

| ASR Range | Interpretation | Action |
|---|---|---|
| 0.0 | No attacks succeeded | Strong safety — monitor for new attack techniques |
| 0.0 – 0.1 | Excellent | Minimal vulnerability |
| 0.1 – 0.3 | Acceptable | Passes default threshold; consider additional rails for edge cases |
| 0.3 – 0.6 | Concerning | Significant vulnerability; deploy guardrails |
| 0.6 – 1.0 | Critical | Highly exploitable; guardrails + model upgrade recommended |

Per-benchmark results include:

- `primary_score`: the overall ASR value
- `pass`: whether the benchmark met its threshold (ASR < 0.3)
- `mlflow_run_id`: the MLflow run ID (when experiment tracking is enabled)
- Per-probe ASR breakdowns (e.g. `dan.Dan_11_0_asr`, `encoding.InjectBase64_asr`)

## MLflow Experiment Tracking

EvalHub can push garak scan results to MLflow so you can view, compare, and
track scans over time in the RHOAI dashboard. This section covers how the
integration works and how to use it effectively.

### How it works

When you include an `experiment` block in the scan submission, EvalHub's
sidecar proxy logs the scan results as an MLflow run:

```text
EvalHub API ──creates──▶ Garak Job Pod
                            ├── adapter (runs garak probes)
                            └── sidecar (proxies model calls,
                                         reports results to EvalHub,
                                         logs metrics to MLflow)
```

The sidecar connects to the RHOAI MLflow server using a projected
ServiceAccount token — no manual MLflow credentials are needed.

> **Key point:** Without the `experiment` block, results are stored in
> EvalHub only. They are still queryable via the EvalHub API, but they
> **will not appear** in the RHOAI Experiments dashboard.

### What gets logged to MLflow

Each completed scan creates an MLflow run containing:

| Category | What's Logged | Example |
|---|---|---|
| **Metrics** | Overall attack success rate | `attack_success_rate = 1.0` |
| **Metrics** | Per-probe ASR breakdowns | `dan.Dan_11_0_asr = 1.0` |
| **Tags** | User-provided tags from the `experiment.tags` array | `agent = langgraph-react-agent` |
| **Tags** | Benchmark metadata | `benchmark_id = quick`, `provider_id = garak` |
| **Artifacts** | Environment card with system info, package versions, resource limits | `evalhub.env_card` |

### The `experiment` block

```json
"experiment": {
  "name": "garak-red-teaming",
  "tags": [
    {"key": "agent", "value": "langgraph-react-agent"},
    {"key": "guardrails", "value": "none"},
    {"key": "scan_type", "value": "quick"},
    {"key": "model", "value": "qwen2-5-7b-instruct"}
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `name` | Yes | MLflow experiment name. Runs with the same name are grouped together. Use a consistent name across baseline and guardrailed scans to compare them side-by-side. |
| `tags` | No | Key-value pairs attached to the MLflow run. Use these to distinguish runs within the same experiment (e.g. `guardrails: none` vs `guardrails: nemo-self-check`). |

### Viewing results in RHOAI

1. Open the RHOAI dashboard
2. Navigate to **Develop and train** → **Experiments**
3. Select your project namespace from the **Project** dropdown
4. Click the experiment name (e.g. `garak-red-teaming`)
5. Each scan appears as a run with its metrics and tags

### Comparing baseline vs guardrailed scans

To compare before/after results side-by-side, use the same experiment name
for both scans and differentiate them with tags:

**Baseline scan (no guardrails):**

```bash
curl -sk -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant: ${NAMESPACE}" \
  -H "Content-Type: application/json" \
  "https://${EVALHUB_ROUTE}/api/v1/evaluations/jobs" \
  -d '{
    "name": "garak-baseline-scan",
    "model": {
      "name": "'"${MODEL_ID}"'",
      "url": "'"${AGENT_SVC}"'"
    },
    "benchmarks": [
      {"id": "quick", "provider_id": "garak"}
    ],
    "experiment": {
      "name": "garak-red-teaming",
      "tags": [
        {"key": "agent", "value": "langgraph-react-agent"},
        {"key": "guardrails", "value": "none"},
        {"key": "scan_type", "value": "quick"}
      ]
    }
  }'
```

**Guardrailed scan (after applying NeMo Guardrails):**

```bash
curl -sk -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant: ${NAMESPACE}" \
  -H "Content-Type: application/json" \
  "https://${EVALHUB_ROUTE}/api/v1/evaluations/jobs" \
  -d '{
    "name": "garak-guardrailed-scan",
    "model": {
      "name": "'"${MODEL_ID}"'",
      "url": "'"${AGENT_SVC}"'"
    },
    "benchmarks": [
      {"id": "quick", "provider_id": "garak"}
    ],
    "experiment": {
      "name": "garak-red-teaming",
      "tags": [
        {"key": "agent", "value": "langgraph-react-agent"},
        {"key": "guardrails", "value": "nemo-self-check"},
        {"key": "scan_type", "value": "quick"}
      ]
    }
  }'
```

In the RHOAI Experiments dashboard, select both runs and click **Compare**
to see the ASR metrics side-by-side.

### Troubleshooting MLflow

| Symptom | Cause | Fix |
|---|---|---|
| Scan completes but doesn't appear in Experiments | Missing `experiment` block in the scan submission | Resubmit the scan with an `experiment` block — results without it go to EvalHub only |
| Experiment appears but has no runs | Scan is still running or failed before completion | Check scan status via the EvalHub API: `curl ... /api/v1/evaluations/jobs/${JOB_ID}` |
| MLflow connection errors in sidecar logs | MLflow server unreachable from the job pod | Verify MLflow is running: `oc get pods -n redhat-ods-applications -l app=mlflow` |
| Runs appear under wrong experiment | Different `experiment.name` values across scans | Use the same `experiment.name` for scans you want to compare |

---

## References

- [Garak Documentation](https://docs.garak.ai/)
- [Garak Configuration Reference](https://reference.garak.ai/en/latest/configurable.html)
- [OWASP Top 10 for LLM Applications](https://genai.owasp.org/llm-top-10/)
- [AVID Taxonomy](https://avidml.org/taxonomy)
- [CWE (Common Weakness Enumeration)](https://cwe.mitre.org/)
