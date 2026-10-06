"""Tests for core data models.

Validates the Settings, Job, and Result dataclasses
defined in pdfshrink.core.models.
"""

from pathlib import Path

import pytest

from pdfshrink.core.models import Job, Result, Settings


class TestSettings:
    """Tests for the Settings dataclass."""

    def test_valid_settings(self) -> None:
        """Settings with valid min/max should instantiate without error."""
        s = Settings(min_kb=100, max_kb=500, output_dir=Path("./output"))
        assert s.min_kb == 100
        assert s.max_kb == 500
        assert s.output_dir == Path("./output")

    def test_default_min_zero(self) -> None:
        """min_kb=0 means no lower bound, should be valid."""
        s = Settings(min_kb=0, max_kb=500, output_dir=Path("."))
        assert s.min_kb == 0

    def test_max_must_be_positive(self) -> None:
        """max_kb=0 should raise ValueError."""
        with pytest.raises(ValueError, match="max_kb harus > 0"):
            Settings(min_kb=0, max_kb=0, output_dir=Path("."))

    def test_max_must_be_negative(self) -> None:
        """max_kb negative should raise ValueError."""
        with pytest.raises(ValueError, match="max_kb harus > 0"):
            Settings(min_kb=0, max_kb=-100, output_dir=Path("."))

    def test_max_must_exceed_min(self) -> None:
        """max_kb <= min_kb should raise ValueError."""
        with pytest.raises(ValueError, match="max_kb.*harus > min_kb"):
            Settings(min_kb=300, max_kb=300, output_dir=Path("."))

    def test_max_less_than_min(self) -> None:
        """max_kb < min_kb should raise ValueError."""
        with pytest.raises(ValueError, match="max_kb.*harus > min_kb"):
            Settings(min_kb=500, max_kb=100, output_dir=Path("."))

    def test_frozen(self) -> None:
        """Settings should be immutable (frozen dataclass)."""
        s = Settings(min_kb=0, max_kb=500, output_dir=Path("."))
        with pytest.raises(AttributeError):
            s.max_kb = 1000  # type: ignore[misc]


class TestJob:
    """Tests for the Job dataclass."""

    def test_job_creation(self) -> None:
        """Job should store source path and size."""
        j = Job(src=Path("test.pdf"), original_bytes=1024)
        assert j.src == Path("test.pdf")
        assert j.original_bytes == 1024
        assert j.password is None

    def test_job_with_password(self) -> None:
        """Job should accept optional password."""
        j = Job(src=Path("test.pdf"), original_bytes=2048, password="secret")
        assert j.password == "secret"


class TestResult:
    """Tests for the Result dataclass."""

    def test_ok_result(self) -> None:
        """OK result should have output path and final size."""
        job = Job(src=Path("test.pdf"), original_bytes=8000)
        r = Result(
            job=job,
            status="ok",
            output=Path("test_compressed.pdf"),
            final_bytes=3000,
            attempts=2,
            message="1.842 KB → 287 KB",
        )
        assert r.status == "ok"
        assert r.output is not None
        assert r.final_bytes == 3000
        assert r.attempts == 2

    def test_failed_result(self) -> None:
        """Failed result should have no output path."""
        job = Job(src=Path("test.pdf"), original_bytes=8000)
        r = Result(
            job=job,
            status="failed",
            output=None,
            final_bytes=None,
            attempts=8,
            message="Tidak bisa mencapai target",
        )
        assert r.status == "failed"
        assert r.output is None

    def test_skipped_result(self) -> None:
        """Skipped result for invalid/locked PDFs."""
        job = Job(src=Path("locked.pdf"), original_bytes=5000)
        r = Result(
            job=job,
            status="skipped",
            output=None,
            final_bytes=None,
            attempts=0,
            message="✖ terkunci sandi",
        )
        assert r.status == "skipped"
        assert r.attempts == 0

    def test_below_min_result(self) -> None:
        """Below-min result: compressed but under minimum."""
        job = Job(src=Path("small.pdf"), original_bytes=30000)
        r = Result(
            job=job,
            status="below_min",
            output=Path("small_compressed.pdf"),
            final_bytes=20000,
            attempts=1,
            message="✔ 20 KB (di bawah minimum — sumber memang kecil)",
        )
        assert r.status == "below_min"
        assert r.output is not None
