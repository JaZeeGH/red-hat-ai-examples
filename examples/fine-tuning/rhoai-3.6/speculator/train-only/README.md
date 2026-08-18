# Train from Extracted Data (TRAIN_ONLY) with SpeculativeDecodingTrainer

This example demonstrates how to train an Eagle3 draft model from pre-extracted hidden states using the `TRAIN_ONLY` mode of `SpeculativeDecodingTrainer`. No vLLM sidecar is needed -- the training container reads hidden state tensors directly from the PVC.

> **Prerequisite:** This notebook requires hidden states extracted by a completed [DATA_ONLY](../data-only/) run. Run the `data-only/` notebook first.

Only the draft model's small components are trained:

- **FC layer 1 (fusion):** Combines hidden states from four verifier layers into one vector
- **FC layer 2 (concat):** Merges the fused hidden state with the previous token's embedding
- **One Transformer decoder layer:** Predicts the next token probability distribution

The verifier model is frozen and never modified.

This example uses **Qwen3-8B** as the verifier model and trains from data extracted with the **ultrachat** dataset.

## When to use TRAIN_ONLY

| Mode | Best for | vLLM Required | Complexity |
| --- | --- | --- | --- |
| [DATA_ONLY](../data-only/) | Extract once, experiment many times | Managed sidecar | Low |
| **TRAIN_ONLY (this example)** | Iterate on hyperparameters without re-extracting | None | Low |
| [OFFLINE](../offline/) | Reuse an existing vLLM deployment | External (user-managed) | Moderate |
| [ONLINE](../online/) | Simplest end-to-end path | Managed sidecar | Simplest |

## Setup

See the [common setup guide](../README.md#setup) for step-by-step instructions on creating a workbench, shared storage, and cloning the repository.

Navigate to `examples/fine-tuning/rhoai-3.6/speculator/train-only` and open `speculator-train-only-example.ipynb`.

## Key TRAIN_ONLY configuration

The key parameters specific to TRAIN_ONLY mode:

```python
train_only_trainer = SpeculativeDecodingTrainer(
    mode=SpeculatorMode.TRAIN_ONLY,
    hidden_states_path=f"{DATA_ONLY_OUTPUT}/hidden_states",
    data_path=DATA_ONLY_OUTPUT,
    training_resources=TRAINING_RESOURCES,
    config=SpeculatorConfig(
        num_layers=1,
        ttt_steps=3,
        norm_before_residual=True,
        scheduler_type="linear",
        checkpoint_freq=1.0,
        resume_from_checkpoint=True,
    ),
    # ...
)
```

| Parameter | Description |
| --- | --- |
| `hidden_states_path` | Path to the `hidden_states/` subdirectory from a DATA_ONLY run |
| `data_path` | Path to the DATA_ONLY output directory (contains preprocessed dataset) |
| `num_layers` | Number of Transformer decoder layers in the draft model (default: 1) |
| `ttt_steps` | Test-time training steps per batch |
| `norm_before_residual` | Apply LayerNorm before the residual connection |
| `scheduler_type` | Learning rate scheduler (`linear` decays to zero) |
| `checkpoint_freq` | Save a checkpoint every N epochs (1.0 = every epoch) |
| `resume_from_checkpoint` | Resume from the latest checkpoint if one exists |

## Running the example

Open `speculator-train-only-example.ipynb` and follow the notebook, which walks you through:

1. **Installing dependencies** -- Kubeflow SDK and required packages
2. **Configuring authentication and paths** -- API access, PVC mount paths, and model configuration
3. **Configuring the TRAIN_ONLY trainer** -- Set up training parameters, hidden states path, and output
4. **Submitting the TrainJob** -- Launch the training job on the cluster
5. **Monitoring progress** -- Check job status and view logs
6. **Cleanup** -- Delete the TrainJob when training is complete

## Customization

| Parameter | Default | Description |
| --- | --- | --- |
| `epochs` | 3 | Number of full passes over the training data |
| `lr` | 1e-4 | AdamW learning rate |
| `total_seq_len` | 2048 | Maximum sequence length |
| `num_layers` | 1 | Transformer decoder layers in the draft model |
| `ttt_steps` | 3 | Test-time training steps per batch |
| `scheduler_type` | `linear` | Learning rate scheduler type |
| `checkpoint_freq` | 1.0 | Save checkpoint every N epochs |
| `PVC_NAME` | `shared` | Update if you use a different PVC name |

## Troubleshooting

### Hidden states not found

If the job fails with a missing path error:

- Verify the `DATA_ONLY` run completed successfully
- Check that `DATA_ONLY_OUTPUT` matches the output path used in the DATA_ONLY run
- Ensure the `hidden_states/` subdirectory exists on the PVC

### Resuming from checkpoint

If training was interrupted:

- Set `resume_from_checkpoint=True` in `SpeculatorConfig`
- The trainer will automatically find the latest checkpoint in `output_dir`
- Resubmit the job with the same configuration
