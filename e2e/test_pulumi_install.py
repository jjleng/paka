import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from paka.cluster.pulumi import ensure_pulumi
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

        ensure_pulumi()

        bin = "pulumi"
        if system == "windows":
            bin += ".exe"

        assert shutil.which(bin) is not None
