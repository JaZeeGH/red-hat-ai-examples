# Data Extraction (DATA_ONLY) with SpeculativeDecodingTrainer

This example demonstrates how to extract hidden states from a verifier model using the `DATA_ONLY` mode of `SpeculativeDecodingTrainer`. The SDK deploys a managed vLLM sidecar alongside the job pod to serve the verifier model, processes the dataset, and writes hidden state tensors (`.safetensors` files) to the output PVC.

No training happens in this mode. It is the first step of a two-step workflow: extract hidden states once, then train the draft model many times with different hyperparameters using [TRAIN_ONLY](../train-only/).

This example uses **Qwen3-8B** as the verifier model and the `ultrachat` built-in dataset.

## When to use DATA_ONLY

| Mode | Best for | vLLM Required | Complexity |
| --- | --- | --- | --- |
| **DATA_ONLY (this example)** | Extract once, experiment many times | Managed sidecar | Low |
| [TRAIN_ONLY](../train-only/) | Iterate on hyperparameters without re-extracting | None | Low |
| [OFFLINE](../offline/) | Reuse an existing vLLM deployment | External (user-managed) | Moderate |
| [ONLINE](../online/) | Simplest end-to-end path | Managed sidecar | Simplest |

## Setup

See the [common setup guide](../README.md#setup) for step-by-step instructions on creating a workbench, shared storage, and cloning the repository.

Navigate to `examples/fine-tuning/rhoai-3.6/speculator/data-only` and open `speculator-data-only-example.ipynb`.

## Key DATA_ONLY configuration

The key parameters specific to DATA_ONLY mode:

```python
data_only_trainer = SpeculativeDecodingTrainer(
    mode=SpeculatorMode.DATA_ONLY,
    vllm_resources=VLLM_RESOURCES,
    vllm_gpu_memory_utilization=0.9,
    regenerate_responses=True,
    config=SpeculatorConfig(
        datagen_concurrency=4,
        hidden_states_dtype="bfloat16",
    ),
    ...
)
```

| Parameter | Description |
| --- | --- |
| `vllm_gpu_memory_utilization` | Fraction of GPU memory the vLLM sidecar can use (0.9 = 90%) |
| `regenerate_responses` | When `True`, generates new responses from prompts before extracting hidden states |
| `datagen_concurrency` | Number of concurrent data generation workers |
| `hidden_states_dtype` | Data type for saved tensors (`bfloat16` halves disk usage vs `float32`) |

## Running the example

Open `speculator-data-only-example.ipynb` and follow the notebook, which walks you through:

1. **Installing dependencies** -- Kubeflow SDK and required packages
2. **Configuring authentication and paths** -- API access, PVC mount paths, and model configuration
3. **Configuring the DATA_ONLY trainer** -- Set up extraction parameters, dataset, and output paths
4. **Submitting the TrainJob** -- Launch the extraction job on the cluster
5. **Monitoring progress** -- Check job status and view logs
6. **Cleanup** -- Delete the TrainJob when extraction is complete

## Customization

| Parameter | Default | Description |
| --- | --- | --- |
| `dataset_name` | `ultrachat` | Built-in dataset name, HuggingFace ID, or PVC URI |
| `max_samples` | 500 | Maximum number of dataset samples to process |
| `total_seq_len` | 2048 | Maximum sequence length for extraction |
| `vllm_gpu_memory_utilization` | 0.9 | GPU memory fraction for vLLM sidecar |
| `datagen_concurrency` | 4 | Number of parallel data generation workers |
| `hidden_states_dtype` | `bfloat16` | Tensor data type (`bfloat16` or `float32`) |
| `PVC_NAME` | `shared` | Update if you use a different PVC name |

## Troubleshooting

### vLLM sidecar fails to start

If the vLLM sidecar pod fails or gets OOMKilled:

```bash
oc logs <pod-name> -c vllm-sidecar
```

Common fixes:

- Increase `memory` in `vllm_resources` (96Gi is recommended for Qwen3-8B)
- Ensure the GPU type supports the model size (Ampere-based or newer recommended)
- Verify the model path on the PVC is correct

### Hidden states output is empty

If no `.safetensors` files appear in the output directory:

- Verify `target_layer_ids` match the verifier model architecture
- Check that `dataset_name` is valid and accessible
- Review the job logs for data processing errors
