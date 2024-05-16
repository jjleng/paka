from __future__ import annotations

from typing import Optional

import fasteners
import pulumi_kubernetes as k8s

from paka.config import CloudConfig, Config


class Context:
    _k8s_provider: Optional[k8s.Provider]
    _config: Optional[Config]
    # Materialized bucket with a unique name
    _bucket: Optional[str]
    # Materialized container registry url
    _registry: Optional[str]
    # The kubeconfig str
    _kubeconfig: Optional[str]

    # Need to lock the access to these fields
    _should_save_kubeconfig: bool = False

    def __init__(self) -> None:
        # Ugly, ideally, we can create these locks dynamically in __getattr__.
        # However, __getattr__ is not thread safe either. We need another lock to protect the creation of locks.
        # This lock is going to be a bottleneck. Therefore, we pre-create the locks.
        # Multiple locks pose a risk of deadlock. We need to be careful when acquiring multiple locks.
        self._k8s_provider_lock = fasteners.ReaderWriterLock()
        self._config_lock = fasteners.ReaderWriterLock()
        self._bucket_lock = fasteners.ReaderWriterLock()
        self._registry_lock = fasteners.ReaderWriterLock()
        self._kubeconfig_lock = fasteners.ReaderWriterLock()

    @fasteners.write_locked(lock="_k8s_provider_lock")
    def set_k8s_provider(self, k8s_provider: k8s.Provider) -> None:
        self._k8s_provider = k8s_provider

    @property
    @fasteners.read_locked(lock="_k8s_provider_lock")
    def k8s_provider(self) -> Optional[k8s.Provider]:
        return self._k8s_provider

    @fasteners.write_locked(lock="_config_lock")
    def set_config(self, config: Config) -> None:
        self._config = config

    @property
    @fasteners.read_locked(lock="_config_lock")
    def config(self) -> Optional[Config]:
        return self._config

    @property
    @fasteners.read_locked(lock="_config_lock")
    def cloud_config(self) -> Optional[CloudConfig]:
        if self._config is None:
            raise RuntimeError("Config is not set.")
        if self._config.aws is None:
            raise RuntimeError("Only AWS is supported.")

        return self._config.aws

    @property
    @fasteners.read_locked(lock="_config_lock")
    def region(self) -> Optional[str]:
        # fasteners's inter thread reader lock is reentrant. We can call other methods that acquire the same lock.
        # https://github.com/harlowja/fasteners/blob/06c3f06cab4e135b8d921932019a231c180eb9f4/docs/guide/inter_thread.md#lack-of-features
        return self.cloud_config.cluster.region

    @property
    @fasteners.read_locked(lock="_config_lock")
    def namespace(self) -> Optional[str]:
        # reentrant
        return self.cloud_config.cluster.namespace

    @property
    @fasteners.read_locked(lock="_config_lock")
    def provider(self) -> str:
        # reentrant
        _ = self.cloud_config
        return "aws"

    @property
    @fasteners.read_locked(lock="_config_lock")
    def cluster_name(self) -> str:
        # reentrant
        return self.cloud_config.cluster.name

    @fasteners.write_locked(lock="_bucket_lock")
    def set_bucket(self, bucket: str) -> None:
        self._bucket = bucket

    @property
    @fasteners.read_locked(lock="_bucket_lock")
    def bucket(self) -> Optional[str]:
        return self._bucket

    @fasteners.write_locked(lock="_registry_lock")
    def set_registry(self, registry: str) -> None:
        self._registry = registry

    @property
    @fasteners.read_locked(lock="_registry_lock")
    def registry(self) -> Optional[str]:
        return self._registry

    @fasteners.write_locked(lock="_kubeconfig_lock")
    def set_kubeconfig(self, kubeconfig: str) -> None:
        self._kubeconfig = kubeconfig

    @property
    @fasteners.read_locked(lock="_kubeconfig_lock")
    def kubeconfig(self) -> Optional[str]:
        return self._kubeconfig

    def set_should_save_kubeconfig(self, should_save_kubeconfig: bool) -> None:
        self._should_save_kubeconfig = should_save_kubeconfig

    @property
    def should_save_kubeconfig(self) -> bool:
        return self._should_save_kubeconfig
