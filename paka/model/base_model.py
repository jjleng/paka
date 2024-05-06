from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from paka.logger import logger
from paka.model.manifest import ModelFile, ModelManifest
from paka.model.settings import ModelSettings
from paka.model.store import ModelStore, StreamLike
from paka.utils import to_yaml


class BaseMLModel(ABC):
    def __init__(
        self,
        name: str,
        model_store: ModelStore,
        quantization: Optional[str],
        prompt_template_name: Optional[str],
        prompt_template_str: Optional[str],
        # Max concurrency for saving model streams
        concurrency: int = 1,
    ) -> None:
        self.name = name
        self.completed_files: List[Tuple[str, str]] = []
        self.settings = ModelSettings(
            quantization=quantization,
            prompt_template_name=prompt_template_name,
            prompt_template_str=prompt_template_str,
        )

        self.model_store = model_store
        self.concurrency = concurrency

    def save_manifest_yml(self, manifest: Optional[ModelManifest] = None) -> None:
        if manifest is None:
            manifest = ModelManifest(
                name=self.name,
                files=[
                    ModelFile(name=name, sha256=sha256)
                    for (name, sha256) in self.completed_files
                ],
                quantization=self.settings.quantization,
                prompt_template_name=self.settings.prompt_template_name,
                prompt_template_str=self.settings.prompt_template_str,
            )

        model_store = self.model_store

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
        self.try_close_progress_bar()
        self.save_manifest_yml()

    def try_close_progress_bar(self) -> None:
        pb = getattr(self.model_store, "progress_bar", None)
        if pb:
            pb.close_progress_bar()
