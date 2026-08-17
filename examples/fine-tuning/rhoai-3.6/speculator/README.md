# Speculative Decoding Draft Model Training via Kubeflow Trainer

This example demonstrates how to train a custom Eagle3 draft model for speculative decoding using the `SpeculativeDecodingTrainer` from the Kubeflow SDK on Red Hat OpenShift AI.

## What is Speculative Decoding?

Large language models generate tokens one at a time during inference. Each token requires reading the entire model from GPU memory (e.g., 140 GB for a 70B model in FP16), but the actual computation for one token is tiny. The GPU spends most of its time waiting for data to arrive from memory — running at under 1% compute utilization during normal token generation. This is called being **memory-bound**.

Speculative decoding exploits a key insight: verifying multiple tokens at once costs almost the same as generating one, because the expensive part (reading the model from memory) is identical and the GPU's compute units are idle anyway. A small, fast **draft model** (~1 GB) quickly guesses the next several tokens, then the large **verifier model** checks all guesses at once in a single forward pass. Correct guesses become output; at the first rejected guess, the verifier's own token is used and the draft model starts guessing again. The output is mathematically identical to normal decoding — no quality loss.

### Why Custom Draft Models?

vLLM already supports Eagle3 speculative decoding at serving time — if you have a draft model, you can deploy it today. Pre-built draft models (like those on HuggingFace) only work well with the original base model. After fine-tuning, the model's internal behavior changes, so a pre-built draft model's guesses no longer match and the acceptance rate drops significantly. Customers need a **custom draft model** trained specifically for their fine-tuned model to achieve meaningful inference speedup.

### Eagle3 Architecture

[Eagle3](https://arxiv.org/abs/2503.01840) is a draft model architecture that reads hidden states from four intermediate layers of the verifier model (not just the final logits), giving it richer context for more accurate predictions. The draft model is very small (~0.5 GB for an 8B verifier, ~1 GB for a 70B verifier) and consists of just two fully-connected layers and one Transformer decoder layer. The verifier model is never modified — only the draft model is trained.

## Training Modes

`SpeculativeDecodingTrainer` supports four training modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| `DATA_ONLY` | Extracts hidden states from the verifier model using a managed vLLM sidecar. No training. | First step of a two-step workflow. Extract once, experiment with training hyperparameters many times. |
| `TRAIN_ONLY` | Trains the draft model from pre-extracted hidden states. No vLLM needed. | Second step after `DATA_ONLY`. Iterate on hyperparameters without re-running extraction. |
| `OFFLINE` | Extracts hidden states via a user-managed external vLLM server, then trains. | When you already have a vLLM deployment or need custom vLLM configuration. |
| `ONLINE` | Fully managed end-to-end: SDK deploys a vLLM sidecar, extracts hidden states, and trains. | Simplest path — recommended when you want everything in one step. |

The notebook demonstrates all four modes.

## Supported Datasets

The SDK provides three built-in dataset names that can be used directly with the `dataset_name` parameter:

| Name | Description |
|------|-------------|
| `ultrachat` | Multi-turn conversational dataset |
| `magpie` | Magpie-format conversation dataset |
| `gsm8k` | Grade school math word problems |

You can also pass a HuggingFace dataset ID, a PVC URI (`pvc://<pvc-name>/<path>`), or a local `.json`/`.jsonl` file path as `dataset_name`.

## RHOAI compatibility

This example is compatible with RHOAI version 3.6EA1.

## Requirements

- An OpenShift cluster with OpenShift AI (RHOAI 3.6EA1) installed:
  - The `dashboard` and `workbenches` components enabled
  - The `trainer` component enabled
  - ClusterTrainingRuntimes (CTRs) deployed for speculator training — different modes require different CTRs (data extraction, model optimization, online)
- Sufficient worker nodes with NVIDIA GPUs (Ampere-based or newer recommended).
- A dynamic storage provisioner supporting RWX PVC provisioning. Talk to your cluster administrator about RWX storage options.
- A HuggingFace account and token (for downloading models and avoiding rate limits).

## Hardware requirements

For the workbench image, the example was run on `Training | Jupyter | PyTorch | CPU Python`.
The workbench only submits TrainJobs and monitors progress — no GPU is required on the workbench itself.

### Workbench Requirements

| Image Type | Use Case | GPU | CPU | Memory | Notes |
|------------|----------|-----|-----|--------|-------|
| Training \| Jupyter \| PyTorch \| CPU Python | Job submission and monitoring | None | 2 cores | 8Gi | No GPU needed; the workbench only submits TrainJobs |

> [!NOTE]
>
> - The workbench does not perform training or inference. All compute-intensive work happens in the TrainJob pods.

### Training Pod Requirements

| Component | GPU | GPU Type | CPU | Memory | Notes |
|-----------|-----|----------|-----|--------|-------|
| Training container | 2× GPU | NVIDIA L40S / A100 or equivalent | 4 cores | 64Gi | Runs Eagle3 draft model training |
| vLLM sidecar | 1× GPU | NVIDIA L40S / A100 or equivalent | 4 cores | 96Gi | Runs verifier model for hidden state extraction |

Which components are deployed depends on the training mode:

| Mode | Training Container | vLLM Sidecar | Total GPUs |
|------|-------------------|--------------|------------|
| `DATA_ONLY` | No | Yes | 1 |
| `TRAIN_ONLY` | Yes | No | 2 |
| `OFFLINE` | Yes | No (external) | 2 |
| `ONLINE` | Yes | Yes | 3 |

> [!NOTE]
>
> - `OFFLINE` mode uses an external vLLM server instead of a sidecar — configure its resources separately.
> - The vLLM sidecar currently supports only 1 GPU.
> - CPU, memory, and GPU requirements scale with verifier model size. The above values suit the example configuration (Qwen3-8B).

### Storage Requirements

| Purpose | Size | Access Mode | Storage Class | Notes |
|---------|------|-------------|---------------|-------|
| Shared Storage (PVC) total | 100Gi (Example Default) | RWX | Dynamic provisioner required | Shared between workbench and training pods |

> [!NOTE]
>
> - The PVC stores downloaded models, extracted hidden states, and trained draft model checkpoints.
> - Storage can be created in `Create Workbench` view on RHOAI Platform, however, dynamic RWX provisioner is required to be configured prior to creating shared file storage in RHOAI.
> - 100Gi is recommended to accommodate the verifier model weights, hidden state data, and output checkpoints.

## Speculator-specific considerations

- **PVC URIs**: All storage paths use PVC URIs (`pvc://<pvc-name>/<path>`). The SDK resolves these to container mount paths internally — do not use direct filesystem paths.
- **Model on PVC**: The verifier model should be pre-downloaded to the shared PVC. The notebook includes a download step using `huggingface_hub.snapshot_download`.
- **Target layer IDs**: When using a PVC URI for the verifier model, you must provide `target_layer_ids` explicitly via `SpeculatorConfig` because the SDK cannot access the model config from the PVC. When using a HuggingFace model ID, the SDK auto-detects target layer IDs.
- **ClusterTrainingRuntimes**: Different training modes use different ClusterTrainingRuntimes (CTRs). The notebook includes placeholders for the CTR names — replace them with the CTR names available on your cluster. Each mode requires a specific CTR:
  - `DATA_ONLY` — Data extraction CTR (includes vLLM sidecar for hidden state extraction)
  - `TRAIN_ONLY` / `OFFLINE` — Model optimization CTR (training only, no vLLM sidecar)
  - `ONLINE` — Online CTR (includes vLLM sidecar + training in one pod)
- **HuggingFace token**: Passed to training pods via the `env` parameter on each trainer. Required for downloading gated models. Qwen3-8B is not gated, but a token avoids rate limits.
- **Job naming**: Use `options=[Name(name="...")]` to give jobs explicit, predictable names. This makes it easier to monitor logs with `oc logs` and check job status with `trainer_client.get_job()`.
- **No manual PVC mounts**: Unlike GRPO/SFT TrainJobs, `SpeculativeDecodingTrainer` handles PVC mounting internally via PVC URIs. You do not need `PodTemplateOverrides` for PVC volume mounts.

## Setup

### Setup Workbench

**Step 1.** Access the OpenShift AI dashboard, for example from the top navigation bar menu:

![](../../images/01.png)

**Step 2.** Log in, then go to **_Data Science Projects_** and create a project:

![](../../images/02.png)

**Step 3.** Once the project is created, click on **_Create a workbench_**:

![](../../images/03.png)

**Step 4.** Select the `Training | Jupyter | PyTorch | CPU Python` workbench image:

![](../../images/04a.png)

> [!NOTE]
> No GPU is needed on the workbench — it only submits TrainJobs and monitors progress. All training runs on dedicated pods.

**Step 5.** You may want to create a **Hardware Profile** with GPU support, similar to the one below:

![](../../images/04b.png)

**Step 6.** Select the Hardware profile you want to use:

![](../../images/04c.png)

**Step 7.** Create **shared storage** that will be shared between the workbench and the training pods. Make sure it uses a storage class with RWX capability:

![](../../images/04d.png)

> [!NOTE]
> You can attach an existing shared storage if you already have one instead.

**Step 8.** Review the storage configuration and click "Create workbench":

![](../../images/04e.png)

**Step 9.** From "Workbenches" page, click on **_Open_** when the workbench you've just created becomes ready:

![](../../images/05.png)

### Running the example notebook

- From the workbench, clone this repository: `https://github.com/red-hat-data-services/red-hat-ai-examples.git`
- Navigate to the `examples/fine-tuning/rhoai-3.6/speculator` directory and open [`speculative-decoding-training-example.ipynb`](./speculative-decoding-training-example.ipynb).

> [!NOTE]
> - You will need a Hugging Face token if using gated models (e.g., Llama models).
> - Set the `HF_TOKEN` environment variable in your trainer configuration via the `env` parameter.

You can now proceed with the instructions from the notebook.
