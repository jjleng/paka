import concurrent.futures
from typing import Any

import boto3
from huggingface_hub import HfFileSystem
from pydantic import BaseModel

from paka.kube_resources.model_group.models.base import Model
from paka.utils import to_yaml


class HuggingFaceModelManifest(BaseModel):
    repo_id: str
    files: list[tuple[str, str]]
    inference_devices: list[str]
    quantization: str
    runtime: str
    prompt_template: str


class HuggingFaceModel(Model):
    def __str__(self) -> str:
        return "HuggingFaceModel"

    def __init__(
        self,
        repo_id: str,
        files: list[str],
        inference_devices: list[str] = ["cpu"],
        quantization: str = "GPTQ",
        runtime: str = "llama.cpp",
        prompt_template: str = "chatml",
        download_max_concurrency: int = 10,
        s3_chunk_size: int = 8 * 1024 * 1024,
        s3_max_concurrency: int = 20,
    ) -> None:
        super().__init__(
            repo_id,
            inference_devices,
            quantization,
            runtime,
            prompt_template,
            download_max_concurrency,
            s3_chunk_size,
            s3_max_concurrency,
        )
        self.repo_id: str = repo_id
        self.fs = HfFileSystem()
        self.orginal_files = files
        self.files: list[str] = []

    def validate_files(self) -> None:
        """
        Validates the list of files to download.
        """
        verified_files: list[str] = []
        for file in self.orginal_files:
            match_files = self.fs.glob(f"{self.repo_id}/{file}")
            if len(match_files) > 0:
                verified_files = verified_files + match_files
            else:
                self.logging_for_class(
                    f"File {file} not found in repository {self.repo_id}", "warn"
                )

        self.files = verified_files

    def get_file_info(self, hf_file_path: str) -> dict[str, Any]:
        """
        Get information about a file on Hugging Face.

        Args:
            hf_file_path (str): The path to the file on Hugging Face.

        Returns:
            dict: A dictionary containing information about the file.
        """
        # Get the file information
        file_info: dict[str, Any] = self.fs.stat(hf_file_path)

        return file_info

    def upload(self, hf_file_path: str) -> None:
        """
        Uploads a Hugging Face model file to the specified file system.

        Args:
            hf_file_path (str): The path to the Hugging Face model file.

        Returns:
            None
        """
        file_info = self.get_file_info(hf_file_path)
        total_size = file_info["size"]
        sha256 = (
            file_info["lfs"]["sha256"]
            if "lfs" in file_info and file_info["lfs"]
            else ""
        )
        with self.fs.open(hf_file_path, "rb") as hf_file:
            self.download(hf_file_path, hf_file, total_size, sha256)

    def save_manifest_yml(self) -> None:
        """
        Saves the HuggingFaceModelManifest YAML file for the model.

        This method creates a `HuggingFaceModelManifest` object with the specified parameters and converts it to YAML format.
        The resulting YAML is then saved to an S3 bucket with the file path "{repo_id}/manifest.yml".

        Returns:
            None

        Raises:
            None
        """
        manifest = HuggingFaceModelManifest(
            repo_id=self.repo_id,
            files=self.completed_files,
            inference_devices=self.inference_devices,
            quantization=self.quantization,
            runtime=self.runtime,
            prompt_template=self.prompt_template,
        )
        manifest_yml = to_yaml(manifest.model_dump(exclude_none=True))
        file_path = self.get_s3_file_path(f"{self.repo_id}/manifest.yml")
        s3 = boto3.resource("s3")
        s3.Object(self.s3_bucket, file_path).put(Body=manifest_yml)
        self.logging_for_class(f"manifest.yml file saved to {file_path}")

    def upload_files(self) -> None:
        """
        Upload multiple files from Hugging Face to S3 in parallel.
        Returns:
            None
        """
        self.logging_for_class("Uploading files to S3...")
        self.validate_files()
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.download_max_concurrency
        ) as executor:
            futures = [executor.submit(self.upload, file) for file in self.files]
            concurrent.futures.wait(futures)
            # Callback function to handle completion of all workers
            self.handle_upload_completion()

    def handle_upload_completion(self) -> None:
        """
        Callback function to handle completion of all workers.
        This function will be called after all files have been uploaded.
        Returns:
            None
        """
        # Add your code here to handle the completion of all workers
        # For example, you can log a message or perform any post-processing tasks
        self.save_manifest_yml()
        self.completed_files = []
        self.clear_counter()
        self.close_pbar()
        self.logging_for_class("All files have been uploaded.")
