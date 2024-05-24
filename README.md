# Welcome to Paka

<img src="https://raw.githubusercontent.com/jjleng/paka/main/docs/img/paka.svg" alt="paka.png" width="100" height="100">


Get your LLM applications to the cloud with ease. Paka handles failure recovery, autoscaling, and monitoring, freeing you to concentrate on crafting your applications.

## 🚀 Bring LLM models to the cloud in minutes
💰 Cut 50% cost with spot instances, backed by on-demand instances for reliable service quality.

| Model      | Parameters | Quantization | GPU          | On-Demand | Spot    | AWS Node (us-west-2) |
| ---------- | ---------- | ------------ | ------------ | --------- | ------- | ---------------------|
| Llama 3    | 70B        | BF16         | A10G x 8     | $16.2880  | $4.8169 | g5.48xlarge          |
| Llama 3    | 70B        | GPTQ 4bit    | T4 x 4       | $3.9120   | $1.6790 | g4dn.12xlarge        |
| Llama 3    | 8B         | BF16         | L4 x 1       | $0.8048   | $0.1100 | g6.xlarge            |
| Llama 2    | 7B         | GPTQ 4bit    | T4 x 1       | $0.526    | $0.2584 | g4dn.xlarge          |
| Mistral    | 7B         | BF16         | T4 x 1       | $0.526    | $0.2584 | g4dn.xlarge          |
| Phi3 Mini  | 3.8B       | BF16         | T4 x 1       | $0.526    | $0.2584 | g4dn.xlarge          |

> Note: Prices are based on us-west-2 region and are in USD per hour. Spot prices change frequently.
> See [Launch Templates](https://github.com/jjleng/paka/tree/main/examples/templates) for more details.


## 🏃 Effortlessly Launch RAG Applications
You only need to take care of the application code. Build the RAG application with your favorite languages (python, TS) and frameworks (Langchain, LlamaIndex) and let Paka handles the rest.

### Support for Vector Store
- A fast vector store (qdrant) for storing embeddings.
- Tunable for performance and cost.

### Serverless Deployment
- Deploy your application as a serverless container.
- Autoscaling and monitoring built-in.


## 📈 Monitoring
Paka comes with built-in support for monitoring and tracing. Metrics are collected via Prometheus. Users can also enable Prometheus Alertmanager for alerting.

<div align="center" style="margin-top:20px;margin-bottom:20px;">
<img src="https://raw.githubusercontent.com/jjleng/paka/main/docs/img/tokens_per_sec.png" max-width="1000"/>
</div>

## ⚙️ Architecture

<div align="center" style="margin-top:20px;margin-bottom:20px;">
<img src="https://raw.githubusercontent.com/jjleng/paka/main/docs/img/architecture.png" max-width="1000"/>
</div>

## 📜 Roadmap
- [x] (Multi-cloud) AWS support
- [x] (Backend) vLLM
- [x] (Backend) llama.cpp
- [x] (Platform) Windows support
- [x] (Accelerator) Nvidia GPU support
- [ ] (Multi-cloud) GCP support
- [ ] (Backend) TGI
- [ ] (Accelerator) AMD GPU support
- [ ] (Accelerator) Inferentia support

## 🎬 Getting Started
### Dependencies
- docker daemon and CLI
- AWS CLI
```bash
# Ensure your AWS credentials are correctly configured.
aws configure
```

### Install Paka
```bash
pip install paka
```

### Provisioning the cluster

Create a `cluster.yaml` file with the following content:

```yaml
version: "1.2"
aws:
  cluster:
    name: my-awesome-cluster
    region: us-west-2
    namespace: default
    nodeType: t3a.medium
    minNodes: 2
    maxNodes: 4
  prometheus:
    enabled: true
  modelGroups:
    - name: llama2-7b-chat
      nodeType: g4dn.xlarge
      isPublic: true
      minInstances: 1
      maxInstances: 1
      name: llama3-70b-instruct
      runtime:
        image: vllm/vllm-openai:v0.4.2
      model:
        hfRepoId: TheBloke/Llama-2-7B-Chat-GPTQ
        useModelStore: false
      gpu:
        enabled: true
        diskSize: 50
```

Bring up the cluster with the following command:

```bash
paka cluster up -f cluster.yaml
```

### Code up the application
Use your favorite language and framework to build the application. Here is an example of a Python application using Langchain:

[invoice_extraction](https://github.com/jjleng/paka/tree/main/examples/invoice_extraction)

With Paka, you can effortlessly build your source code and deploy it as a serverless function, no Dockerfile needed. Just ensure the following:

- **Procfile**: Defines the entrypoint for your application. See [Procfile](https://github.com/jjleng/paka/blob/main/examples/invoice_extraction/Procfile).
- **.cnignore file**: Excludes any files that shouldn't be included in the build. See [.cnignore](https://github.com/jjleng/paka/blob/main/examples/invoice_extraction/.cnignore).
- **runtime.txt**: Pins the version of the runtime your application uses. See [runtime.txt](https://github.com/jjleng/paka/blob/main/examples/invoice_extraction/runtime.txt).
- **requirements.txt**: Lists all necessary packages for your application.


### Deploy the App
```bash
paka function deploy --name invoice-extraction --source . --entrypoint serve
```

## Contributing
- code changes
- `make check-all`
- Open a PR
