from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any

from pulumi import automation as auto

from paka.cluster.pulumi import ensure_pulumi
from paka.config import CloudConfig, Config
from paka.k8s.model_group.service import (
    cleanup_staled_model_group_services,
    create_model_group_service,
)
from paka.logger import logger
from paka.utils import read_cluster_data, save_cluster_data

STACK_NAME = "default"


class ClusterManager(ABC):
    """
    Abstract base class for a cluster manager.

    A ClusterManager is responsible for managing a cluster of compute resources.

    Subclasses must implement the abstract methods defined in this class.
    """

    _orig_config: Config
    config: CloudConfig

    def __init__(self, config: Config) -> None:
        self._orig_config = config
        if not config.aws is None:
            self.config = config.aws
        save_cluster_data(
            self.config.cluster.name, "namespace", self.config.cluster.namespace
        )

    @abstractmethod
    def provision_k8s(self) -> None:
        pass

    def _stack_for_program(self, program: auto.PulumiFn) -> auto.Stack:
        return auto.create_or_select_stack(
            stack_name=STACK_NAME,
            project_name=self.config.cluster.name,
            program=program,
        )

    @cached_property
    def _stack(self) -> auto.Stack:
        ensure_pulumi()

        def program() -> None:
            self.provision_k8s()

        return self._stack_for_program(program)

    def create(self) -> None:
        if self._orig_config.aws is None:
            raise ValueError("Only AWS is supported.")

        if self._orig_config.aws:
            self._stack.set_config(
                "aws:region", auto.ConfigValue(value=self.config.cluster.region)
            )

        save_cluster_data(
            self.config.cluster.name, "region", self.config.cluster.region
        )

        logger.info("Creating resources...")
        self._stack.up(on_output=logger.info)

        if self.config.modelGroups is None:
            return

        namespace = read_cluster_data(self.config.cluster.name, "namespace")

        # Clean up staled model group resources before creating new ones
        cleanup_staled_model_group_services(
            namespace, [mg.name for mg in self._orig_config.aws.modelGroups or []]
        )

        for model_group in self.config.modelGroups:
            create_model_group_service(namespace, self._orig_config, model_group)

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
