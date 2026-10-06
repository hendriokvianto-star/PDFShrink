"""Quality/DPI ladder and binary search for optimal compression parameters.

Defines the LADDER constant and implements binary search to find
the highest-quality parameter set that achieves the target file size.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from pathlib import Path

import pikepdf

from pdfshrink.core.images import apply_recompressed_images
from pdfshrink.core.models import Job, Settings
from pdfshrink.core.pdfio import lossless_rewrite, open_pdf, save_pdf

logger = logging.getLogger(__name__)

# Quality/DPI ladder — ordered from highest quality to most aggressive.
# Each tuple: (jpeg_quality, target_dpi or None for no downsampling)
LADDER: list[tuple[int, int | None]] = [
    (95, None), (85, None), (75, None),
    (85, 200),  (75, 200),  (65, 200),
    (75, 150),  (65, 150),  (55, 150),
    (65, 120),  (55, 120),
    (55,  96),  (45,  96),
    (40,  72),
]

# Maximum number of render attempts per file (hard limit, PRD §6.2)
MAX_ATTEMPTS: int = 8


def _render_with_params(
    src: Path,
    quality: int,
    dpi: int | None,
    password: str | None = None,
) -> Path:
    """Render a PDF with given quality/DPI params to a temp file.

    Args:
        src: Source PDF path.
        quality: JPEG quality for image recompression.
        dpi: Target DPI for downsampling, or None.
        password: Optional PDF password.

    Returns:
        Path to the temporary rendered file.
    """
    temp_fd, temp_path_str = tempfile.mkstemp(suffix=".pdf", prefix="pdfshrink_")
    os.close(temp_fd)
    temp_path = Path(temp_path_str)

    try:
        pdf = open_pdf(src, password)
        try:
            apply_recompressed_images(pdf, quality=quality, target_dpi=dpi)
            save_pdf(pdf, temp_path, compress=True, linearize=True)
        finally:
            pdf.close()
    except Exception:
        # Clean up temp file on failure
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    return temp_path


def find_best_params(
    job: Job,
    settings: Settings,
    cancel: threading.Event,
) -> tuple[int | None, Path, int] | None:
    """Find the best compression parameters via binary search on LADDER.

    Tries Tier 0 (lossless) first. If that's insufficient, performs
    binary search over LADDER indices to find the highest-quality
    settings that achieve the target size.

    Args:
        job: Compression job with source path.
        settings: Target size range.
        cancel: Cancellation event.

    Returns:
        Tuple of (ladder_index_or_None, temp_file_path, file_size_bytes),
        or None if no parameter set achieves the target.
    """
    max_bytes = settings.max_kb * 1024
    temp_files: list[Path] = []
    best: tuple[int, Path, int] | None = None
    result_path: Path | None = None  # Track the path we're returning

    try:
        # Check cancel before any work
        if cancel.is_set():
            return None

        # --- Tier 0: Lossless rewrite ---
        tier0_fd, tier0_path_str = tempfile.mkstemp(
            suffix=".pdf", prefix="pdfshrink_t0_"
        )
        os.close(tier0_fd)
        tier0_path = Path(tier0_path_str)
        temp_files.append(tier0_path)

        tier0_size = lossless_rewrite(job.src, tier0_path, job.password)

        if tier0_size <= max_bytes:
            logger.info(
                "Tier 0 sufficient: %d bytes (target ≤ %d bytes)",
                tier0_size, max_bytes,
            )
            result_path = tier0_path
            return (None, tier0_path, tier0_size)

        if cancel.is_set():
            return None

        # --- Binary search on LADDER ---
        lo, hi = 0, len(LADDER) - 1
        attempts = 0

        while lo <= hi and attempts < MAX_ATTEMPTS:
            if cancel.is_set():
                return None

            mid = (lo + hi) // 2
            quality, dpi = LADDER[mid]

            logger.debug(
                "Attempt %d: LADDER[%d] quality=%d dpi=%s",
                attempts + 1, mid, quality, dpi,
            )

            temp_path = _render_with_params(
                job.src, quality, dpi, job.password
            )
            temp_files.append(temp_path)
            size = temp_path.stat().st_size
            attempts += 1

            logger.debug("  Result: %d bytes (target ≤ %d)", size, max_bytes)

            if size <= max_bytes:
                best = (mid, temp_path, size)
                hi = mid - 1  # Try higher quality (lower index)
            else:
                lo = mid + 1  # Need more compression (higher index)

        if best is not None:
            logger.info(
                "Best: LADDER[%d] → %d bytes in %d attempts",
                best[0], best[2], attempts,
            )
            result_path = best[1]

        return best

    finally:
        # Clean up temp files, EXCEPT the one we're returning
        for tf in temp_files:
            if tf == result_path:
                continue
            try:
                tf.unlink(missing_ok=True)
            except Exception:
                pass
