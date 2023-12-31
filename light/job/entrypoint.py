from kubernetes import client
from light.k8s import apply_resource
from light.config import CloudConfig
import json


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
    json_body_dict = json.loads(json_body)
    dst_name = json_body_dict["filename"]

    escaped_json_body = json_body.replace('"', '\\"')

    bash_script = f"""#!/bin/sh

# URL of the fetch endpoint
FETCH_URL="http://localhost:8000/fetch"

# Stringified JSON body for the POST request
JSON_BODY='{escaped_json_body}'

WORKING_DIR='/userfunc/{dst_name}'

# Directory containing secrets
SECRETS_DIR="/secrets"

# Function to convert filename to environment variable name
convert_to_env_name() {{
    local filename=$1
    echo "$filename" | tr '[:lower:]-' '[:upper:]_'
}}

# Function to perform an HTTP POST request using Python or Node.js
perform_request() {{
  if command -v python &>/dev/null; then
    python -c "import urllib.request; req = urllib.request.Request('$FETCH_URL', data='$JSON_BODY'.encode('utf-8'), headers={{'Content-Type': 'application/json'}}, method='POST'); print(urllib.request.urlopen(req).getcode())"
  elif command -v node &>/dev/null; then
    node -e "const http = require('http'); const data = '$JSON_BODY'; const req = http.request('$FETCH_URL', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) }} }}, (res) => {{ console.log(res.statusCode); }}); req.on('error', console.error); req.write(data); req.end();"
  else
    echo "No supported runtime (Python or Node.js) found for HTTP request"
    exit 1
  fi
}}

# Main logic
while true; do
  response=$(perform_request | tail -n 1)
  if [ "$response" -eq 200 ]; then
    echo "Fetch successful. Executing the runtime command."

    cd "$WORKING_DIR"

    if command -v python &>/dev/null; then
      export PYTHONPATH="$WORKING_DIR:$PYTHONPATH"

      if [ -d "$WORKING_DIR/bin" ]; then
        export PATH="$WORKING_DIR/bin:$PATH"
      fi
    fi

    # Create a temporary file
    temp_file=$(mktemp)

    # Find files and save the list to the temporary file
    find "$SECRETS_DIR" -type f > "$temp_file"

    # Read from the temporary file
    while IFS= read -r file; do
        # Extract filename without the leading directory path
        filename=$(basename "$file")

        # Convert filename to environment variable name
        env_name=$(convert_to_env_name "$filename")

        # Read the content of the file
        file_content=$(cat "$file")

        # Export the content as an environment variable
        export "$env_name=$file_content"
    done < "$temp_file"

    # Remove the temporary file
    rm "$temp_file"

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
