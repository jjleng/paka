import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from paka.constants import HOME_ENV_VAR
from paka.container.pack import ensure_pack


def test_installation_on_windows() -> None:
    with patch(
        "platform.system", return_value="windows"
    ), tempfile.TemporaryDirectory() as temp_dir:
        os.environ[HOME_ENV_VAR] = temp_dir

        pack = Path(ensure_pack())

        assert pack.exists()
        assert str(pack).endswith(".exe")


@pytest.mark.parametrize(
    "system, arch",
    [("darwin", "amd64"), ("darwin", "arm64"), ("linux", "amd64"), ("linux", "arm64")],
)
def test_installation_on_other_platforms(system: str, arch: str) -> None:
    with patch("platform.system", return_value=system), patch(
        "platform.machine", return_value=arch
    ), tempfile.TemporaryDirectory() as temp_dir:
        os.environ[HOME_ENV_VAR] = temp_dir

        pack = Path(ensure_pack())

        assert pack.exists()
