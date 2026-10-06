"""Additional tests targeting uncovered branches for ≥80% coverage.

Focuses on exception paths and edge cases in images.py, compressor.py,
pdfio.py that the primary test modules don't exercise.
"""

from __future__ import annotations

import io
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pikepdf
import pytest
from PIL import Image

from pdfshrink.core.compressor import compress_one, _output_path
from pdfshrink.core.images import (
    ImageInfo,
    _downsample_image,
    extract_images,
    extract_pillow_image,
    recompress_image_data,
    apply_recompressed_images,
    should_process_image,
)
from pdfshrink.core.models import Job, Result, Settings
from pdfshrink.core.pdfio import (
    _deduplicate_images,
    _has_forms,
    _has_images,
    _has_signatures,
    _strip_metadata,
    _remove_thumbnails,
    open_pdf,
    validate_pdf,
)
from pdfshrink.errors import InvalidPDF, PasswordRequired

FIXTURES = Path(__file__).parent / "fixtures"


def _noop(frac: float) -> None:
    pass


def _make_blank_pdf() -> pikepdf.Pdf:
    """Create a blank single-page PDF without triggering pikepdf Page type checks."""
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    return pdf


# ── images.py coverage boost ─────────────────────────────────────────────

class TestImagesCoverageBranches:
    def test_extract_images_no_resources(self):
        """Page with no /Resources should not crash."""
        pdf = _make_blank_pdf()
        # Remove /Resources if present
        if "/Resources" in pdf.pages[0]:
            del pdf.pages[0]["/Resources"]
        images = extract_images(pdf)
        assert images == []
        pdf.close()

    def test_extract_images_no_xobjects(self):
        """Page with /Resources but no /XObject should return empty."""
        pdf = _make_blank_pdf()
        pdf.pages[0]["/Resources"] = pikepdf.Dictionary({})
        images = extract_images(pdf)
        assert images == []
        pdf.close()

    def test_recompress_palette_mode(self):
        """Palette mode (P) image should be converted to RGB."""
        img = Image.new("P", (200, 200))
        data = recompress_image_data(img, quality=75)
        result = Image.open(io.BytesIO(data))
        assert result.mode == "RGB"

    def test_recompress_la_mode(self):
        """LA mode (grayscale+alpha) should be composited onto white."""
        img = Image.new("LA", (200, 200), (128, 128))
        data = recompress_image_data(img, quality=75)
        result = Image.open(io.BytesIO(data))
        assert result.mode == "RGB"

    def test_downsample_zero_page_width(self):
        """Zero page width should return original image."""
        img = Image.new("RGB", (500, 500))
        result = _downsample_image(img, target_dpi=72, page_width_pt=0.0)
        assert result.width == 500
        assert result.height == 500

    def test_extract_pillow_image_returns_none_on_bad_xobj(self):
        """Non-image XObject should return None gracefully."""
        pdf = pikepdf.new()
        # Create a stream that is NOT an image
        stream = pdf.make_stream(b"not an image")
        result = extract_pillow_image(stream)
        assert result is None
        pdf.close()


# ── compressor.py coverage boost ──────────────────────────────────────────

class TestCompressorCoverageBranches:
    @pytest.fixture
    def output_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "output"
        d.mkdir()
        return d

    @pytest.fixture
    def cancel(self) -> threading.Event:
        return threading.Event()

    def test_compress_one_password_exception_in_small_branch(
        self, output_dir: Path, cancel: threading.Event
    ):
        """Test PasswordRequired exception in the already-small branch."""
        src = FIXTURES / "encrypted.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        # Make original_bytes small enough to enter the "already within target" branch
        job = Job(src=src, original_bytes=1, password=None)
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)

        # But encrypted.pdf fails validate_pdf, so it gets skipped before the branch
        result = compress_one(job, settings, _noop, cancel)
        assert result.status == "skipped"

    def test_compress_one_with_form_pdf(
        self, output_dir: Path, cancel: threading.Event
    ):
        """Form PDF should compress normally (forms are preserved)."""
        src = FIXTURES / "with_form.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)
        result = compress_one(job, settings, _noop, cancel)

        assert result.status in ("ok", "below_min")

    def test_small_branch_password_required(
        self, output_dir: Path, cancel: threading.Event
    ):
        """PasswordRequired in already-small branch → skipped."""
        src = FIXTURES / "small.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        job = Job(src=src, original_bytes=1)  # Force into small branch
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)

        with patch(
            "pdfshrink.core.compressor.validate_pdf", return_value=True
        ), patch(
            "pdfshrink.core.compressor.find_best_params",
            side_effect=PasswordRequired("test"),
        ):
            result = compress_one(job, settings, _noop, cancel)
        assert result.status == "skipped"
        assert "sandi" in result.message

    def test_small_branch_invalid_pdf(
        self, output_dir: Path, cancel: threading.Event
    ):
        """InvalidPDF in already-small branch → skipped."""
        src = FIXTURES / "small.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        job = Job(src=src, original_bytes=1)
        settings = Settings(min_kb=0, max_kb=500, output_dir=output_dir)

        with patch(
            "pdfshrink.core.compressor.validate_pdf", return_value=True
        ), patch(
            "pdfshrink.core.compressor.find_best_params",
            side_effect=InvalidPDF("test"),
        ):
            result = compress_one(job, settings, _noop, cancel)
        assert result.status == "skipped"
        assert "tidak valid" in result.message

    def test_main_flow_password_required(
        self, output_dir: Path, cancel: threading.Event
    ):
        """PasswordRequired in main flow → skipped."""
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=50, output_dir=output_dir)

        with patch(
            "pdfshrink.core.compressor.validate_pdf", return_value=True
        ), patch(
            "pdfshrink.core.compressor.find_best_params",
            side_effect=PasswordRequired("test"),
        ):
            result = compress_one(job, settings, _noop, cancel)
        assert result.status == "skipped"

    def test_main_flow_generic_exception(
        self, output_dir: Path, cancel: threading.Event
    ):
        """Generic exception in main flow → skipped with error."""
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        job = Job(src=src, original_bytes=src.stat().st_size)
        settings = Settings(min_kb=0, max_kb=50, output_dir=output_dir)

        with patch(
            "pdfshrink.core.compressor.validate_pdf", return_value=True
        ), patch(
            "pdfshrink.core.compressor.find_best_params",
            side_effect=RuntimeError("disk full"),
        ):
            result = compress_one(job, settings, _noop, cancel)
        assert result.status == "skipped"
        assert "error" in result.message


# ── pdfio.py coverage boost ──────────────────────────────────────────────

class TestPdfioCoverageBranches:
    def test_strip_metadata_empty_docinfo(self, tmp_path: Path):
        """Strip metadata on PDF with empty docinfo should not crash."""
        pdf = _make_blank_pdf()
        _strip_metadata(pdf)
        out = tmp_path / "stripped.pdf"
        pdf.save(out)
        pdf.close()
        assert out.exists()

    def test_remove_thumbnails_no_thumb(self):
        """Pages without /Thumb should not crash."""
        pdf = _make_blank_pdf()
        _remove_thumbnails(pdf)
        pdf.close()

    def test_deduplicate_no_images(self):
        """Deduplication on PDF with no images should not crash."""
        pdf = _make_blank_pdf()
        _deduplicate_images(pdf)
        pdf.close()

    def test_has_forms_no_acroform(self):
        """PDF without /AcroForm should return False."""
        pdf = _make_blank_pdf()
        assert _has_forms(pdf) is False
        pdf.close()

    def test_has_signatures_no_acroform(self):
        """PDF without /AcroForm should return False for signatures."""
        pdf = _make_blank_pdf()
        assert _has_signatures(pdf) is False
        pdf.close()

    def test_has_images_no_images(self):
        """PDF with no XObjects should return False."""
        pdf = _make_blank_pdf()
        assert _has_images(pdf) is False
        pdf.close()

    def test_open_pdf_generic_exception(self, tmp_path: Path):
        """Non-PDF file should raise InvalidPDF."""
        fake = tmp_path / "fake.pdf"
        fake.write_bytes(b"this is not a pdf at all, random data here!!")
        with pytest.raises(InvalidPDF):
            open_pdf(fake)
