import concurrent.futures
from typing import Any

from huggingface_hub import HfFileSystem

from paka.kube_resources.model_group.models.abstract import Model
from paka.logger import logger


class HuggingFaceModel(Model):
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
                logger.warn(f"File {file} not found in repository {self.repo_id}")
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
            logger.info(f"Model file {full_model_file_path} already exists.")
            return

        logger.info(f"Downloading model from {hf_file_path}")
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
            logger.error(f"An error occurred, download: {str(e)}")
            raise e
        finally:
            # If an error occurred and upload was not completed
            if completed_upload_id is None:
                self.s3.abort_multipart_upload(
                    Bucket=self.s3_bucket, Key=full_model_file_path, UploadId=upload_id
                )

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
