from abc import ABC, abstractmethod

from pulumi import automation as auto

from light.config import CloudConfig, Config
from light.constants import APP_NS
from light.kube_resources.model_group.ingress import (
    create_model_group_ingress,
    create_model_vservice,
)
from light.kube_resources.model_group.service import create_model_group_service
from light.logger import logger
from light.utils import save_cluster_data

STACK_NAME = "default"


class ClusterManager(ABC):
    _orig_config: Config
    config: CloudConfig

    def __init__(self, config: Config) -> None:
        self._orig_config = config
        if not config.aws is None:
            self.config = config.aws

    @abstractmethod
    def provision_k8s(self) -> None:
        pass

    def _stack_for_program(self, program: auto.PulumiFn) -> auto.Stack:
        return auto.create_or_select_stack(
            stack_name=STACK_NAME,
            project_name=self.config.cluster.name,
            program=program,
        )

    @property
    def _stack(self) -> auto.Stack:
        def program() -> None:
            self.provision_k8s()

        return self._stack_for_program(program)

    def create(self) -> None:
        if self._orig_config.aws:
            self._stack.set_config(
                "aws:region", auto.ConfigValue(value=self.config.cluster.defaultRegion)
            )

        save_cluster_data(
            self.config.cluster.name, "region", self.config.cluster.defaultRegion
        )

        logger.info("Creating resources...")
        self._stack.up(on_output=logger.info)

        if self.config.modelGroups is None:
            return

        create_model_group_ingress(APP_NS)
        for model_group in self.config.modelGroups:
            create_model_group_service(APP_NS, self._orig_config, model_group)
            create_model_vservice(APP_NS, model_group.name)

    def destroy(self) -> None:
        logger.info("Destroying resources...")
        self._stack.destroy(on_output=logger.info)

    def refresh(self) -> None:
        logger.info("Refreshing the stack...")
        self._stack.refresh(on_output=logger.info)

    def preview(self) -> None:
        self._stack.preview(on_output=logger.info)
