import os
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple

from paka.logger import logger
from paka.model.manifest import ModelFile, ModelManifest
from paka.model.settings import ModelSettings
from paka.model.store import ModelStore, S3ModelStore, StreamLike
from paka.utils import read_current_cluster_data, to_yaml


class BaseMLModel(ABC):
    def __init__(
        self,
        name: str,
        inference_devices: List[str],
        quantization: str,
        runtime: str,
        prompt_template_name: Optional[str],
        prompt_template_str: Optional[str],
        # Max concurrency for saving model streams
        concurrency: int = 1,
    ) -> None:
        self.name = name
        self.completed_files: List[Tuple[str, str]] = []
        self.settings = ModelSettings(
            inference_devices=inference_devices,
            quantization=quantization,
            runtime=runtime,
            prompt_template_name=prompt_template_name,
            prompt_template_str=prompt_template_str,
        )

        self.model_store = self.get_model_store()
        self.concurrency = concurrency

    @staticmethod
    def get_model_store(*args: Any, **kwargs: Any) -> ModelStore:
        provider = read_current_cluster_data("provider")
        if provider != "aws":
            raise ValueError("Only AWS is supported.")

        return S3ModelStore(*args, **kwargs)

    def save_manifest_yml(self, manifest: Optional[ModelManifest] = None) -> None:
        if manifest is None:
            manifest = ModelManifest(
                name=self.name,
                files=[
                    ModelFile(name=name, sha256=sha256)
                    for (name, sha256) in self.completed_files
                ],
                inference_devices=self.settings.inference_devices,
                quantization=self.settings.quantization,
                runtime=self.settings.runtime,
                prompt_template_name=self.settings.prompt_template_name,
                prompt_template_str=self.settings.prompt_template_str,
            )

        model_store = self.get_model_store(with_progress_bar=False)

        manifest_yml = to_yaml(manifest.model_dump(exclude_none=True))

        file_path = f"{self.name}/manifest.yml"
        if model_store.file_exists(file_path):
            logger.info(
                f"manifest.yml file already exists at {file_path}. Overwriting..."
            )
            model_store.delete_file(file_path)
        model_store.save(file_path, manifest_yml.encode("utf-8"))
        logger.info(f"manifest.yml file saved to {file_path}")

    @abstractmethod
    def save(self) -> None:
        pass

    def save_single_stream(
        self, path: str, stream: StreamLike, total_size: int, sha256: str = ""
    ) -> None:
        self.model_store.save_stream(path, stream, total_size, sha256)
        fname = os.path.basename(path)
        self.completed_files.append((fname, sha256))

    def finish(self) -> None:
        self.save_manifest_yml()
        pb = getattr(self.model_store, "progress_bar", None)
        if pb:
            pb.close_progress_bar()
