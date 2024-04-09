from huggingface_hub import hf_hub_url, snapshot_download

from paka.kube_resources.model_group.models.abstract import Model
from paka.logger import logger


class HuggingFaceModel(Model):
    """
    A class representing a Hugging Face model.

    Args:
        name (str): The name of the model.
        files (list[tuple[str, str] | str], optional): A list of files to download for the model. Each file can be specified as a tuple containing the filename and its corresponding SHA256 hash, or as a string representing the filename. Defaults to None.

    Attributes:
        urls (list[str]): A list of URLs to download the files.
        sha256s (list[str]): A list of SHA256 hashes corresponding to the files.

    Methods:
        define_urls(files: list[tuple[str, str] | str]) -> None: Defines the URLs and SHA256 hashes for the files.
        download() -> None: Downloads the files.
        snapshot_download(destination: str) -> None: Downloads the model using the Hugging Face snapshot_download function.

    """

    def __init__(self, name: str, files: list[tuple[str, str] | str] = []):
        super().__init__(name)
        self.urls: list[str] = []
        self.sha256s: list[str | None] = []
        if len(files) > 0:
            self.define_urls(files)

    def define_urls(self, files: list[tuple[str, str] | str]) -> None:
        """
        Defines the URLs and SHA256 hashes for the files.

        Args:
            files (list[tuple[str, str] | str]): A list of files to download for the model. Each file can be specified as a tuple containing the filename and its corresponding SHA256 hash, or as a string representing the filename.

        Returns:
            None

        """
        for file in files:
            if isinstance(file, tuple):
                self.urls.append(hf_hub_url(repo_id=self.name, filename=file[0]))
                self.sha256s.append(file[1])
            elif file is not None and file != "":
                self.urls.append(hf_hub_url(repo_id=self.name, filename=file))
                self.sha256s.append(None)

    def save_to_s3(self) -> None:
        """
        Downloads the files.

        Returns:
            None

        """
        if len(self.urls) == 0:
            logger.info("No files to download.")
            return None
        self.download_all(self.urls, self.sha256s)

    def snapshot_download(self, destination: str) -> None:
        """
        Downloads the model using the Hugging Face snapshot_download function.

        Args:
            destination (str): The destination directory to save the downloaded model.

        Returns:
            None

        """
        # Implement the download logic for Hugging Face models here
        snapshot_download(self.name, library_name="transformers", cache_dir=destination)
        pass
