import os
import tempfile
from unittest.mock import patch

import pytest

from paka.cluster.kubectl import ensure_kubectl
from paka.constants import HOME_ENV_VAR


@pytest.mark.parametrize(
    "system, arch",
    [
        ("darwin", "amd64"),
        ("darwin", "arm64"),
        ("linux", "amd64"),
        ("linux", "arm64"),
        ("windows", "amd64"),
        ("windows", "arm64"),
    ],
)
def test_installation(system: str, arch: str) -> None:
    with patch("platform.system", return_value=system), patch(
        "platform.machine", return_value=arch
    ), tempfile.TemporaryDirectory() as temp_dir:
        os.environ[HOME_ENV_VAR] = temp_dir
        orig_path = os.environ["PATH"]

        try:
            ensure_kubectl()
            bin = "kubectl"
            if system == "windows":
                bin += ".exe"
            paths = os.environ["PATH"].split(":")
            list_of_list = [p.split(";") for p in paths if p]
            paths = [item for sublist in list_of_list for item in sublist]

            for path in paths:
                if os.path.exists(os.path.join(path, bin)):
                    break
            else:
                pytest.fail(f"{bin} not found in PATH")
        finally:
            os.environ["PATH"] = orig_path
