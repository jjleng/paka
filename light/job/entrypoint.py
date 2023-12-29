from kubernetes import client
from light.k8s import apply_resource
from light.config import CloudConfig


def write_entrypoint_script_to_cfgmap(
    config: CloudConfig, runtime_command: str, json_body: str
) -> None:
    """
    Writes the entrypoint script to the given path.

    Args:
        runtime_command (str): The runtime command to be executed.
        json_body (str): The stringified JSON body for the POST request.

    Returns:
        None
    """
    project = config.cluster.name

    bash_script = f"""#!/bin/sh

# URL of the fetch endpoint
FETCH_URL="http://localhost:8000/fetch"

# Stringified JSON body for the POST request
JSON_BODY='{json_body}'

# Change directory to /userfunc/
cd /userfunc/

# Function to perform an HTTP POST request using Python or Node.js
perform_request() {{
  if command -v python &>/dev/null; then
    python -c "import urllib.request; req = urllib.request.Request('$FETCH_URL', data='{json_body}'.encode(), headers={{'Content-Type': 'application/json'}}, method='POST'); print(urllib.request.urlopen(req).getcode())"
  elif command -v node &>/dev/null; then
    node -e "const http = require('http'); const data = '{json_body}'; const req = http.request('$FETCH_URL', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: data }}, (res) => {{ console.log(res.statusCode); }}); req.on('error', console.error); req.write(data); req.end();"
  else
    echo "No supported runtime (Python or Node.js) found for HTTP request"
    exit 1
  fi
}}

# Main logic
while true; do
  response=$(perform_request)
  if [ "$response" -eq 200 ]; then
    echo "Fetch successful. Executing the runtime command."

    # Execute the runtime command
    {runtime_command}
    break
  else
    echo "Fetch not ready. Retrying in 5 seconds."
    sleep 5
  fi
done
"""
    configmap_data = {"entrypoint.sh": bash_script}

    # Write the entrypoint script to the configmap
    config_map = client.V1ConfigMap(
        kind="ConfigMap",
        metadata=client.V1ObjectMeta(
            name="entrypoint-script", namespace="celery-workers"
        ),
        data=configmap_data,
    )
    apply_resource(project, config_map)
