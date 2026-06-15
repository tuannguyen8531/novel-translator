"""
Progress tracker for batch translation.

Provides a single-line progress display that updates in place.
"""

import sys
import time

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"


class ProgressTracker:
    """Single-line progress tracker for batch translation."""

    def __init__(self, total_chapters: int, novel_name: str):
        self.total_chapters = total_chapters
        self.novel_name = novel_name
        self.current_index = 0
        self.current_chapter = 0
        self.file_size = 0
        self.overall_start = time.time()
        self.success = 0
        self.failed = 0
        self._last_line = ""

    def start_chapter(self, index: int, chapter_num: int, file_size: int = 0):
        """Start tracking a new chapter."""
        self.current_index = index
        self.current_chapter = chapter_num
        self.file_size = file_size
        self._render()

    def chapter_done(self, success: bool):
        """Mark current chapter as done."""
        if success:
            self.success += 1
        else:
            self.failed += 1
        self._clear()

    def _render(self):
        """Render progress line."""
        overall = time.time() - self.overall_start
        pct = self.current_index / self.total_chapters * 100 if self.total_chapters else 0

        size_str = f"{self.file_size:,} chars" if self.file_size else ""
        line = (
            f"  {CYAN}[{self.current_index}/{self.total_chapters}]{RESET}"
            f" {pct:.0f}%"
            f" {DIM}· Ch.{self.current_chapter}{RESET}"
            f" {DIM}· {size_str}{RESET}"
            f" {DIM}· {overall:.0f}s total{RESET}"
        )

        if len(line) < len(self._last_line):
            line += " " * (len(self._last_line) - len(line))
        self._last_line = line

        sys.stdout.write(f"\r{line}")
        sys.stdout.flush()

    def _clear(self):
        """Clear the progress line."""
        sys.stdout.write("\r" + " " * len(self._last_line) + "\r")
        sys.stdout.flush()
        self._last_line = ""

    def print_summary(self):
        """Print final summary."""
        overall = time.time() - self.overall_start
        print()
        print(f"  {GREEN}{'═' * 54}")
        print(f"  ✅ {self.novel_name}: {self.success}/{self.total_chapters} translated")
        print(f"  {'═' * 54}{RESET}")
        if self.failed:
            print(f"  {RED}Failed: {self.failed}{RESET}")
        print(f"  {DIM}Total time: {overall:.0f}s{RESET}")
        print()
