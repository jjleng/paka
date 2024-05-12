from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any

from pulumi import automation as auto

from paka.cluster.context import Context
from paka.cluster.pulumi import ensure_pulumi
from paka.config import CloudConfig, Config
from paka.constants import PULUMI_STACK_NAME
from paka.k8s.model_group.service import (
    cleanup_staled_model_group_services,
    create_model_group_service,
)
from paka.k8s.model_group.service_v1 import (
    create_model_group_service as create_model_group_service_v1,
)
from paka.logger import logger

STACK_NAME = "default"


class ClusterManager(ABC):
    """
    Abstract base class for a cluster manager.

    A ClusterManager is responsible for managing a cluster of compute resources.

    Subclasses must implement the abstract methods defined in this class.
    """

    config: Config
    cloud_config: CloudConfig

    def __init__(self, config: Config) -> None:
        self.config = config
        if not config.aws is None:
            self.cloud_config = config.aws
        self.ctx = Context()
        self.ctx.set_config(config)

    @abstractmethod
    def provision_k8s(self) -> None:
        pass

    def _stack_for_program(self, program: auto.PulumiFn) -> auto.Stack:
        return auto.create_or_select_stack(
            stack_name=PULUMI_STACK_NAME,
            project_name=self.cloud_config.cluster.name,
            program=program,
        )

    @cached_property
    def _stack(self) -> auto.Stack:
        ensure_pulumi()

        def program() -> None:
            self.provision_k8s()

        return self._stack_for_program(program)

    def create(self) -> None:
        if self.config.aws is None:
            raise ValueError("Only AWS is supported.")

        if self.config.aws:
            self._stack.set_config(
                "aws:region", auto.ConfigValue(value=self.cloud_config.cluster.region)
            )

        logger.info("Creating resources...")
        self._stack.up(on_output=logger.info)

        if (
            self.cloud_config.modelGroups is None
            and self.cloud_config.mixedModelGroups is None
        ):
            return

        namespace = self.cloud_config.cluster.namespace

        # Clean up staled model group resources before creating new ones
        model_group_names = [mg.name for mg in self.config.aws.modelGroups or []]
        mixed_model_group_names = [
            mg.name for mg in self.config.aws.mixedModelGroups or []
        ]
        all_group_names = model_group_names + mixed_model_group_names

        cleanup_staled_model_group_services(namespace, all_group_names)
        # TODO: We should clean up deployment as well

        for model_group in self.cloud_config.modelGroups or []:
            create_model_group_service(self.ctx, namespace, model_group)

        for mixed_model_group in self.cloud_config.mixedModelGroups or []:
            create_model_group_service_v1(self.ctx, namespace, mixed_model_group)

    def destroy(self) -> Any:
        logger.info("Destroying resources...")
        return self._stack.destroy(on_output=logger.info)

    def refresh(self) -> None:
        logger.info("Refreshing the stack...")
        self._stack.refresh(on_output=logger.info)

    def preview(self, *args: Any, **kwargs: Any) -> None:
        if not "on_output" in kwargs:
            kwargs["on_output"] = logger.info
        self._stack.preview(*args, **kwargs)
