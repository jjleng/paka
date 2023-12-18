from light.cluster.config import Config, CloudConfig
from pulumi import automation as auto
from light.cluster.iac.aws_eks import provision_k8s


class AWSClusterManager:
    config: CloudConfig

    def __init__(self, config: Config) -> None:
        if config.aws is None:
            raise ValueError("AWS config is required")
        self.config = config.aws

    def create(self) -> None:
        project_name = self.config.cluster.name
        stack_name = "prod"

        stack = auto.create_or_select_stack(
            stack_name=stack_name, project_name=project_name, program=provision_k8s
        )

        # Set AWS region
        stack.set_config(
            "aws:region", auto.ConfigValue(value=self.config.cluster.defaultRegion)
        )

        # Deploy the stack
        print("Creating resources...")
        stack.up(on_output=print)

    def destroy(self) -> None:
        project_name = self.config.cluster.name
        stack_name = "prod"

        # Select the stack
        stack = auto.select_stack(
            stack_name=stack_name, project_name=project_name, program=provision_k8s
        )

        # Destroy the stack resources
        print("Destroying resources...")
        stack.destroy(on_output=print)

    def refresh(self) -> None:
        project_name = self.config.cluster.name
        stack_name = "prod"

        # Select the stack
        stack = auto.select_stack(
            stack_name=stack_name, project_name=project_name, program=provision_k8s
        )

        # Destroy the stack resources
        print("Refreshing the stack...")
        stack.refresh(on_output=print)
