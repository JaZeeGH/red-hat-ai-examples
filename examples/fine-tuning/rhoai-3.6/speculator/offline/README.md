# Offline Mode (User-Managed vLLM) with SpeculativeDecodingTrainer

This example demonstrates how to train an Eagle3 draft model using the `OFFLINE` mode of `SpeculativeDecodingTrainer`. This mode connects to an external, user-managed vLLM server to extract hidden states, then trains the draft model -- all within a single job.

This is useful when you already have a vLLM deployment running (e.g., as an OpenShift AI model serving instance) and want to reuse it for hidden state extraction instead of having the SDK deploy a sidecar.

This example uses **Qwen3-8B** as the verifier model and the `magpie` built-in dataset.

## When to use OFFLINE

| Mode | Best for | vLLM Required | Complexity |
| --- | --- | --- | --- |
| [DATA_ONLY](../data-only/) | Extract once, experiment many times | Managed sidecar | Low |
| [TRAIN_ONLY](../train-only/) | Iterate on hyperparameters without re-extracting | None | Low |
| **OFFLINE (this example)** | Reuse an existing vLLM deployment | External (user-managed) | Moderate |
| [ONLINE](../online/) | Simplest end-to-end path | Managed sidecar | Simplest |

## Setup

See the [common setup guide](../README.md#setup) for step-by-step instructions on creating a workbench, shared storage, and cloning the repository.

Navigate to `examples/fine-tuning/rhoai-3.6/speculator/offline` and open `speculator-offline-example.ipynb`.

### External vLLM server

Before running this notebook, you must have a vLLM server running that:

- Serves the same verifier model (Qwen3-8B) used in training
- Exposes the OpenAI-compatible API (typically at port 8000, path `/v1`)
- Is accessible from the training pods (e.g., via a Kubernetes service URL)

## Key OFFLINE configuration

The key parameters specific to OFFLINE mode:

```python
offline_trainer = SpeculativeDecodingTrainer(
    mode=SpeculatorMode.OFFLINE,
    vllm_endpoint=VLLM_ENDPOINT,
    hidden_states_path=f"{OFFLINE_OUTPUT}/hidden_states",
    training_resources=TRAINING_RESOURCES,
    ...
)
```

| Parameter | Description |
| --- | --- |
| `vllm_endpoint` | URL of your external vLLM server (e.g., `http://vllm-svc.namespace.svc.cluster.local:8000/v1`) |
| `hidden_states_path` | Where extracted hidden states are saved on the PVC |
| `training_resources` | GPU/CPU/memory for the training container |

**Key differences from other modes:**

- You must provide `vllm_endpoint` pointing to your external vLLM server
- The SDK does not deploy a vLLM sidecar -- `vllm_resources` is not used
- Both extraction and training happen in a single job (extract first, then train)

## Running the example

Open `speculator-offline-example.ipynb` and follow the notebook, which walks you through:

1. **Installing dependencies** -- Kubeflow SDK and required packages
2. **Configuring authentication and paths** -- API access, PVC mount paths, and model configuration
3. **Setting the vLLM endpoint** -- Point to your external vLLM server
4. **Configuring the OFFLINE trainer** -- Set up extraction and training parameters
5. **Submitting the TrainJob** -- Launch the job on the cluster
6. **Monitoring progress** -- Check job status and view logs
7. **Cleanup** -- Delete the TrainJob when complete

## Customization

| Parameter | Default | Description |
| --- | --- | --- |
| `VLLM_ENDPOINT` | `http://vllm-svc....:8000/v1` | URL of your external vLLM server |
| `dataset_name` | `magpie` | Built-in dataset name, HuggingFace ID, or PVC URI |
| `max_samples` | 500 | Maximum number of dataset samples to process |
| `epochs` | 3 | Number of full passes over the training data |
| `lr` | 1e-4 | AdamW learning rate |
| `total_seq_len` | 2048 | Maximum sequence length |
| `PVC_NAME` | `shared` | Update if you use a different PVC name |

## Troubleshooting

### Cannot connect to vLLM endpoint

If the job fails with a connection error:

```bash
oc logs <pod-name> -c node | grep -i "connection"
```

Common fixes:

- Verify the vLLM service is running: `oc get svc -n <namespace>`
- Check the endpoint URL format (must include `/v1`)
- Ensure network policies allow traffic from the training pod namespace to the vLLM namespace
- Verify the vLLM server is serving the correct model

### Extraction succeeds but training fails

If hidden states are extracted but training errors occur:

- Check GPU memory -- the training container needs its own GPU allocation
- Verify `target_layer_ids` match the model served by the vLLM endpoint
- Review training logs for OOM or configuration errors
