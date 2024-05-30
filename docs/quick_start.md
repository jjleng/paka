Since Paka currently only supports AWS, the quick start guide will be tailored to AWS.

### Install the necessary dependencies
- Install docker daemon and CLI.
- Install the aws cli and ensure your AWS credentials are correctly configured.
```bash
aws configure
```
- Install Paka.
```bash
pip install paka
```

### Request GPU quota increase
Go to the AWS console and request a quota increase. Beware that there are two types of quotas: On-Demand and Spot. The On-Demand quota is the number of instances that are not preemptible, while the Spot quota is the number of instances that can be preempted. Spot instances are cheaper than On-Demand instances.

Paka supports mixed instance types, so you can use spot instances for cost savings and on-demand instances as a fallback.

### Create a cluster config file
Create a `cluster.yaml` (could be any name) file. See [cluster.yaml](https://github.com/jjleng/paka/blob/main/examples/invoice_extraction/cluster.yaml) as an example. Refer to the [cluster config](https://github.com/jjleng/paka/blob/main/docs/cluster_config.md) for the fields that can be included in the cluster config file.

### Provision the cluster
Provision the cluster with the following command:
```bash
paka cluster up -f cluster.yaml
```

### Build an LLM powered application
Create an application skeleton. See [invoice_extraction](https://github.com/jjleng/paka/tree/main/examples/invoice_extraction) as an example. Ensure the following files are included in your application root directory:

- **Procfile**: Defines the entrypoint for your application. See [Procfile](https://github.com/jjleng/paka/blob/main/examples/invoice_extraction/Procfile).
- **.cnignore file**: Excludes any files that shouldn't be included in the build. See [.cnignore](https://github.com/jjleng/paka/blob/main/examples/invoice_extraction/.cnignore).
- **runtime.txt**: Pins the version of the runtime your application uses. See [runtime.txt](https://github.com/jjleng/paka/blob/main/examples/invoice_extraction/runtime.txt).
- **requirements.txt or package.json**: Lists all necessary packages for your application.


### Deploy the application
```bash
paka function deploy --name APP_NAME --source . --entrypoint ENTRYPOINT_NAME
```

APP_NAME is the name of the application. The command above will build the source and deploy it as a serverless function.
`--source` specifies the source directory of the application.
`--entrypoint` specifies the entrypoint of the application, which is defined in the Procfile.

### Check the logs
For AWS deployment, logs are sinked to AWS CloudWatch. You can view the logs by navigating to the CloudWatch console and selecting the log group for the function you want to monitor. Alternatively, you can use the Stern CLI (https://github.com/stern/stern) to view the logs.

To view the model logs, you can use the following command:
```bash
stern --selector app=model-group
```

To view the function logs, you can use the following command:
```bash
stern "my-app*"
```

### Continuous Integration/Deployment
You can set up a CI/CD pipeline to automate the deployment process. For example, you can use GitHub Actions to build and deploy the application on every push to the main branch. To deploy the local changes to the cloud, you can simply run the deploy command again.

```bash
paka function deploy --name APP_NAME --source . --entrypoint ENTRYPOINT_NAME
```

### Tear down the cluster
```bash
paka cluster down -f cluster.yaml -y
```
