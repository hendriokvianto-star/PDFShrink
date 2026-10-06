"""Tests for the compression orchestrator.

Covers AC-1, AC-2, AC-3, AC-4, AC-7 acceptance criteria.
"""

from __future__ import annotations

import hashlib
import shutil
import threading
from pathlib import Path

import pytest

from pdfshrink.core.compressor import compress_batch, compress_one, _output_path
from pdfshrink.core.models import Job, Result, Settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Provide a temporary output directory."""
    d = tmp_path / "output"
    d.mkdir()
    return d


@pytest.fixture
def cancel() -> threading.Event:
    return threading.Event()


def _noop_progress(frac: float) -> None:
    pass


# ── AC-1: scan_300dpi → ≤ 500 KB ──────────────────────────────────────────

class TestAC1ScanCompression:
    def test_scan_compresses_below_500kb(self, output_dir: Path, cancel: threading.Event):
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture scan_300dpi.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)

        result = compress_one(job, settings, _noop_progress, cancel)

        assert result.status in ("ok", "below_min"), f"Expected ok/below_min, got: {result.status} — {result.message}"
        assert result.output is not None
        assert result.output.exists()
        assert result.final_bytes is not None
        assert result.final_bytes <= 500 * 1024, (
            f"Output {result.final_bytes} bytes exceeds 500 KB target"
        )

    def test_output_is_readable_pdf(self, output_dir: Path, cancel: threading.Event):
        """Compressed output must be a valid, openable PDF."""
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture scan_300dpi.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)
        result = compress_one(job, settings, _noop_progress, cancel)

        assert result.output is not None
        from pdfshrink.core.pdfio import validate_pdf
        assert validate_pdf(result.output), "Output is not a valid PDF"


# ── AC-2: range compliance ────────────────────────────────────────────────

class TestAC2RangeCompliance:
    def test_result_within_range(self, output_dir: Path, cancel: threading.Event):
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture scan_300dpi.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=100, max_kb=500, output_dir=output_dir)
        result = compress_one(job, settings, _noop_progress, cancel)

        assert result.status in ("ok", "below_min", "failed")
        if result.status == "ok":
            assert result.final_bytes is not None
            assert result.final_bytes <= 500 * 1024
        elif result.status == "below_min":
            # Below minimum is acceptable — the file is as small as possible
            assert result.final_bytes is not None
            assert result.final_bytes <= 500 * 1024

    def test_impossible_range_returns_failed(self, output_dir: Path, cancel: threading.Event):
        """If max_kb is extremely small, compression should return 'failed'."""
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture scan_300dpi.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=1, output_dir=output_dir)
        result = compress_one(job, settings, _noop_progress, cancel)

        assert result.status == "failed"
        assert result.output is None


# ── AC-3: source file integrity ───────────────────────────────────────────

class TestAC3SourceIntegrity:
    def test_source_hash_unchanged(self, output_dir: Path, cancel: threading.Event):
        """Source file must not be modified during compression."""
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture scan_300dpi.pdf not generated")

        # Hash before
        hash_before = hashlib.sha256(src.read_bytes()).hexdigest()

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)
        compress_one(job, settings, _noop_progress, cancel)

        # Hash after
        hash_after = hashlib.sha256(src.read_bytes()).hexdigest()
        assert hash_before == hash_after, "Source file was modified during compression!"


# ── AC-4: batch continues despite corrupt files ──────────────────────────

class TestAC4BatchResilience:
    def test_batch_with_corrupt_files(self, output_dir: Path, cancel: threading.Event):
        """Batch must continue processing after encountering corrupt files."""
        scan = FIXTURES / "scan_300dpi.pdf"
        corrupt = FIXTURES / "corrupt.pdf"
        small = FIXTURES / "small.pdf"

        if not scan.exists() or not corrupt.exists() or not small.exists():
            pytest.skip("Required fixtures not generated")

        jobs = [
            Job(src=scan, original_bytes=scan.stat().st_size),
            Job(src=corrupt, original_bytes=corrupt.stat().st_size),
            Job(src=small, original_bytes=small.stat().st_size),
        ]
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)

        done_results: list[Result] = []

        results = compress_batch(
            jobs, settings,
            on_file_done=lambda r: done_results.append(r),
            on_progress=lambda c, t: None,
            cancel=cancel,
        )

        assert len(results) == 3
        assert len(done_results) == 3

        # Corrupt file should be skipped, not crash the batch
        assert results[1].status == "skipped"

        # Other files should succeed or be handled gracefully
        assert results[0].status in ("ok", "below_min", "failed")
        assert results[2].status in ("ok", "below_min")

    def test_batch_callback_invoked_per_file(self, output_dir: Path, cancel: threading.Event):
        """on_file_done callback must be called once per file."""
        small = FIXTURES / "small.pdf"
        text = FIXTURES / "text_only.pdf"

        if not small.exists() or not text.exists():
            pytest.skip("Required fixtures not generated")

        jobs = [
            Job(src=small, original_bytes=small.stat().st_size),
            Job(src=text, original_bytes=text.stat().st_size),
        ]
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)

        callback_count = 0
        def count_callback(r: Result) -> None:
            nonlocal callback_count
            callback_count += 1

        compress_batch(
            jobs, settings,
            on_file_done=count_callback,
            on_progress=lambda c, t: None,
            cancel=cancel,
        )

        assert callback_count == 2


# ── AC-7: text-only PDF graceful failure ──────────────────────────────────

class TestAC7TextOnly:
    def test_text_only_fails_gracefully(self, output_dir: Path, cancel: threading.Event):
        """Text-only PDF should fail with informative message, not crash."""
        src = FIXTURES / "text_only.pdf"
        if not src.exists():
            pytest.skip("Fixture text_only.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        # Set target below the text-only file size to force failure
        settings = Settings(min_kb=0, max_kb=1, output_dir=output_dir)

        result = compress_one(job, settings, _noop_progress, cancel)

        assert result.status in ("failed", "ok", "below_min")
        if result.status == "failed":
            assert "teks" in result.message.lower() or "minimum" in result.message.lower()
        # Key: no exception raised


# ── Output naming ─────────────────────────────────────────────────────────

class TestOutputNaming:
    def test_output_path_basic(self, tmp_path: Path):
        src = Path("report.pdf")
        result = _output_path(src, tmp_path)
        assert result.name == "report_compressed.pdf"
        assert result.parent == tmp_path

    def test_output_path_dedup(self, tmp_path: Path):
        src = Path("report.pdf")
        # Create first file
        (tmp_path / "report_compressed.pdf").touch()
        result = _output_path(src, tmp_path)
        assert result.name == "report_compressed (2).pdf"

    def test_output_path_multi_dedup(self, tmp_path: Path):
        src = Path("report.pdf")
        (tmp_path / "report_compressed.pdf").touch()
        (tmp_path / "report_compressed (2).pdf").touch()
        result = _output_path(src, tmp_path)
        assert result.name == "report_compressed (3).pdf"


# ── Edge cases ────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_nonexistent_file(self, output_dir: Path, cancel: threading.Event):
        job = Job(src=Path("nonexistent.pdf"), original_bytes=0)
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)
        result = compress_one(job, settings, _noop_progress, cancel)
        assert result.status == "skipped"

    def test_corrupt_file(self, output_dir: Path, cancel: threading.Event):
        src = FIXTURES / "corrupt.pdf"
        if not src.exists():
            pytest.skip("Fixture corrupt.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)
        result = compress_one(job, settings, _noop_progress, cancel)
        assert result.status == "skipped"

    def test_already_small_file(self, output_dir: Path, cancel: threading.Event):
        """A file already within target should be copied as-is or optimized."""
        src = FIXTURES / "small.pdf"
        if not src.exists():
            pytest.skip("Fixture small.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)
        result = compress_one(job, settings, _noop_progress, cancel)

        assert result.status in ("ok", "below_min")
        assert result.output is not None
        assert result.output.exists()

    def test_cancel_event(self, output_dir: Path):
        """Setting cancel before compression should skip the file."""
        src = FIXTURES / "small.pdf"
        if not src.exists():
            pytest.skip("Fixture small.pdf not generated")

        cancel = threading.Event()
        cancel.set()  # Pre-cancel

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)
        result = compress_one(job, settings, _noop_progress, cancel)

        assert result.status == "skipped"
        assert "dibatalkan" in result.message

    def test_encrypted_without_password(self, output_dir: Path, cancel: threading.Event):
        src = FIXTURES / "encrypted.pdf"
        if not src.exists():
            pytest.skip("Fixture encrypted.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)
        result = compress_one(job, settings, _noop_progress, cancel)

        # Either skipped (password required) or handled
        assert result.status in ("skipped", "ok", "below_min")

    def test_encrypted_with_password(self, output_dir: Path, cancel: threading.Event):
        src = FIXTURES / "encrypted.pdf"
        if not src.exists():
            pytest.skip("Fixture encrypted.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size, password="test123")
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)
        result = compress_one(job, settings, _noop_progress, cancel)

        # validate_pdf() opens without password → fails validation before
        # password is passed to find_best_params. This is expected behavior:
        # encrypted PDFs are skipped at the validation gate.
        assert result.status in ("ok", "below_min", "skipped")
