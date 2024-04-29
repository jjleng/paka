from unittest.mock import MagicMock, patch

from moto import mock_aws

from paka.container.ecr import authenticate_docker_to_ecr


@mock_aws
def test_authenticate_docker_to_ecr() -> None:
    with patch("subprocess.Popen") as mock_popen:
        mock_result = MagicMock()
        mock_result.communicate.return_value = (b"", b"")
        mock_result.returncode = 0
        mock_popen.return_value = mock_result

        authenticate_docker_to_ecr("us-west-2")
