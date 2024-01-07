import os
from pathlib import Path
from typing import List, Optional
from zipfile import ZIP_DEFLATED, ZipFile

from pathspec import GitIgnoreSpec, PathSpec


def archive_directory(
    directory_path: str, archive_path: str, blacklist: Optional[List[str]] = None
) -> None:
    if blacklist is None:
        blacklist = []

    gitignore_path = Path(directory_path) / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, "r") as file:
            blacklist += file.readlines()

    blacklist_spec = GitIgnoreSpec.from_lines(blacklist)

    with ZipFile(f"{archive_path}.zip", "w", ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(directory_path):
            relative_root = os.path.relpath(root, directory_path)
            for f in files:
                relative_file_path = os.path.join(relative_root, f)
                if not blacklist_spec.match_file(relative_file_path):
                    full_file_path = os.path.join(root, f)
                    zipf.write(full_file_path, relative_file_path)
