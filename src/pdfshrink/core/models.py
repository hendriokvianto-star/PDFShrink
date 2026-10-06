"""Data models for PDF Shrink.

Defines the core data contracts used between the GUI and
compression engine. These dataclasses are the sole interface
between the two layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Settings:
    """Compression settings provided by the user.

    Attributes:
        min_kb: Minimum target size in KB. Acts as a quality floor,
                NOT a padding target. Default 0 means no lower bound.
        max_kb: Maximum target size in KB. Must be > 0 and > min_kb.
        output_dir: Directory where compressed files are saved.
    """

    min_kb: int
    max_kb: int
    output_dir: Path

    def __post_init__(self) -> None:
        if self.max_kb <= 0:
            raise ValueError(f"max_kb harus > 0, dapat: {self.max_kb}")
        if self.max_kb <= self.min_kb:
            raise ValueError(
                f"max_kb ({self.max_kb}) harus > min_kb ({self.min_kb})"
            )


@dataclass
class Job:
    """A single PDF compression job.

    Attributes:
        src: Path to the source PDF file.
        original_bytes: Size of the source file in bytes.
        password: Optional password for encrypted PDFs.
    """

    src: Path
    original_bytes: int
    password: str | None = None


@dataclass
class Result:
    """Outcome of a single compression job.

    Attributes:
        job: The original job that was processed.
        status: One of:
            - "ok": Compressed successfully within [min_kb, max_kb].
            - "below_min": Compressed ≤ max_kb but < min_kb (source too small).
            - "failed": Could not reach max_kb target.
            - "skipped": Skipped due to error (corrupt, locked, etc.).
        output: Path to the compressed file, or None if failed/skipped.
        final_bytes: Size of the output file in bytes, or None.
        attempts: Number of compression attempts made.
        message: Human-readable status message for display in the file list.
    """

    job: Job
    status: Literal["ok", "below_min", "failed", "skipped"]
    output: Path | None
    final_bytes: int | None
    attempts: int
    message: str
