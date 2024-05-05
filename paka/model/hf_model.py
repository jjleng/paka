from __future__ import annotations

import concurrent.futures
import os
from typing import Any, Dict, List, Optional

from huggingface_hub import HfFileSystem
from huggingface_hub.utils import validate_repo_id

from paka.logger import logger
from paka.model.base_model import BaseMLModel
from paka.model.store import ModelStore


class HuggingFaceModel(BaseMLModel):
    def __init__(
        self,
        name: str,
        repo_id: str,
        files: List[str],
        model_store: ModelStore,
        quantization: Optional[str] = None,
        prompt_template_name: Optional[str] = None,
        prompt_template_str: Optional[str] = None,
    ) -> None:
        super().__init__(
            name=name,
            model_store=model_store,
            quantization=quantization,
            prompt_template_name=prompt_template_name,
            prompt_template_str=prompt_template_str,
        )
        validate_repo_id(repo_id)
        self.repo_id: str = repo_id
        self.fs = HfFileSystem()
        self._files = files

    def save(self) -> None:
        """
        Saves the model to a model store.
        """
        files: List[str] = []
        for file in self._files:
            match_files = self.fs.glob(f"{self.repo_id}/{file}")

            if not match_files:
                logger.warn(
                    f"No matching files found for {file} in HuggingFace repo {self.repo_id}"
                )

            files.extend(match_files)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.concurrency
        ) as executor:
            futures = [executor.submit(self._save_single_file, file) for file in files]
            concurrent.futures.wait(futures)
            self.finish()

    def _save_single_file(self, hf_file_path: str) -> None:
        """
        Saves a HuggingFace model file to the specified model store.

        Args:
            hf_file_path (str): The path to the HuggingFace model file.

        Returns:
            None
        """
        file_info: Dict[str, Any] = self.fs.stat(hf_file_path)
        total_size = file_info["size"]
        sha256 = (
            file_info["lfs"]["sha256"]
            if "lfs" in file_info and file_info["lfs"]
            else ""
        )

        fname = os.path.basename(hf_file_path)
        with self.fs.open(hf_file_path, "rb") as hf_file:
            self.save_single_stream(f"{self.name}/{fname}", hf_file, total_size, sha256)
