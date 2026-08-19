# OpenCode Skill Evaluation with MLflow Scorers

This directory contains [OpenCode](https://github.com/opendatahub-io/opencode) skills and an evaluation notebook that demonstrates the end-to-end evaluation workflow: run scorers against skill traces, find a gap, strengthen the skill, and re-evaluate. Each skill defines a structured, multi-step task that an OpenCode agent executes, producing both a written output artifact and a traceable record of the agent's reasoning and tool use.

## Evaluation

The [evaluation notebook](opencode_scorer_evaluation.ipynb) demonstrates the end-to-end evaluation workflow for OpenCode skills — similar to the [end-to-end LangGraph notebook](../end-to-end/agent_evaluation_end_to_end.ipynb), but for a coding agent. Individual scorer behavior is covered in the [failure-mode notebooks](../failure-modes/); this notebook focuses on applying them as a complete workflow.

- **Simulate skill traces** — creates traces mirroring real skill executions observed on an OpenShift AI cluster
- **Two-tier evaluation** — runs built-in + custom scorers (deterministic checks → LLM judges)
- **Discover a gap** — `write_verification_check` finds that `pr-summarizer` skips read-back after writing
- **Strengthen and re-evaluate** — updates the skill language, confirms the fix with before/after evaluation

Custom scorers in [`scorers.py`](scorers.py) extend built-in MLflow scorers with checks specific to coding agents: write verification, hallucinated tool detection, repeated action loops, and PII detection (regex default, no extra dependencies).

> **Note:** OpenCode 1.18.3's MLflow plugin creates trace metadata but does not upload span data as `traces.json` artifacts. Traces must be reconstructed from OpenCode's local SQLite database using the Python SDK with `MLFLOW_ENABLE_ASYNC_TRACE_LOGGING=false`.

### Running the evaluation notebook

1. Complete the [project setup](../README.md#setup) (dependencies, API keys, MLflow tracking)
2. Open [opencode_scorer_evaluation.ipynb](opencode_scorer_evaluation.ipynb) and run all cells

> **`pii_check` note:** Uses deterministic regex patterns by default (no extra setup). Set `OPENCODE_USE_GUARDRAILS_PII=true` and install `guardrails-ai-detect-pii` to use Presidio-based `DetectPII` instead. See [PII Leakage setup](../failure-modes/04_pii_leakage/README.md).

### Files

| File | What it is |
|---|---|
| [opencode_scorer_evaluation.ipynb](opencode_scorer_evaluation.ipynb) | Evaluation notebook — runs scorers against OpenCode traces |
| [scorers.py](scorers.py) | Adapted scorers for OpenCode trace format |
| [golden_queries.json](golden_queries.json) | Reference queries for both skills |
| [skills/](skills/) | Skill definitions mounted in the OpenCode pod |

## Deploying OpenCode

Deploy OpenCode on Red Hat OpenShift AI using the manifests and guides in the agentic-starter-kits repository:

- **Deployment guide:** [agents/opencode](https://github.com/red-hat-data-services/agentic-starter-kits/tree/main/agents/opencode)
- **MLflow tracing setup:** [agents/opencode/deployment/docs](https://github.com/red-hat-data-services/agentic-starter-kits/tree/main/agents/opencode/deployment/docs)

Use the **MLflow tracing** image variant (`Containerfile.mlflow`) to enable trace export. Skills require CLI mode — exec into the pod after deployment.

## Skills

Skills are located under `skills/`. Each skill is a subdirectory containing a single `SKILL.md` file, which OpenCode discovers and makes available via the `/skill` command.

```text
skills/
├── python-file-review/
│   └── skill.md        # Code quality review for Python source files
└── pr-summarizer/
    └── skill.md        # Structured PR description from git diff
```

### Mounting skills in the pod

Skills are mounted via a Kubernetes ConfigMap. Each key in the ConfigMap corresponds to one skill file, and the volume `items` mapping remaps each flat key to the `<skill-name>/SKILL.md` path that OpenCode requires for skill discovery.

> **Note:** Skill files are named `skill.md` (lowercase) in this repository. The ConfigMap `items` mapping renames each file to `SKILL.md` when mounting into the pod, which is the filename OpenCode's skill loader expects.

Example ConfigMap creation:

```bash
oc create configmap opencode-web-skills \
  --from-file=python-file-review.md=skills/python-file-review/skill.md \
  --from-file=pr-summarizer.md=skills/pr-summarizer/skill.md \
  -n <namespace> \
  --dry-run=client -o yaml | oc apply -f -
```

Add the corresponding `items` entries to the skills volume in the deployment:

```yaml
volumes:
  - name: skills
    configMap:
      name: opencode-web-skills
      items:
        - key: python-file-review.md
          path: python-file-review/SKILL.md
        - key: pr-summarizer.md
          path: pr-summarizer/SKILL.md
```

### Invoking skills

Skills must be invoked from a **fresh `opencode` session** to produce a separate MLflow trace per run. Each `opencode` process is one session and one trace.

**Interactive (recommended for development):**

```bash
oc exec -it deployment/opencode-web -c opencode-web -n <namespace> -- bash
# Inside the pod:
opencode
# At the opencode prompt:
/skill <skill-name> <input>
# Exit opencode between runs for separate traces
```

**Headless (one trace per exec call):**

```bash
oc exec -n <namespace> deployment/opencode-web -c opencode-web -- \
  opencode run --command skill --auto "<input>"
```

---

## Skill Reference

### `python-file-review`

Reviews a Python source file for code quality issues and writes a structured markdown report.

**Input:** Absolute path to a Python file inside the pod workspace.

**Example:**

```text
/skill python-file-review /opt/app-root/workspace/input-files/my_module.py
```

**Steps the agent performs:**

1. Reads the file
2. Runs `ruff check <file> --output-format=text` (skips gracefully if ruff is unavailable)
3. Analyzes for missing docstrings, complexity, potential bugs, and dead code
4. Writes the report
5. Reads back the first lines of the report to confirm the write

**Output:** `/opt/app-root/workspace/reviews/<basename>-review.md`

**Report structure:**

```text
# Code Review: <filename>
## Summary
## Issues
### High / Medium / Low
## Ruff output
## Recommendations
```

**Workspace files created:**

```text
/opt/app-root/workspace/
└── reviews/
    └── <basename>-review.md
```

**Caveats:**

- `ruff` is not pre-installed in the base OpenCode image. The agent handles this gracefully but the Ruff output section will always read "not available" unless ruff is added to the image.
- Input files must be present inside the pod workspace before invoking the skill. Copy them in with `oc cp` or place them directly on the PVC.

**Suggested input files:** Any non-trivial Python source file. Files with real logic (functions, classes, error handling) produce more meaningful traces than pure data files (e.g., dicts of constants).

---

### `pr-summarizer`

Fetches a pull request from a local clone of `agentic-starter-kits` and writes a structured PR description including summary, changed files, risk assessment, and test plan.

**Input:** A pull request number from the `red-hat-data-services/agentic-starter-kits` repository.

**Example:**

```text
/skill pr-summarizer 178
```

**One-time setup — clone the repository into the pod workspace:**

```bash
oc exec -n <namespace> deployment/opencode-web -c opencode-web -- \
  git clone https://github.com/red-hat-data-services/agentic-starter-kits \
  /opt/app-root/workspace/repos/agentic-starter-kits
```

The clone is stored on the workspace PVC and persists across pod restarts. Do not re-clone on each run.

**Steps the agent performs:**

1. Fetches the PR ref: `git fetch origin refs/pull/<N>/head:pr/<N>`
2. Gets the commit list: `git log main..pr/<N> --oneline`
3. Gets the full diff: `git diff main...pr/<N>`
4. Gets file stats: `git diff --stat main...pr/<N>`
5. Analyzes purpose, approach, scope, risk, and test coverage
6. Writes the summary file
7. Verifies the write by reading back the first lines (required before reporting completion)

**Output:** `/opt/app-root/workspace/pr-summaries/pr-<NUMBER>-summary.md`

**Report structure:**

```text
# PR #<NUMBER>: <title>
## Summary
## Changed files
## Risk assessment
## Test plan
## Notes
```

**Workspace files created:**

```text
/opt/app-root/workspace/
├── repos/
│   └── agentic-starter-kits/   ← one-time clone, persists on PVC
└── pr-summaries/
    └── pr-<NUMBER>-summary.md
```

**Caveats:**

- **Hardcoded repository:** The skill is hardcoded to use the local clone at `/opt/app-root/workspace/repos/agentic-starter-kits`. To use a different repository, update the path in `SKILL.md` and clone accordingly.
- **Full history required:** The clone must not be shallow (`--depth`). A shallow clone causes `git log main..pr/<N>` to return incorrect commit counts because the merge base is outside the truncated history. If you cloned with `--depth`, run `git fetch --unshallow` inside the pod.
- **Internet access required at fetch time:** The skill runs `git fetch` to retrieve the PR ref at invocation time. The pod must have outbound HTTPS access to `github.com`.
- **Analysis is diff-based:** The agent sees only the raw code diff and commit message titles — not the GitHub PR description, body, or any test plan written by the PR author.

---

## Pod Workspace Layout

After running both skills, the workspace PVC contains:

```text
/opt/app-root/workspace/
├── input-files/                     ← Python files to review (copy in manually)
│   └── *.py
├── reviews/                         ← python-file-review outputs
│   └── <basename>-review.md
├── pr-summaries/                    ← pr-summarizer outputs
│   └── pr-<NUMBER>-summary.md
└── repos/
    └── agentic-starter-kits/        ← one-time git clone for pr-summarizer
```

## MLflow Traces

Each skill invocation (one `opencode` session) produces one MLflow trace. Traces are exported to the experiment configured in the pod's `MLFLOW_EXPERIMENT_NAME` environment variable.

Key span types in traces:

| Span | Description |
| --- | --- |
| `opencode_conversation` | Root span; `inputs.prompt` is the `/skill` command |
| `llm_call` | One LLM inference turn |
| `tool_read` | File read |
| `tool_write` | File write |
| `tool_bash` | Shell command (ruff, git, ls, etc.) |
| `tool_glob` | Glob/file search |
| `tool_skill` | Skill definition loaded by name — present only when skill is invoked as `/skill <name> <args>` |

> **Note:** The `tool_skill` span is only present when the skill name is explicitly provided (e.g., `/skill python-file-review <path>`). Omitting the skill name (e.g., `/skill <path>`) bypasses skill loading — the agent will not have the skill instructions in context even if it produces plausible output. Always include the skill name.
