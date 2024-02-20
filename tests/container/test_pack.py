from unittest.mock import MagicMock, patch

import pytest

from paka.container.pack import get_latest_pack_version, install_pack


def test_get_latest_pack_version() -> None:
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"tag_name": "v1.2.3"}
        mock_get.return_value = mock_response

        result = get_latest_pack_version()

        mock_get.assert_called_once_with(
            "https://api.github.com/repos/buildpacks/pack/releases/latest"
        )

        assert result == "1.2.3"


def test_skipping_installation_when_already_installed() -> None:
    with patch("shutil.which", return_value=True), patch(
        "requests.get"
    ) as mock_get, patch("os.makedirs") as mock_makedirs, patch(
        "tempfile.NamedTemporaryFile"
    ) as mock_tempfile:
        install_pack()

        mock_get.assert_not_called()
        mock_makedirs.assert_not_called()
        mock_tempfile.assert_not_called()


@pytest.mark.parametrize(
    "system, arch, expected_file",
    [
        ("windows", "x86_64", "pack-vX.Y.Z-windows.zip"),
        ("darwin", "amd64", "pack-vX.Y.Z-macos.tgz"),
    ],
)
def test_installation_on_different_systems(
    system: str, arch: str, expected_file: str
) -> None:
    with patch("shutil.which", return_value=False), patch(
        "platform.system", return_value=system
    ), patch("platform.machine", return_value=arch), patch(
        "paka.container.pack.get_latest_pack_version", return_value="X.Y.Z"
    ), patch(
        "requests.get"
    ) as mock_requests, patch(
        "tempfile.NamedTemporaryFile"
    ), patch(
        "tarfile.open"
    ) as mock_tarfile, patch(
        "zipfile.ZipFile"
    ) as mock_zipfile, patch(
        "os.makedirs"
    ), patch(
        "os.unlink"
    ):
        install_pack()

        # Assertions to verify that the correct file is downloaded and extracted
        mock_requests.assert_called_once_with(
            f"https://github.com/buildpacks/pack/releases/download/vX.Y.Z/{expected_file}",
            stream=True,
        )
        if system == "windows":
            mock_zipfile.assert_called_once()
        else:
            mock_tarfile.assert_called_once()
