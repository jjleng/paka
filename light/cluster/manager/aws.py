from light.config import Config, CloudConfig
from pulumi import automation as auto
import pulumi_eks as eks
import pulumi_kubernetes as k8s
from light.cluster.aws.object_store import create_object_store
from light.cluster.aws.container_registry import create_container_registry
from light.cluster.aws.eks import create_k8s_cluster
from light.model_group_service.service import create_model_group_service

STACK_NAME = "default"


class AWSClusterManager:
    _orig_config: Config
    config: CloudConfig

    def __init__(self, config: Config) -> None:
        self._orig_config = config
        if config.aws is None:
            raise ValueError("AWS config is required")
        self.config = config.aws

    def _provision_k8s(self) -> eks.Cluster:
        create_object_store(self.config)
        create_container_registry(self.config)
        return create_k8s_cluster(self.config)

    def _stack_for_program(self, program: auto.PulumiFn) -> auto.Stack:
        return auto.create_or_select_stack(
            stack_name=STACK_NAME,
            project_name=self.config.cluster.name,
            program=program,
        )

    @property
    def _stack(self) -> auto.Stack:
        def program() -> None:
            self._provision_k8s()

        return self._stack_for_program(program)

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

    def start_model_group_service(self) -> None:
        def program() -> None:
            cluster = self._provision_k8s()

            k8s_provider = k8s.Provider("k8s-provider", kubeconfig=cluster.kubeconfig)

            if self.config.modelGroups is None:
                print("No model groups found")
                return

            for model_group in self.config.modelGroups:
                create_model_group_service(self._orig_config, model_group, k8s_provider)

        stack = self._stack_for_program(program)
        stack.up(on_output=print)
