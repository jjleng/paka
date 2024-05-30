The cluster config is a YAML file that specifies the cluster configuration. The cluster config includes the following fields:

```yaml
version: "1.2" # The version of the cluster config file
aws: # The AWS-specific configuration
  cluster: # The overall cluster configuration
    name: my-awesome-cluster
    region: us-west-2
    namespace: default # Optional. The k8s namespace to deploy the cluster
    nodeType: t3a.medium # The default node type to run system components, functions and job workers
    minNodes: 2 # The minimum number of nodes to provision
    maxNodes: 4 # The maximum number of nodes the cluster can scale to. If too low, the cluster may not be able to start or scale to meet demand
  prometheus: # Optional. By default, prometheus is not installed
    enabled: true # Install prometheus for monitoring
    storageSize: 20Gi # The storage size for prometheus
    grafana: false # Wether to install grafana for monitoring
    alertmanager: false # Wether to install alertmanager
    # More fields see https://github.com/jjleng/paka/blob/9599aa7df9d48f280885d4b2f9f1e0c401290bb0/paka/config.py#L491-L523
  tracing: # Optional. By default, tracing is not installed
    enabled: false # Wether to install Zipkin for tracing
  function: # Optional. By default, functions run on the default node types provided in the cluster config. Once specified, Paka will prioritize running functions on the specified node types
    nodeGroups:
      - nodeTypes: ["t3a.large"] # The node types to run functions on
        diskSize: 20 # The disk size for the function nodes
        isSpot: true # Wether to use spot instances for the function nodes
        minInstances: 1 # The minimum number of instances to provision
        maxInstances: 3 # The maximum number of instances to provision
  vectorStore: # Optional. By default, vector store is not installed. Qdrant is used as the vector store
    nodeType: t3a.small # The node type to run the vector store
    replicas: 2 # The number of replicas
  job: # Optional. By default, jobs run on the default node types provided in the cluster config. Once specified, Paka will prioritize running jobs on the specified node types. Depending on the loads, job workers are scaled out or in
    enabled: true # Wether to provision job related resources
    brokerStorageSize: 40Gi # The storage size for the job broker (Redis)
    nodeGroups:
      - nodeTypes: ["t3a.large"] # The node types to run job workers on
        diskSize: 20 # The disk size for the job workers
        isSpot: true # Wether to use spot instances for the job workers
        minInstances: 1 # The minimum number of instances to provision
        maxInstances: 3 # The maximum number of instances to provision
  modelGroups: # Optional. By default, no model groups are provisioned. Model groups run on on-demand instances
    - name: llama2-7b-chat # The name of the model group
      nodeType: g4dn.xlarge # The node type to run the model group
      isPublic: true # Wether the model group is publicly accessible through the internet
      minInstances: 1 # The minimum number of instances to provision
      maxInstances: 3 # The maximum number of instances to provision
      runtime:
        image: ghcr.io/ggerganov/llama.cpp:server # The runtime image to use
        command: [...] # Optional. The command to run in the runtime image
        env: # Optional. The environment variables to set in the runtime image
          - name: ENV_VAR # The name of the environment variable
            value: test # The value of the environment variable
          - name: ANOTHER_ENV_VAR # Another environment variable
            valueFrom:
              configMapKeyRef:
                name: my-config-map # The name of the config map
                key: my-key # The key in the config map
        readinessProbe: # Optional. The readiness probe for the runtime image
          httpGet: # The HTTP readiness probe
            path: /ready # The path to check
            port: 8080 # The port to check
          initialDelaySeconds: 5 # The initial delay before checking
          periodSeconds: 5 # The period to check
        livenessProbe: # Optional. The liveness probe for the runtime image
          httpGet: # The HTTP liveness probe
            path: /live # The path to check
            port: 8080 # The port to check
          initialDelaySeconds: 15 # The initial delay before checking
          periodSeconds: 20 # The period to check
        volumeMounts: # Optional. The volume mounts for the runtime image
          - name: my-volume # The name of the volume
            mountPath: /path/to/mount # The path to mount
      model:
        hfRepoId: TheBloke/Llama-2-7B-Chat-GGUF # The Hugging Face model repository ID
        files: ["*.Q4_0.gguf"] # Optional. The files to download from the model repository. If not specified, all files are downloaded
        useModelStore: false # Wether to save the model files to s3. Using s3 can be cost and performance effective
      autoScaleTriggers: # Optional. The auto scale triggers for the model group. Multiple triggers can be specified. Once one of the triggers is met, the model group is scaled.
        - type: cpu # The type of trigger
          metadata:
            type: Utilization
            value: "50"
  mixedModelGroups: # Optional. By default, no mixed model groups are provisioned. A mixed model group can include both on-demand and spot nodes
    - name: llama2-7b-chat-awq # The name of the mixed model group
      nodeType: g4dn.xlarge # The node type to run the model group
      gpu:
        enabled: true # This model group runs on GPU-enabled instances
        diskSize: 50 # The disk size for the model group
      baseInstances: 1 # Fail-safe instances. These are always run on-demand instances. Set to 0 if no fail-safe instances are needed
      maxOnDemandInstances: 2 # The maximum number of on-demand instances to provision, including the fail-safe instances
      spot: # The spot instance configuration. Spot instances are cheaper than on-demand instances and are prioritized over on-demand instances. Only when spot instances are unavailable, on-demand instances are provisioned
        minInstances: 1 # The minimum number of spot instances to provision
        maxInstances: 2 # The maximum number of spot instances to provision
      runtime:
        image: vllm/vllm-openai:v0.4.2
      model:
        hfRepoId: TheBloke/Llama-2-7B-Chat-AWQ
      autoScaleTriggers: # Optional. The auto scale triggers for the model group. Multiple triggers can be specified. Once one of the triggers is met, the model group is scaled.
        - type: prometheus # The type of trigger.
          metadata:
            serverAddress: http://kube-prometheus-stack-prometheus.prometheus.svc.cluster.local:9090 # Prometheus endpoint
            metricName: latency_p95
            threshold: '20000' # Set to 20s, tune as needed
            query: | # Trigger scaling if p95 latency exceeds 20s
              histogram_quantile(0.95, sum(rate(istio_request_duration_milliseconds_bucket{destination_service="llama2-7b-chat.default.svc.cluster.local"}[5m])) by (le))

```
