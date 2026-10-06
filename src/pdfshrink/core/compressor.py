"""Compression orchestrator — tiers 0 through 3.

Coordinates lossless rewrite, image recompression, downsampling,
and binary search over the quality/DPI ladder. This module contains
the public API: compress_one() and compress_batch().
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path

from pdfshrink.core.ladder import find_best_params
from pdfshrink.core.models import Job, Result, Settings
from pdfshrink.core.pdfio import get_pdf_info, validate_pdf
from pdfshrink.errors import InvalidPDF, PasswordRequired

logger = logging.getLogger(__name__)


def _output_path(src: Path, output_dir: Path) -> Path:
    """Generate a non-conflicting output file path.

    Pattern: {name}_compressed.pdf, then {name}_compressed (2).pdf, etc.
    Never overwrites the source file.

    Args:
        src: Source PDF path.
        output_dir: Directory for output files.

    Returns:
        A unique output file path.
    """
    stem = src.stem + "_compressed"
    ext = ".pdf"
    candidate = output_dir / (stem + ext)
    counter = 2
    while candidate.exists():
        candidate = output_dir / f"{stem} ({counter}){ext}"
        counter += 1
    return candidate


def compress_one(
    job: Job,
    settings: Settings,
    on_progress: Callable[[float], None],
    cancel: threading.Event,
) -> Result:
    """Compress a single PDF file.

    Orchestrates the tiered compression strategy:
    - Tier 0: Lossless rewrite
    - Tier 1-2: Image recompression with/without downsampling (via LADDER)
    - Tier 3: Failure — target unreachable

    Args:
        job: The compression job to execute.
        settings: Target size range and output directory.
        on_progress: Callback with progress fraction [0.0, 1.0].
        cancel: Event flag; set to request cancellation.

    Returns:
        Result with status and output path.
    """
    src = job.src
    max_bytes = settings.max_kb * 1024
    min_bytes = settings.min_kb * 1024
    _start_time = time.monotonic()

    logger.info(
        "Compress start: %s (%d KB) target=%d-%d KB",
        src.name, job.original_bytes // 1024,
        settings.min_kb, settings.max_kb,
    )

    on_progress(0.0)

    # --- Pre-checks ---
    # Validate PDF
    if not src.exists():
        return Result(
            job=job,
            status="skipped",
            output=None,
            final_bytes=None,
            attempts=0,
            message="✖ file tidak ditemukan",
        )

    if not validate_pdf(src):
        return Result(
            job=job,
            status="skipped",
            output=None,
            final_bytes=None,
            attempts=0,
            message="✖ file tidak valid",
        )

    # Check if source already within target
    if job.original_bytes <= max_bytes:
        # Still run Tier 0 — but if result is larger, copy source as-is
        on_progress(0.1)
        try:
            result = find_best_params(job, settings, cancel)
        except PasswordRequired:
            return Result(
                job=job, status="skipped", output=None,
                final_bytes=None, attempts=0,
                message="✖ terkunci sandi",
            )
        except InvalidPDF:
            return Result(
                job=job, status="skipped", output=None,
                final_bytes=None, attempts=0,
                message="✖ file tidak valid",
            )

        if cancel.is_set():
            return Result(
                job=job, status="skipped", output=None,
                final_bytes=None, attempts=0,
                message="✖ dibatalkan",
            )

        output = _output_path(src, settings.output_dir)
        settings.output_dir.mkdir(parents=True, exist_ok=True)

        if result is not None and result[2] <= job.original_bytes:
            # Tier 0/1/2 produced smaller file
            shutil.copy2(result[1], output)
            _cleanup_temp(result[1])
            final_bytes = result[2]
        else:
            # Copy source as-is (Tier 0 made it larger or no result)
            shutil.copy2(src, output)
            if result is not None:
                _cleanup_temp(result[1])
            final_bytes = job.original_bytes

        on_progress(1.0)
        final_kb = final_bytes // 1024
        orig_kb = job.original_bytes // 1024

        if final_bytes < min_bytes and settings.min_kb > 0:
            return _log_result(Result(
                job=job, status="below_min", output=output,
                final_bytes=final_bytes, attempts=1,
                message=f"✔ {final_kb} KB (di bawah minimum — sumber memang kecil)",
            ), _start_time)

        return _log_result(Result(
            job=job, status="ok", output=output,
            final_bytes=final_bytes, attempts=1,
            message=f"{orig_kb} KB → {final_kb} KB",
        ), _start_time)

    # --- Main compression flow ---
    on_progress(0.1)

    try:
        result = find_best_params(job, settings, cancel)
    except PasswordRequired:
        return Result(
            job=job, status="skipped", output=None,
            final_bytes=None, attempts=0,
            message="✖ terkunci sandi",
        )
    except InvalidPDF:
        return Result(
            job=job, status="skipped", output=None,
            final_bytes=None, attempts=0,
            message="✖ file tidak valid",
        )
    except Exception as e:
        logger.exception("Unexpected error compressing %s", src)
        return Result(
            job=job, status="skipped", output=None,
            final_bytes=None, attempts=0,
            message=f"✖ error: {e}",
        )

    if cancel.is_set():
        if result is not None:
            _cleanup_temp(result[1])
        return Result(
            job=job, status="skipped", output=None,
            final_bytes=None, attempts=0,
            message="✖ dibatalkan",
        )

    on_progress(0.8)

    # --- Tier 3: Failure ---
    if result is None:
        # Check if it's a text-only PDF
        try:
            info = get_pdf_info(src, job.password)
            if not info.get("has_images", True):
                return Result(
                    job=job, status="failed", output=None,
                    final_bytes=None, attempts=MAX_ATTEMPTS_USED,
                    message="✖ dokumen berbasis teks — sudah minimum",
                )
        except Exception:
            pass

        return _log_result(Result(
            job=job, status="failed", output=None,
            final_bytes=None, attempts=8,
            message=f"✖ tidak bisa mencapai target ({settings.max_kb} KB)",
        ), _start_time)

    # --- Success: pick best quality respecting min_kb ---
    _, temp_path, final_bytes = result
    final_kb = final_bytes // 1024
    orig_kb = job.original_bytes // 1024

    output = _output_path(src, settings.output_dir)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(temp_path, output)
    _cleanup_temp(temp_path)

    on_progress(1.0)

    # Check min_kb
    if final_bytes < min_bytes and settings.min_kb > 0:
        return _log_result(Result(
            job=job, status="below_min", output=output,
            final_bytes=final_bytes, attempts=result[0] if result[0] is not None else 1,
            message=f"✔ {final_kb} KB (di bawah minimum — sumber memang kecil)",
        ), _start_time)

    return _log_result(Result(
        job=job, status="ok", output=output,
        final_bytes=final_bytes,
        attempts=result[0] if result[0] is not None else 1,
        message=f"{orig_kb} KB → {final_kb} KB",
    ), _start_time)


# Sentinel for attempts count when tier 3 fails
MAX_ATTEMPTS_USED = 8


def _log_result(result: Result, start_time: float) -> Result:
    """Log compression result and return it unchanged.

    Logs: filename, status, final_bytes, duration.
    Never logs content — per SKILL spec.
    """
    duration = time.monotonic() - start_time
    final_kb = result.final_bytes // 1024 if result.final_bytes else "N/A"
    logger.info(
        "Compress done: %s status=%s final=%s KB duration=%.1fs",
        result.job.src.name, result.status, final_kb, duration,
    )
    return result


def compress_batch(
    jobs: list[Job],
    settings: Settings,
    on_file_done: Callable[[Result], None],
    on_progress: Callable[[int, int], None],
    cancel: threading.Event,
) -> list[Result]:
    """Compress a batch of PDF files.

    One file failing does NOT stop the batch. Each file is processed
    independently and errors are captured in the Result.

    Args:
        jobs: List of compression jobs.
        settings: Target size range and output directory.
        on_file_done: Callback invoked after each file completes.
        on_progress: Callback with (current_index, total) for overall progress.
        cancel: Event flag; set to request cancellation.

    Returns:
        List of Results, one per job.
    """
    results: list[Result] = []
    total = len(jobs)

    for idx, job in enumerate(jobs):
        if cancel.is_set():
            # Mark remaining as skipped
            for remaining_job in jobs[idx:]:
                r = Result(
                    job=remaining_job, status="skipped", output=None,
                    final_bytes=None, attempts=0,
                    message="✖ dibatalkan",
                )
                results.append(r)
                on_file_done(r)
            break

        on_progress(idx, total)

        try:
            r = compress_one(
                job, settings,
                on_progress=lambda frac: None,  # Per-file progress not forwarded in batch
                cancel=cancel,
            )
        except Exception as e:
            logger.exception("Unhandled error for %s", job.src)
            r = Result(
                job=job, status="skipped", output=None,
                final_bytes=None, attempts=0,
                message=f"✖ error: {e}",
            )

        results.append(r)
        on_file_done(r)

    on_progress(total, total)
    return results


def _cleanup_temp(path: Path) -> None:
    """Safely delete a temporary file."""
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
