import concurrent.futures
from typing import Any

import boto3
import requests
from pydantic import BaseModel

from paka.kube_resources.model_group.models.base import Model
from paka.logger import logger
from paka.utils import to_yaml


class HttpSourceManifest(BaseModel):
    name: str
    urls: list[str]
    inference_devices: list[str]
    quantization: str
    runtime: str
    prompt_template: str


class HttpSourceModel(Model):
    def __str__(self) -> str:
        return "HttpSourceModel"

    def __init__(
        self,
        name: str,
        urls: list[str],
        inference_devices: list[str] = ["cpu"],
        quantization: str = "GPTQ",
        runtime: str = "llama.cpp",
        prompt_template: str = "chatml",
        download_max_concurrency: int = 10,
        s3_chunk_size: int = 8 * 1024 * 1024,
        s3_max_concurrency: int = 20,
    ) -> None:
        super().__init__(
            name,
            inference_devices,
            quantization,
            runtime,
            prompt_template,
            download_max_concurrency,
            s3_chunk_size,
            s3_max_concurrency,
        )
        self.urls = urls

    def save_manifest_yml(self) -> None:
        """
        Saves the HttpSourceManifest YAML file for the model.

        This method creates a `HttpSourceManifest` object with the specified parameters and converts it to YAML format.
        The resulting YAML is then saved to an S3 bucket with the file path "{name}/manifest.yml".

        Returns:
            None

        Raises:
            None
        """
        manifest = HttpSourceManifest(
            name=self.name,
            urls=self.completed_files,
            inference_devices=self.inference_devices,
            quantization=self.quantization,
            runtime=self.runtime,
            prompt_template=self.prompt_template,
        )
        manifest_yml = to_yaml(manifest.model_dump(exclude_none=True))
        file_path = self.get_s3_file_path(f"{self.name}/manifest.yml")
        s3 = boto3.resource("s3")
        if self.s3_file_exists(file_path):
            self.logging_for_class(
                f"manifest.yml file already exists at {file_path}. Overwriting..."
            )
            s3.Object(self.s3_bucket, file_path).delete()
        s3.Object(self.s3_bucket, file_path).put(Body=manifest_yml)
        self.logging_for_class(f"manifest.yml file saved to {file_path}")

    def upload(self, url: str) -> None:
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            self.download(url, response, total_size)

    def upload_files(self) -> None:
        """
        Upload multiple files from http urls in parallel.
        Returns:
            None
        """
        self.logging_for_class("Uploading http sources to S3...")
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.download_max_concurrency
        ) as executor:
            futures = [executor.submit(self.upload, url) for url in self.urls]
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
