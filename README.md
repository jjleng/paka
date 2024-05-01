# Welcome to Paka

<img src="https://raw.githubusercontent.com/jjleng/paka/main/docs/img/paka.svg" alt="paka.svg" width="200" height="200">

**paka** is a versatile LLMOps tool that simplifies the deployment and management of large language model (LLM) apps with a single command.

## Paka Highlights

- **Cloud-Agnostic Resource Provisioning**: paka starts by breaking down the barriers of cloud vendor lock-in, currently supporting EKS with plans to expand to more cloud services.
- **Optimized Model Execution**: Designed for efficiency, paka runs LLM models on CPUs and Nvidia GPUs, ensuring optimal performance. Auto-scaling of model replicas based on CPU usage, request rate, and latency.
- **Scalable Batch Job Management**: paka excels in managing batch jobs that dynamically scale out and in, catering to varying workload demands without manual intervention.
- **Seamless Application Deployment**: With support for running Langchain and LlamaIndex applications as functions, paka offers scalability to zero and back up, along with rolling updates to ensure no downtime.
- **Comprehensive Monitoring and Tracing**: Embedded with built-in support for metrics collection via Prometheus and Grafana, along with tracing through Zipkin.




### Runtime Inference
Current runtime inference is done through the awesome [llama.cpp](https://github.com/ggerganov/llama.cpp) and [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) projects.

vLLM support is coming soon.

Each model is ran in a separate model group. Each model group can have its own node type, replicas and autoscaling policies.

### Serverless Containers
Applications are deployed as serverless containers using [knative](https://knative.dev). However, users can deploy their applications to the native cloud offerings as well, such as Lambda, Cloud Run, etc.

### Batch Jobs
Optional redis broker can be provisioned for celery jobs. Job workers are automatically scaled based on the queue length.

### Vector Store
Vector store is a key-value store for storing embeddings. Paka supports provisioning [qdrant](https://github.com/qdrant/qdrant).

### Monitoring
Paka comes with built-in support for monitoring and tracing. Metrics are collected via Prometheus and Grafana, and tracing is done through Zipkin. Users can also enable Prometheus Alertmanager for alerting.

### Continuous Deployment
Paka supports continuous deployment with rolling updates to ensure no downtime. Application can be built, pushed to container registry and deployed with a single command.

### Building
Application, job code is built using [buildpacks](https://buildpacks.io/). No need to write Dockerfile. However, user still needs to have docker runtime installed.


## Paka CLI Reference

Install the paka CLI
```bash
pip install paka
```

### Provision a cluster

Create a cluster.yaml
```yaml
aws:
  cluster:
    name: example
    region: us-west-2
    nodeType: t2.medium
    minNodes: 2
    maxNodes: 4
  modelGroups:
    - nodeType: c7a.xlarge
      minInstances: 1
      maxInstances: 3
      name: llama2-7b
      resourceRequest:
        cpu: 3600m
        memory: 6Gi
      autoScaleTriggers:
        - type: cpu
          metadata:
            type: Utilization
            value: "50"
```

Provision the cluster
```bash
paka cluster up -f cluster.yaml
```

### Deploy an application
Change to the application directory and add a `Procfile` and a .cnignore file.
In `Procfile`, add the command to start the application. For example, for a flask app, it would be `web: gunicorn app:app`. In `.cnignore`, add the files to ignore during build.

To pin the version of the language runtime, add a `runtime.txt` file with the version number. For example, for python, it could be `python-3.11.*`.

For a python application, a requirements.txt file is required.

To deploy the application, run `paka function deploy --name <function_name> --source <source_path> --entrypoint <Procfile_command>. For example:

```bash
paka function deploy --name langchain-server --source . --entrypoint serve
```

### Destroy a cluster
```bash
paka cluster down -f cluster.yaml
```

## Contributing
- code changes
- `make check-all`
- Open a PR

## Dependencies
- docker daemon and CLI
- AWS CLI
```bash
# Ensure your AWS credentials are correctly configured.
aws configure
```
