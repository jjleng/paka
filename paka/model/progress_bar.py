from __future__ import annotations

from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from tqdm import tqdm


class ProgressBar:
    def __init__(self, message: str = "Downloading") -> None:
        self.counter: Dict[str, int] = {}
        self.lock = Lock()
        self.progress_bar: Optional[tqdm] = None
        self.completed_files: List[Tuple[str, str]] = []
        self.message = message

    def __getattr__(self, name: str) -> Any:
        return getattr(self.progress_bar, name)

    def set_postfix_str(self, *args: Any, **kwargs: Any) -> None:
        if self.progress_bar is None:
            return
        self.progress_bar.set_postfix_str(*args, **kwargs)

    def clear_counter(self) -> None:
        with self.lock:
            self.counter = {}

    def create_progress_bar(self, total_size: int) -> None:
        with self.lock:
            if self.progress_bar is not None:
                return

            self.progress_bar = tqdm(
                total=total_size, unit="B", unit_scale=True, desc=self.message
            )

    def update_progress_bar(self, key: str, value: int) -> None:
        if key in self.counter:
            return

        with self.lock:
            if self.progress_bar is not None:
                # Increase the total count of the progress bar by the provided value
                self.progress_bar.total += value
                # Refresh the progress bar to reflect the new total
                self.progress_bar.refresh()

    def close_progress_bar(self) -> None:
        if self.progress_bar is None:
            return
        with self.lock:
            self.counter = {}
            self.progress_bar.close()
            self.progress_bar = None

    def advance_progress_bar(self, key: str = "", value: int = 0) -> None:
        if self.progress_bar is None:
            return
        with self.lock:
            if key:
                self.counter[key] = value
            # Calculate the total progress by summing the progress of all tasks
            total_progress = sum(self.counter.values())
            # Update the progress bar by the amount of progress made since the last update
            self.progress_bar.update(total_progress - self.progress_bar.n)
            self.progress_bar.refresh()


class NullProgressBar:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: None

    def __setattr__(self, name: str, value: Any) -> None:
        pass
