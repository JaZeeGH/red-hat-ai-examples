# MLflow Integration (Optional)

Red Hat OpenShift AI includes a managed [MLflow](https://mlflow.org/) instance for experiment tracking. When MLflow is enabled on your RHOAI cluster, training metrics (loss, learning rate, etc.) are automatically logged to MLflow experiments — no additional code changes required beyond setting the experiment name.

## Supported training modes

| Mode | MLflow support | Notes |
| --- | --- | --- |
| **Interactive (single node)** | Yes | Set `MLFLOW_EXPERIMENT_NAME` in the notebook; workbench annotation auto-injects tracking URI and auth |
| **Distributed (Kubeflow Trainer)** | Yes | Pass `MLFLOW_TRACKING_AUTH=kubernetes-namespaced` and `mlflow[kubernetes]` in the training job env — see the [Orpheus TTS example](../trainer/orpheus-tts/) |

## How it works

The MLflow Operator deploys a cluster-scoped, singleton tracking server in `redhat-ods-applications`. Each OpenShift project maps 1:1 to an MLflow workspace. Authentication uses `kubernetes-namespaced` — the SDK automatically injects service account tokens and workspace headers on every request.

- **Workbenches**: Annotate the Notebook CR with `opendatahub.io/mlflow-instance: mlflow` to auto-inject `MLFLOW_TRACKING_URI`, `MLFLOW_TRACKING_AUTH`, and `MLFLOW_K8S_INTEGRATION`. The dashboard does this automatically when MLflow is `Managed`.
- **Training pods**: Set `MLFLOW_TRACKING_AUTH=kubernetes-namespaced` in the job env and install `mlflow[kubernetes]` (>=3.11). Grant the training service account the `mlflow-operator-mlflow-integration` ClusterRole.

For full details, see [Working with MLflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/) in the RHOAI documentation.

## Enabling MLflow

Each interactive notebook already includes a cell that sets the MLflow experiment name:

```python
os.environ["MLFLOW_EXPERIMENT_NAME"] = "<your-experiment-name>"
```

For this to work, MLflow must be enabled as a component in your RHOAI installation. If MLflow is not enabled, the environment variable is simply ignored and training proceeds normally.

**To enable MLflow on your cluster:**

1. Enable the MLflow Operator component in your `DataScienceCluster` CR:

   ```bash
   oc patch datasciencecluster default-dsc \
     --type=merge \
     -p '{"spec":{"components":{"mlflowoperator":{"managementState":"Managed"}}}}'
   ```

2. Create an `MLflow` CR to deploy the tracking server (example using PVC-backed storage):

   ```bash
   oc apply -f - <<EOF
   apiVersion: mlflow.opendatahub.io/v1
   kind: MLflow
   metadata:
     name: mlflow
   spec:
     artifactsDestination: "file:///mlflow/artifacts"
     serveArtifacts: true
     storage:
       accessModes:
         - ReadWriteOnce
       resources:
         requests:
           storage: 10Gi
   EOF
   ```

   For production, use PostgreSQL for the backend store and S3 for artifacts. See [Install and configure MLflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-mlflow_mlflow).

3. For distributed training jobs, grant the training service account MLflow access:

   ```bash
   oc create rolebinding <name>-mlflow-integration \
     --clusterrole=mlflow-operator-mlflow-integration \
     --serviceaccount=<namespace>:default \
     -n <namespace>
   ```

## Viewing MLflow Experiments

Once training completes with MLflow enabled, you can browse your experiment runs:

1. In the OpenShift AI dashboard, navigate to **Develop & train → Experiments (MLflow)** from the left sidebar menu.
2. Select the experiment name to view all runs.
3. Each run contains logged metrics (training loss, learning rate), parameters, and artifacts.

You can also launch the full MLflow UI by clicking the **"Launch MLflow"** link in the top right of the Experiments page:

![MLflow experiments page](./images/mlflow-experiments.png)

Each run logs metrics including training loss, learning rate, samples per second, and more:

![MLflow run metrics](./images/mlflow-run-metrics.png)
