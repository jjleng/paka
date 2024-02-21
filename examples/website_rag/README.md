## website-rag
This code provides an example for Quality Answering (QA) of a website by leveraging LangChain. It begins by scraping the website to gather necessary data. The scraped text is then segmented into chunks. These chunks are transformed into embeddings, a numerical representation of the text data, which are then stored in a vector store, specifically Qdrant.

These embeddings are used to facilitate Question Answering (QA) with the help of Llama2-7b. This allows for interactive querying of the stored data, providing a robust tool for website QA.

## Running the example

To run the example, first install the necessary dependencies:
```bash
pip install paka

# Make sure aws credentials and cli are set up. Your aws credentials should have access to the following services:
# - S3
# - ECR
# - EKS
# - EC2
aws configure
```

### Make sure docker daemon is running
```bash
docker info
```

### Provisioning the cluster

```bash
cd examples/website_rag

# Provision the cluster and update ~/.kube/config
paka cluster up -f cluster.yaml -u
```

### Scrape the website and create embeddings


```bash
# Default BP_BUILDER is "paketobuildpacks/builder:base".
# Here we use "paketobuildpacks/builder:full" to install sqlite
# `ingest` is the entrypoint for the container, which is defined in the Procfile.
BP_BUILDER="paketobuildpacks/builder:full" paka run --entrypoint ingest --source .
```

The command above will scrape https://python.langchain.com/docs, chunk the text, and create embeddings through langchain. Embeddings are created by a light Bert model that is managed by paka model group. The embeddings are then stored in a Qdrant cluster provisioned by paka.

### Run the serverless LangServe App

```bash
# Below command will build the source and deploy it as a serverless function.
BP_BUILDER="paketobuildpacks/builder:full" paka function deploy --name langchain-docs --source . --entrypoint serve

# Or, without building from the source, you can deploy the pre-built image
paka function deploy --name langchain-docs --image website_rag-latest --entrypoint serve
```

Check the statuses of the functions
```bash
paka function list
```

If everything is successful, you should see the function in the list with a status of "READY". By default, the function is exposed through a public accessible REST API endpoint.

### Query the website

Doing a similarity search by hitting the `/invoke` endpoint of the deployed function.

```bash
curl -X POST -H "Content-Type: application/json" -d '{"input": "what is langchain"}' http://langchain-docs.default.xxxx.sslip.io/invoke
```

Asking a question by hitting the `/v2/invoke` endpoint of the deployed function. This will use the Llama2-7b model to answer the question.

NOTE: The request may take a while to respond since by default we are asking the model to generate answers based on 4 documents. RetrievalQA cannot stream the response; everything has to be processed before the response is sent back.

```bash
curl -X POST -H "Content-Type: application/json" -d '{"input": "what is langchain"}' http://langchain-docs.default.xxxx.sslip.io/v2/invoke
```
