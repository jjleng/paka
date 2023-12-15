import subprocess
import shutil
import sys
from typing import Dict, List
import os

cwd = os.path.dirname(__file__)


def is_packer_installed() -> bool:
    """Check if Packer is installed."""
    return shutil.which("packer") is not None


def build_packer_image(template_path: str, variables: Dict[str, str]) -> None:
    """Run Packer build command."""
    if not is_packer_installed():
        raise Exception("Packer is not installed or not found in PATH.")

    # Convert variables dictionary to Packer variable args
    var_args: List[str] = sum([["-var", f"{k}={v}"] for k, v in variables.items()], [])

    # Construct the Packer command
    command = ["packer", "build"] + var_args + [template_path]

    # Execute the command
    subprocess.run(command, check=True, cwd=cwd)


def main() -> None:
    build_packer_image("./aws.pkr.hcl", {})


if __name__ == "__main__":
    main()
