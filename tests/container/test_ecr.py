from unittest.mock import ANY, patch

from moto import mock_aws

from paka.container.ecr import authenticate_docker_to_ecr


@mock_aws
def test_authenticate_docker_to_ecr() -> None:
    with patch("subprocess.run") as mock_subprocess:
        authenticate_docker_to_ecr("us-west-2")
        mock_subprocess.assert_called_with(
            ["docker", "login", "-u", ANY, "-p", ANY, ANY], check=True
        )
