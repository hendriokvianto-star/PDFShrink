"""Generate PDF test fixtures programmatically using reportlab.

Creates test PDFs in tests/fixtures/ for use by the test suite.
Run: python tests/generate_fixtures.py
"""

from __future__ import annotations

import io
import os
import random
import sys
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def ensure_dir() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


def generate_scan_300dpi(path: Path) -> None:
    """Generate a 10-page scan-like PDF with large images (~8 MB target).

    Each page contains a full-page JPEG image at ~300 DPI,
    simulating a scanned document.
    """
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4  # 595.27 x 841.89 points

    for page_num in range(10):
        # Create a ~300 DPI image for A4 page
        # A4 is ~8.27 x 11.69 inches, so at 300 DPI:
        img_w = int(8.27 * 300)  # ~2481 pixels
        img_h = int(11.69 * 300)  # ~3507 pixels

        # Generate a realistic-looking image with text-like patterns
        img = Image.new("RGB", (img_w, img_h), (245, 245, 240))

        # Add some "content" — horizontal lines simulating text
        pixels = img.load()
        random.seed(42 + page_num)  # Reproducible
        for y in range(100, img_h - 100, 18):
            line_length = random.randint(img_w // 3, img_w - 200)
            for x in range(100, 100 + line_length):
                gray = random.randint(20, 60)
                pixels[x, y] = (gray, gray, gray)
                if y + 1 < img_h:
                    pixels[x, y + 1] = (gray, gray, gray)

        # Save as JPEG to temp buffer
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        buf.seek(0)

        # Draw image on page
        from reportlab.lib.utils import ImageReader
        c.drawImage(ImageReader(buf), 0, 0, width=width, height=height)
        c.showPage()

    c.save()
    print(f"  ✔ scan_300dpi.pdf: {path.stat().st_size / 1024:.0f} KB")


def generate_text_only(path: Path) -> None:
    """Generate a pure text PDF (~50 KB) with no images."""
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4

    lorem = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris "
        "nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in "
        "reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
        "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in "
        "culpa qui officia deserunt mollit anim id est laborum. "
    )

    for page_num in range(5):
        y = height - 72
        c.setFont("Helvetica", 11)
        for line_num in range(60):
            text = lorem[line_num % len(lorem):(line_num % len(lorem)) + 80]
            c.drawString(72, y, text)
            y -= 14
            if y < 72:
                break
        c.showPage()

    c.save()
    print(f"  ✔ text_only.pdf: {path.stat().st_size / 1024:.0f} KB")


def generate_with_form(path: Path) -> None:
    """Generate a PDF with AcroForm fields."""
    from reportlab.lib.colors import black
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 72, "Formulir Pendaftaran")

    c.setFont("Helvetica", 12)
    c.drawString(72, height - 120, "Nama:")
    c.acroForm.textfield(
        name="nama",
        x=72, y=height - 155,
        width=300, height=25,
        borderWidth=1,
        borderColor=black,
    )

    c.drawString(72, height - 190, "Email:")
    c.acroForm.textfield(
        name="email",
        x=72, y=height - 225,
        width=300, height=25,
        borderWidth=1,
        borderColor=black,
    )

    c.drawString(72, height - 260, "Setuju:")
    c.acroForm.checkbox(
        name="setuju",
        x=130, y=height - 270,
        size=20,
    )

    c.showPage()
    c.save()
    print(f"  ✔ with_form.pdf: {path.stat().st_size / 1024:.0f} KB")


def generate_encrypted(path: Path) -> None:
    """Generate a password-protected PDF.

    Password: test123
    """
    import pikepdf

    # First create a normal PDF
    temp_path = path.with_suffix(".tmp")
    c = canvas.Canvas(str(temp_path), pagesize=A4)
    c.setFont("Helvetica", 14)
    c.drawString(72, 700, "Dokumen Rahasia - Terkunci Sandi")
    c.drawString(72, 680, "Password: test123")
    c.showPage()
    c.save()

    # Encrypt with pikepdf
    pdf = pikepdf.open(temp_path)
    pdf.save(
        path,
        encryption=pikepdf.Encryption(
            owner="owner123",
            user="test123",
        ),
    )
    pdf.close()
    temp_path.unlink()
    print(f"  ✔ encrypted.pdf: {path.stat().st_size / 1024:.0f} KB (password: test123)")


def generate_corrupt(path: Path) -> None:
    """Generate a corrupt/truncated PDF file."""
    # Write a partial PDF header followed by garbage
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4\n")
        f.write(b"% This file is intentionally corrupt\n")
        f.write(b"1 0 obj\n<< /Type /Catalog >>\nendobj\n")
        # Truncate — no xref, no trailer
    print(f"  ✔ corrupt.pdf: {path.stat().st_size / 1024:.0f} KB (intentionally broken)")


def generate_small(path: Path) -> None:
    """Generate a very small PDF (~20 KB) that's already within typical targets."""
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(72, 700, "Dokumen kecil — sudah optimal.")
    c.showPage()
    c.save()
    print(f"  ✔ small.pdf: {path.stat().st_size / 1024:.0f} KB")


def main() -> None:
    print("Generating PDF test fixtures...")
    ensure_dir()

    generate_scan_300dpi(FIXTURES_DIR / "scan_300dpi.pdf")
    generate_text_only(FIXTURES_DIR / "text_only.pdf")
    generate_with_form(FIXTURES_DIR / "with_form.pdf")
    generate_encrypted(FIXTURES_DIR / "encrypted.pdf")
    generate_corrupt(FIXTURES_DIR / "corrupt.pdf")
    generate_small(FIXTURES_DIR / "small.pdf")

    print("\nDone! All fixtures saved to:", FIXTURES_DIR)


if __name__ == "__main__":
    main()
