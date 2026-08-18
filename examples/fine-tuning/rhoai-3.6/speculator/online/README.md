# Online Mode (End-to-End Managed) with SpeculativeDecodingTrainer

This example demonstrates how to train an Eagle3 draft model using the `ONLINE` mode of `SpeculativeDecodingTrainer`. This is the simplest workflow -- the SDK manages everything in a single job:

1. Deploys a vLLM sidecar to serve the verifier model
2. Extracts hidden states from the dataset batch by batch
3. Trains the Eagle3 draft model using the extracted hidden states

Hidden states are processed in a streaming fashion -- each batch is extracted, used for training, then discarded. This means disk usage stays constant regardless of dataset size.

This example uses **Qwen3-8B** as the verifier model and the `magpie` built-in dataset.

## When to use ONLINE

| Mode | Best for | vLLM Required | Complexity |
| --- | --- | --- | --- |
| [DATA_ONLY](../data-only/) | Extract once, experiment many times | Managed sidecar | Low |
| [TRAIN_ONLY](../train-only/) | Iterate on hyperparameters without re-extracting | None | Low |
| [OFFLINE](../offline/) | Reuse an existing vLLM deployment | External (user-managed) | Moderate |
| **ONLINE (this example)** | Simplest end-to-end path | Managed sidecar | Simplest |

**Trade-off:** ONLINE is the simplest path (one step instead of two), but you cannot reuse the extracted data for multiple training runs with different hyperparameters. If you want to experiment with hyperparameters, use [DATA_ONLY](../data-only/) + [TRAIN_ONLY](../train-only/) instead.

## Setup

See the [common setup guide](../README.md#setup) for step-by-step instructions on creating a workbench, shared storage, and cloning the repository.

Navigate to `examples/fine-tuning/rhoai-3.6/speculator/online` and open `speculator-online-example.ipynb`.

## Key ONLINE configuration

The key parameters specific to ONLINE mode:

```python
online_trainer = SpeculativeDecodingTrainer(
    mode=SpeculatorMode.ONLINE,
    vllm_resources=VLLM_RESOURCES,
    vllm_gpu_memory_utilization=0.9,
    training_resources=TRAINING_RESOURCES,
    ...
)
```

| Parameter | Description |
| --- | --- |
| `vllm_resources` | GPU/CPU/memory for the managed vLLM sidecar |
| `vllm_gpu_memory_utilization` | Fraction of GPU memory the vLLM sidecar can use (0.9 = 90%) |
| `training_resources` | GPU/CPU/memory for the training container |

ONLINE mode requires both `vllm_resources` and `training_resources` since it runs extraction and training together.

## Running the example

Open `speculator-online-example.ipynb` and follow the notebook, which walks you through:

1. **Installing dependencies** -- Kubeflow SDK and required packages
2. **Configuring authentication and paths** -- API access, PVC mount paths, and model configuration
3. **Configuring the ONLINE trainer** -- Set up extraction and training parameters
4. **Submitting the TrainJob** -- Launch the end-to-end job on the cluster
5. **Monitoring progress** -- Check job status and view logs
6. **Cleanup** -- Delete the TrainJob when complete

## Customization

| Parameter | Default | Description |
| --- | --- | --- |
| `dataset_name` | `magpie` | Built-in dataset name, HuggingFace ID, or PVC URI |
| `max_samples` | 500 | Maximum number of dataset samples to process |
| `epochs` | 3 | Number of full passes over the training data |
| `lr` | 1e-4 | AdamW learning rate |
| `total_seq_len` | 2048 | Maximum sequence length |
| `vllm_gpu_memory_utilization` | 0.9 | GPU memory fraction for vLLM sidecar |
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

### Out of GPU memory during training

If the training container runs out of GPU memory:

- Reduce `total_seq_len` to lower memory usage
- Ensure training and vLLM containers are scheduled on separate GPUs
- Check that `training_resources` GPU count matches expectations
