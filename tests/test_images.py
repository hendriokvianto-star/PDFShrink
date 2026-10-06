"""Tests for image extraction and recompression.

Covers skip rules, quality parameter effects, and
downsampling dimension correctness.
"""

from __future__ import annotations

import io
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from pdfshrink.core.images import (
    ImageInfo,
    MIN_PIXEL_AREA,
    _downsample_image,
    apply_recompressed_images,
    extract_images,
    extract_pillow_image,
    recompress_image_data,
    should_process_image,
)
from pdfshrink.core.pdfio import save_pdf

FIXTURES = Path(__file__).parent / "fixtures"


# ── Skip rules ────────────────────────────────────────────────────────────

class TestSkipRules:
    def test_skip_tiny_image(self):
        """Images with area < 10,000 pixels should be skipped."""
        info = ImageInfo(
            page_index=0, xobj_name="/Im0",
            width=50, height=50,  # 2500 < 10,000
            is_mask=False, has_smask=False,
            page_width_pt=612.0,
        )
        assert not should_process_image(info)

    def test_skip_image_mask(self):
        """1-bit image masks should be skipped."""
        info = ImageInfo(
            page_index=0, xobj_name="/Im0",
            width=1000, height=1000,
            is_mask=True, has_smask=False,
            page_width_pt=612.0,
        )
        assert not should_process_image(info)

    def test_skip_smask(self):
        """Images with /SMask (alpha) should be skipped."""
        info = ImageInfo(
            page_index=0, xobj_name="/Im0",
            width=1000, height=1000,
            is_mask=False, has_smask=True,
            page_width_pt=612.0,
        )
        assert not should_process_image(info)

    def test_process_normal_image(self):
        """Normal large image should be processed."""
        info = ImageInfo(
            page_index=0, xobj_name="/Im0",
            width=2000, height=3000,
            is_mask=False, has_smask=False,
            page_width_pt=612.0,
        )
        assert should_process_image(info)

    def test_process_boundary_area(self):
        """Image exactly at MIN_PIXEL_AREA should be processed."""
        # sqrt(10000) ~ 100, so 100x100 = 10000 is at boundary
        info = ImageInfo(
            page_index=0, xobj_name="/Im0",
            width=100, height=100,
            is_mask=False, has_smask=False,
            page_width_pt=612.0,
        )
        assert should_process_image(info)

    def test_skip_just_below_boundary(self):
        info = ImageInfo(
            page_index=0, xobj_name="/Im0",
            width=99, height=100,  # 9900 < 10,000
            is_mask=False, has_smask=False,
            page_width_pt=612.0,
        )
        assert not should_process_image(info)


# ── Quality parameter effects ─────────────────────────────────────────────

class TestQualityEffect:
    @pytest.fixture
    def test_image(self) -> Image.Image:
        """Create a test RGB image with some content."""
        img = Image.new("RGB", (500, 500), (128, 64, 32))
        # Add some variation
        pixels = img.load()
        for x in range(0, 500, 2):
            for y in range(0, 500, 2):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
        return img

    def test_higher_quality_larger_output(self, test_image: Image.Image):
        """Higher JPEG quality should produce larger output."""
        high_q = recompress_image_data(test_image, quality=95)
        low_q = recompress_image_data(test_image, quality=20)
        assert len(high_q) > len(low_q)

    def test_output_is_valid_jpeg(self, test_image: Image.Image):
        """Recompressed output should be a valid JPEG."""
        data = recompress_image_data(test_image, quality=75)
        img = Image.open(io.BytesIO(data))
        assert img.format == "JPEG"
        assert img.size == test_image.size

    def test_rgba_converted_to_rgb(self):
        """RGBA images should be composited onto white background."""
        img = Image.new("RGBA", (200, 200), (255, 0, 0, 128))
        data = recompress_image_data(img, quality=85)
        result = Image.open(io.BytesIO(data))
        assert result.mode == "RGB"

    def test_cmyk_converted(self):
        """CMYK images should be converted to RGB."""
        img = Image.new("CMYK", (200, 200), (0, 0, 0, 128))
        data = recompress_image_data(img, quality=85)
        result = Image.open(io.BytesIO(data))
        assert result.mode == "RGB"

    def test_grayscale_preserved(self):
        """Grayscale images should stay as 'L' mode."""
        img = Image.new("L", (200, 200), 128)
        data = recompress_image_data(img, quality=85)
        result = Image.open(io.BytesIO(data))
        assert result.mode == "L"


# ── Downsampling ──────────────────────────────────────────────────────────

class TestDownsampling:
    def test_downsample_reduces_dimensions(self):
        """Downsampling to lower DPI should reduce image dimensions."""
        img = Image.new("RGB", (2400, 3000))
        # A4 width = 595 pt ≈ 8.27 inches
        # 2400 pixels / 8.27 inches ≈ 290 DPI
        result = _downsample_image(img, target_dpi=72, page_width_pt=595.0)
        assert result.width < img.width
        assert result.height < img.height

    def test_no_downsample_if_below_target(self):
        """If current DPI is below target, image should not change."""
        img = Image.new("RGB", (400, 500))
        # 400 pixels / 8.27 inches ≈ 48 DPI (below 72)
        result = _downsample_image(img, target_dpi=72, page_width_pt=595.0)
        assert result.width == img.width
        assert result.height == img.height

    def test_downsample_correct_ratio(self):
        """Downsampled dimensions should match DPI ratio."""
        img = Image.new("RGB", (2400, 3000))
        page_width_pt = 595.0
        target_dpi = 150
        result = _downsample_image(img, target_dpi=target_dpi, page_width_pt=page_width_pt)

        page_width_inches = page_width_pt / 72.0
        current_dpi = 2400 / page_width_inches
        expected_scale = target_dpi / current_dpi
        expected_width = int(2400 * expected_scale)

        # Allow 1 pixel rounding tolerance
        assert abs(result.width - expected_width) <= 1

    def test_downsample_with_recompress(self):
        """Downsampling + recompression should produce smaller data."""
        img = Image.new("RGB", (2400, 3000), (100, 150, 200))
        no_ds = recompress_image_data(img, quality=75, target_dpi=None)
        with_ds = recompress_image_data(
            img, quality=75, target_dpi=72, page_width_pt=595.0
        )
        assert len(with_ds) < len(no_ds)


# ── extract_images from PDF ───────────────────────────────────────────────

class TestExtractImages:
    def test_scan_has_images(self):
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        pdf = pikepdf.open(str(src))
        images = extract_images(pdf)
        pdf.close()

        assert len(images) == 10  # 10 pages, 1 image each

    def test_text_only_has_no_images(self):
        src = FIXTURES / "text_only.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        pdf = pikepdf.open(str(src))
        images = extract_images(pdf)
        pdf.close()

        assert len(images) == 0

    def test_image_info_fields(self):
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        pdf = pikepdf.open(str(src))
        images = extract_images(pdf)
        pdf.close()

        info = images[0]
        assert info.page_index == 0
        assert info.width > 0
        assert info.height > 0
        assert not info.is_mask
        assert not info.has_smask
        assert info.page_width_pt > 0


# ── extract_pillow_image ──────────────────────────────────────────────────

class TestExtractPillowImage:
    def test_extract_from_scan(self):
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        pdf = pikepdf.open(str(src))
        page = pdf.pages[0]
        xobjects = page["/Resources"]["/XObject"]

        for name, xobj in xobjects.items():
            pil_img = extract_pillow_image(xobj)
            assert pil_img is not None, f"Failed to extract image {name}"
            assert pil_img.width > 0
            assert pil_img.height > 0
            break  # Just test first

        pdf.close()


# ── apply_recompressed_images ─────────────────────────────────────────────

class TestApplyRecompressedImages:
    def test_recompress_reduces_size(self, tmp_path: Path):
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        pdf = pikepdf.open(str(src))
        apply_recompressed_images(pdf, quality=40, target_dpi=72)
        output = tmp_path / "recompressed.pdf"
        save_pdf(pdf, output)
        pdf.close()

        assert output.stat().st_size < src.stat().st_size, (
            "Recompressed PDF should be smaller than source"
        )

    def test_text_only_unchanged(self, tmp_path: Path):
        """Applying recompression to text-only PDF should not error."""
        src = FIXTURES / "text_only.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        pdf = pikepdf.open(str(src))
        apply_recompressed_images(pdf, quality=75)
        output = tmp_path / "text_recomp.pdf"
        save_pdf(pdf, output)
        pdf.close()

        # Should produce a valid PDF
        assert output.exists()
        assert output.stat().st_size > 0
