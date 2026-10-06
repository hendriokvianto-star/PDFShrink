"""Tests for the compression quality/DPI ladder and binary search.

Covers binary search correctness, max attempts enforcement,
and edge cases (already-small, text-only PDFs).
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest

from pdfshrink.core.ladder import (
    LADDER,
    MAX_ATTEMPTS,
    _render_with_params,
    find_best_params,
)
from pdfshrink.core.models import Job, Settings

FIXTURES = Path(__file__).parent / "fixtures"


class TestLadderConstant:
    def test_ladder_has_14_levels(self):
        assert len(LADDER) == 14

    def test_ladder_entries_are_tuples(self):
        for entry in LADDER:
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            quality, dpi = entry
            assert isinstance(quality, int)
            assert quality > 0
            assert dpi is None or isinstance(dpi, int)

    def test_ladder_quality_decreases_overall(self):
        """Broadly: first entries have higher quality than last."""
        first_q = LADDER[0][0]
        last_q = LADDER[-1][0]
        assert first_q > last_q

    def test_max_attempts_is_8(self):
        assert MAX_ATTEMPTS == 8

    def test_ladder_no_downsampling_entries(self):
        """First 3 entries should have no downsampling (dpi=None)."""
        for i in range(3):
            assert LADDER[i][1] is None


class TestRenderWithParams:
    def test_render_produces_file(self):
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture scan_300dpi.pdf not generated")

        temp_path = _render_with_params(src, quality=75, dpi=None)
        try:
            assert temp_path.exists()
            assert temp_path.stat().st_size > 0
        finally:
            temp_path.unlink(missing_ok=True)

    def test_lower_quality_produces_smaller_file(self):
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture scan_300dpi.pdf not generated")

        high_q = _render_with_params(src, quality=95, dpi=None)
        low_q = _render_with_params(src, quality=40, dpi=72)
        try:
            assert low_q.stat().st_size < high_q.stat().st_size, (
                "Lower quality should produce a smaller file"
            )
        finally:
            high_q.unlink(missing_ok=True)
            low_q.unlink(missing_ok=True)


class TestFindBestParams:
    @pytest.fixture
    def cancel(self) -> threading.Event:
        return threading.Event()

    def test_finds_params_for_scan(self, cancel: threading.Event, tmp_path: Path):
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture scan_300dpi.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=500, output_dir=tmp_path)

        result = find_best_params(job, settings, cancel)

        assert result is not None, "Should find params for scan PDF at 500 KB"
        ladder_idx, temp_path, size = result
        assert size <= 500 * 1024
        assert temp_path.exists()

        # Cleanup
        temp_path.unlink(missing_ok=True)

    def test_tier0_sufficient_for_small(self, cancel: threading.Event, tmp_path: Path):
        """Small PDF should pass at Tier 0 (lossless) without LADDER search."""
        src = FIXTURES / "small.pdf"
        if not src.exists():
            pytest.skip("Fixture small.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=500, output_dir=tmp_path)

        result = find_best_params(job, settings, cancel)

        assert result is not None
        ladder_idx, temp_path, size = result
        assert ladder_idx is None, "Small PDF should pass at Tier 0 (no LADDER index)"
        assert size <= 500 * 1024

        temp_path.unlink(missing_ok=True)

    def test_returns_none_for_impossible_target(self, cancel: threading.Event, tmp_path: Path):
        """Impossible target (1 KB for large scan) should return None."""
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture scan_300dpi.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=1, output_dir=tmp_path)

        result = find_best_params(job, settings, cancel)

        assert result is None, "Should return None for impossible target"

    def test_cancel_stops_search(self, tmp_path: Path):
        """Pre-cancelled event should stop the search early."""
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture scan_300dpi.pdf not generated")

        cancel = threading.Event()
        cancel.set()  # Pre-cancel

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=500, output_dir=tmp_path)

        result = find_best_params(job, settings, cancel)

        assert result is None, "Cancelled search should return None"

    def test_text_only_returns_none_for_tiny_target(
        self, cancel: threading.Event, tmp_path: Path
    ):
        """Text-only PDF can't be compressed below its natural size."""
        src = FIXTURES / "text_only.pdf"
        if not src.exists():
            pytest.skip("Fixture text_only.pdf not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        # Target below the text-only file size
        settings = Settings(min_kb=0, max_kb=1, output_dir=tmp_path)

        result = find_best_params(job, settings, cancel)

        # Either None (no images to compress, Tier 0 still too big)
        # or result with Tier 0 if file is already small enough
        # For a 6 KB text file targeting 1 KB: should be None
        assert result is None
