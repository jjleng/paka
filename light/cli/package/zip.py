import os
from pathlib import Path
from typing import List, Optional
from zipfile import ZIP_DEFLATED, ZipFile

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern


def parse_gitignore(directory_path: str) -> PathSpec:
    gitignore_path = Path(directory_path) / ".gitignore"
    if not gitignore_path.exists():
        return PathSpec.from_lines(GitWildMatchPattern, [])
    with open(gitignore_path, "r") as file:
        return PathSpec.from_lines(GitWildMatchPattern, file)


def recursive_archive(
    directory_path: str, ignore_spec: PathSpec, zipf: ZipFile
) -> None:
    gitignore = parse_gitignore(directory_path)
    current_ignore_spec = ignore_spec + gitignore

    for entry in os.scandir(directory_path):
        if entry.is_file():
            if not current_ignore_spec.match_file(entry.path):
                zipf.write(entry.path, Path(entry.path).relative_to(directory_path))
        elif entry.is_dir():
            recursive_archive(entry.path, current_ignore_spec, zipf)


def archive_directory(
    directory_path: str, archive_path: str, blacklist: Optional[List[str]] = None
) -> None:
    if blacklist is None:
        blacklist = []

    # First pass: Check for .gitignore files
    use_gitignore = any(
        Path(root).joinpath(".gitignore").exists()
        for root, dirs, files in os.walk(directory_path)
    )

    if use_gitignore:
        blacklist = []

    with ZipFile(f"{archive_path}.zip", "w", ZIP_DEFLATED) as zipf:
        blacklist_spec = PathSpec.from_lines(GitWildMatchPattern, blacklist)
        recursive_archive(directory_path, blacklist_spec, zipf)
