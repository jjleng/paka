from light.config import Config, CloudConfig
from pulumi import automation as auto
from light.cluster.aws.object_store import create_object_store
from light.cluster.aws.container_registry import create_container_registry
from light.cluster.aws.eks import create_k8s_cluster

STACK_NAME = "default"


class AWSClusterManager:
    config: CloudConfig

    def __init__(self, config: Config) -> None:
        if config.aws is None:
            raise ValueError("AWS config is required")
        self.config = config.aws

    @property
    def _program(self) -> auto.PulumiFn:
        def internal_program() -> None:
            create_object_store(self.config)
            create_container_registry(self.config)
            create_k8s_cluster(self.config)

        return internal_program

    @property
    def _stack(self) -> auto.Stack:
        project_name = self.config.cluster.name

        # Create a stack with the project name and stack name
        return auto.create_or_select_stack(
            stack_name=STACK_NAME,
            project_name=project_name,
            program=self._program,
        )

    def create(self) -> None:
        # Set AWS region
        self._stack.set_config(
            "aws:region", auto.ConfigValue(value=self.config.cluster.defaultRegion)
        )

        print("Creating resources...")
        self._stack.up(on_output=print)

    def destroy(self) -> None:
        print("Destroying resources...")
        self._stack.destroy(on_output=print)

    def refresh(self) -> None:
        print("Refreshing the stack...")
        self._stack.refresh(on_output=print)

    def preview(self) -> None:
        self._stack.preview(on_output=print)
