## Invoice Extraction
This code provides an example of how to build a RESTful API that converts an invoice PDF into a structured data format (JSON). It extracts text from the PDF and then uses the langchain and llama2-7B to extract structured data from the text.

## Running the Example

Follow the steps below to run the example:

1. **Install the necessary dependencies:**
  ```bash
  pip install paka

  # Ensure AWS credentials and CLI are set up. Your AWS credentials should have access to the following services:
  # - S3
  # - ECR
  # - EKS
  # - EC2
  aws configure
  ```

2. **Ensure the Docker daemon is running:**
  ```bash
  docker info
  ```

3. **Provision the cluster:**
  ```bash
  cd examples/invoice_extraction

  # Provision the cluster and update ~/.kube/config
  paka cluster up -f cluster.yaml -u
  ```

4. **Deploy the App:**
  ```bash
  # The command below will build the source and deploy it as a serverless function.
  paka function deploy --name invoice-extraction --source . --entrypoint serve
  ```

5. **Check the status of the functions:**
  ```bash
  paka function list
  ```

  If everything is successful, you should see the function in the list with a status of "READY". By default, the function is exposed through a publicly accessible REST API endpoint.

6. **Test the App:**

  Submit the PDF invoices by hitting the `/extract_invoice` endpoint of the deployed function.

  ```bash
  curl -X POST -H "Content-Type: multipart/form-data" -F "file=@/path/to/invoices/invoice-2024-02-29.pdf" http://invoice-extraction.default.xxxx.sslip.io/extract_invoice
  ```

  If the invoice extraction is successful, you should see the structured data in the response, e.g.

  ```json
  {"number":"#25927345","date":"2024-01-31T05:07:53","company":"Akamai Technologies, Inc.","company_address":"249 Arch St. Philadelphia, PA 19106 USA","tax_id":"United States EIN: 04-3432319","customer":"John Doe","customer_address":"1 Hacker Way Menlo Park, CA  94025","amount":"$5.00"}
  ```
