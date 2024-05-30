# Frequently Asked Questions

### How to use Paka in a team?
Paka is designed to handle cluster management in a team setting. To activate this feature, you'll need to establish a shared storage backend. This backend will hold the state data for the cluster provision.

A practical choice for this shared storage backend is AWS S3. You can set it up by using the `PULUMI_BACKEND_URL` environment variable. The format for this is `PULUMI_BACKEND_URL=s3://<bucket-name>/<path>`.

It's important to note that Paka uses Pulumi for cluster provisioning, hence the use of the Pulumi backend URL.

### How to run functions on dedicated nodes?
To run functions on dedicated nodes, you can use the `function` field in the cluster spec. This field allows you to specify a node label that the function should run on.

```yaml
function:
  nodeGroups:
    - nodeTypes: ["t3a.large"]
      diskSize: 20
      isSpot: true
      minInstances: 1
      maxInstances: 3
```

### How to run jobs on dedicated nodes?
To run jobs on dedicated nodes, you can use the `job` field in the cluster spec. This field allows you to specify a node label that the job should run on.

```yaml
job:
  enabled: true
  brokerStorageSize: 40Gi
  nodeGroups:
    - nodeTypes: ["t3a.large"]
      diskSize: 20
      isSpot: true
      minInstances: 1
      maxInstances: 3
```

### How to monitor logs?
For AWS deployment, logs are sinked to AWS CloudWatch. You can view the logs by navigating to the CloudWatch console and selecting the log group for the function you want to monitor. Alternatively, you can use the Stern CLI (https://github.com/stern/stern) to view the logs.

To view the model logs, you can use the following command:
```bash
stern --selector app=model-group
```

To view the function logs, you can use the following command:
```bash
stern "my-app*"
```

### How to scale the cluster?
For model groups, you can scale the cluster by updating the `maxInstances` field in the cluster spec. This field specifies the maximum number of instances that can be created for the model group. And then set up appropriate auto-scaling triggers.

Scaling by CPU utilization:
```yaml
modelGroups:
  - name: auto-scale-model
    minInstances: 1
    maxInstances: 3
    ...
    autoScaleTriggers:
      - type: cpu
        metadata:
          type: Utilization
          value: "50"
```

Scaling by Prometheus metrics:
```yaml
prometheus:
  enabled: true
modelGroups:
  - name: auto-scale-model
    minInstances: 1
    maxInstances: 3
    ...
    autoScaleTriggers:
      - type: prometheus
        metadata:
          serverAddress: http://kube-prometheus-stack-prometheus.prometheus.svc.cluster.local:9090 # Prometheus endpoint
          metricName: latency_p95
          threshold: '20000' # Set to 20s, tune as needed
          query: | # Trigger scaling if p95 latency exceeds 20s
            histogram_quantile(0.95, sum(rate(istio_request_duration_milliseconds_bucket{destination_service="llama2-7b-chat.default.svc.cluster.local"}[5m])) by (le))
```

For functions, you can adjust the scaling parameters as you deploy the function.

```bash
paka function deploy --name my-function --source . --entrypoint serve --min-instances 1 --max-instances 3 --scaling-metric concurrency --metric_target 2
```
