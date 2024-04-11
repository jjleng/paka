import concurrent.futures
from typing import Any

from huggingface_hub import HfFileSystem
from pydantic import BaseModel

from paka.kube_resources.model_group.models.abstract import Model
from paka.logger import logger
from paka.utils import to_yaml


class Manifest(BaseModel):
    repo_id: str
    files: list[str]
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
        self.repo_id = repo_id
        self.fs = HfFileSystem()
        self.files = self.validate_files(files)

    def validate_files(self, files: list[str]) -> list[str]:
        """
        Validates the list of files to download.
        """
        verified_files: list[str] = []
        for file in files:
            match_files = self.fs.glob(f"{self.repo_id}/{file}")
            if len(match_files) > 0:
                verified_files = verified_files + match_files
            else:
                self.logging_for_class(
                    f"File {file} not found in repository {self.repo_id}", "warn"
                )
        return verified_files

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

    def upload_file_to_s3(self, hf_file_path: str) -> None:
        """
        Upload a file from Hugging Face to S3.

        Args:
            hf_file_path (str): The path to the file on Hugging Face.

        Returns:
            None
        """
        full_model_file_path = self.get_s3_file_path(hf_file_path)
        if self.s3_file_exists(full_model_file_path):
            self.logging_for_class(f"Model file {full_model_file_path} already exists.")
            return

        self.logging_for_class(f"Downloading huggingface model from {hf_file_path}")
        completed_upload_id = None
        file_info = self.get_file_info(hf_file_path)
        total_size = file_info["size"]
        sha256 = file_info["lfs"]["sha256"] if "lfs" in file_info else None
        try:
            with self.fs.open(hf_file_path, "rb") as hf_file:
                upload_id, sha256_value = self.upload_fs_to_s3(
                    hf_file, total_size, full_model_file_path
                )
                if sha256 is not None and sha256 != sha256_value:
                    self.delete_s3_file(full_model_file_path)
                    raise Exception(
                        f"SHA256 hash of the downloaded file does not match the expected value. {full_model_file_path}"
                    )
                completed_upload_id = upload_id
        except Exception as e:
            self.logging_for_class(f"An error occurred, download: {str(e)}", "error")
            raise e
        finally:
            # If an error occurred and upload was not completed
            if completed_upload_id is None:
                self.s3.abort_multipart_upload(
                    Bucket=self.s3_bucket, Key=full_model_file_path, UploadId=upload_id
                )
            else:
                self.save_manifest_yml()
                self.logging_for_class(
                    f"Model file {full_model_file_path} uploaded successfully."
                )

    def save_manifest_yml(self) -> None:
        """
        Saves the manifest YAML file for the model.

        This method creates a `Manifest` object with the specified parameters and converts it to YAML format.
        The resulting YAML is then saved to an S3 bucket with the file path "{repo_id}/manifest.yml".

        Returns:
            None

        Raises:
            None
        """
        manifest = Manifest(
            repo_id=self.repo_id,
            files=self.files,
            inference_devices=self.inference_devices,
            quantization=self.quantization,
            runtime=self.runtime,
            prompt_template=self.prompt_template,
        )
        manifest_yaml = to_yaml(manifest.model_dump(exclude_none=True))
        file_path = self.get_s3_file_path(f"{self.repo_id}/manifest.yml")
        self.s3.Object(self.s3_bucket, file_path).put(Body=manifest_yaml)
        self.logging_for_class(f"Manifest file saved to {file_path}")

    def upload_files(self) -> None:
        """
        Upload multiple files from Hugging Face to S3 in parallel.
        Returns:
            None
        """
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.download_max_concurrency
        ) as executor:
            executor.map(self.upload_file_to_s3, self.files)

    def logging_for_class(self, message: str, type: str = "info") -> None:
        """
        Logs an informational message.

        Args:
            message (str): The message to log.

        Returns:
            None
        """
        if type == "info":
            logger.info(f"HuggingFaceModel ({self.repo_id}): {message}")
        elif type == "warn":
            logger.warn(f"HuggingFaceModel ({self.repo_id}): {message}")
        elif type == "error":
            logger.error(f"HuggingFaceModel ({self.repo_id}): {message}")
        else:
            logger.info(f"HuggingFaceModel ({self.repo_id}): {message}")
