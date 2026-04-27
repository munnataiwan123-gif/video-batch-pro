"""Filesystem helpers and output-path management."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable


VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm",
    ".flv", ".m4v", ".mpg", ".mpeg", ".wmv", ".ts",
}


def is_video_file(path: str) -> bool:
    """Return True if `path` has a known video extension and exists on disk."""
    if not os.path.isfile(path):
        return False
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


def filter_video_paths(paths: Iterable[str]) -> list[str]:
    """Filter an iterable of paths down to files that look like videos."""
    return [p for p in paths if is_video_file(p)]


_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    """Replace any character not in [A-Za-z0-9._-] with `_`."""
    base = Path(name).name
    safe = _SANITIZE_RE.sub("_", base)
    return safe or "output"


def build_output_path(
    input_path: str,
    output_dir: str,
    suffix: str = "_processed",
    ext: str = ".mp4",
) -> str:
    """Return `<output_dir>/<sanitized stem><suffix><ext>`.

    Resolves collisions by appending `_1`, `_2`, ...
    """
    os.makedirs(output_dir, exist_ok=True)
    stem = sanitize_filename(Path(input_path).stem)
    candidate = os.path.join(output_dir, f"{stem}{suffix}{ext}")
    i = 1
    while os.path.exists(candidate):
        candidate = os.path.join(output_dir, f"{stem}{suffix}_{i}{ext}")
        i += 1
    return candidate


def ensure_dir(path: str) -> str:
    """mkdir -p and return the path."""
    os.makedirs(path, exist_ok=True)
    return path


def human_size(num_bytes: int) -> str:
    """Format a byte count as a human-readable string."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"
