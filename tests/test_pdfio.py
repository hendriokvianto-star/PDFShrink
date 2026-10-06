"""Tests for PDF I/O operations.

Covers open_pdf, save_pdf, validate_pdf, get_pdf_info,
lossless_rewrite, and internal helpers.
"""

from __future__ import annotations

from pathlib import Path

import pikepdf
import pytest

from pdfshrink.core.pdfio import (
    get_pdf_info,
    lossless_rewrite,
    open_pdf,
    save_pdf,
    validate_pdf,
)
from pdfshrink.errors import InvalidPDF, PasswordRequired

FIXTURES = Path(__file__).parent / "fixtures"


class TestOpenPdf:
    def test_open_valid_pdf(self):
        src = FIXTURES / "small.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")
        pdf = open_pdf(src)
        assert len(pdf.pages) > 0
        pdf.close()

    def test_open_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            open_pdf(Path("nonexistent.pdf"))

    def test_open_corrupt_raises_invalid(self):
        src = FIXTURES / "corrupt.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")
        with pytest.raises(InvalidPDF):
            open_pdf(src)

    def test_open_encrypted_without_password_raises(self):
        src = FIXTURES / "encrypted.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")
        with pytest.raises(PasswordRequired):
            open_pdf(src)

    def test_open_encrypted_with_password(self):
        src = FIXTURES / "encrypted.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")
        pdf = open_pdf(src, password="test123")
        assert len(pdf.pages) > 0
        pdf.close()


class TestSavePdf:
    def test_save_creates_file(self, tmp_path: Path):
        src = FIXTURES / "small.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        pdf = open_pdf(src)
        output = tmp_path / "saved.pdf"
        save_pdf(pdf, output)
        pdf.close()

        assert output.exists()
        assert output.stat().st_size > 0

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        src = FIXTURES / "small.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        pdf = open_pdf(src)
        output = tmp_path / "sub" / "dir" / "saved.pdf"
        save_pdf(pdf, output)
        pdf.close()

        assert output.exists()

    def test_save_without_compression(self, tmp_path: Path):
        src = FIXTURES / "small.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        pdf = open_pdf(src)
        output = tmp_path / "uncompressed.pdf"
        save_pdf(pdf, output, compress=False, linearize=False)
        pdf.close()

        assert output.exists()
        assert validate_pdf(output)


class TestValidatePdf:
    def test_valid_pdf(self):
        src = FIXTURES / "small.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")
        assert validate_pdf(src) is True

    def test_corrupt_pdf(self):
        src = FIXTURES / "corrupt.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")
        assert validate_pdf(src) is False

    def test_nonexistent_file(self):
        assert validate_pdf(Path("nonexistent.pdf")) is False

    def test_non_pdf_file(self, tmp_path: Path):
        fake = tmp_path / "fake.pdf"
        fake.write_text("This is not a PDF")
        assert validate_pdf(fake) is False


class TestGetPdfInfo:
    def test_scan_info(self):
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")
        info = get_pdf_info(src)
        assert info["page_count"] == 10
        assert info["has_images"] is True
        assert info["has_forms"] is False

    def test_text_only_info(self):
        src = FIXTURES / "text_only.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")
        info = get_pdf_info(src)
        assert info["page_count"] == 5
        assert info["has_images"] is False

    def test_form_info(self):
        src = FIXTURES / "with_form.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")
        info = get_pdf_info(src)
        assert info["has_forms"] is True

    def test_encrypted_with_password(self):
        src = FIXTURES / "encrypted.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")
        info = get_pdf_info(src, password="test123")
        assert info["page_count"] > 0


class TestLosslessRewrite:
    def test_rewrite_produces_valid_pdf(self, tmp_path: Path):
        src = FIXTURES / "scan_300dpi.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        dst = tmp_path / "rewritten.pdf"
        size = lossless_rewrite(src, dst)

        assert dst.exists()
        assert size > 0
        assert validate_pdf(dst)

    def test_rewrite_text_only(self, tmp_path: Path):
        src = FIXTURES / "text_only.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        dst = tmp_path / "text_rewritten.pdf"
        size = lossless_rewrite(src, dst)

        assert dst.exists()
        assert size > 0

    def test_rewrite_encrypted(self, tmp_path: Path):
        src = FIXTURES / "encrypted.pdf"
        if not src.exists():
            pytest.skip("Fixture not generated")

        dst = tmp_path / "enc_rewritten.pdf"
        size = lossless_rewrite(src, dst, password="test123")

        assert dst.exists()
        assert size > 0
