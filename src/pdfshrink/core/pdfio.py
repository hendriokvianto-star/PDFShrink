"""PDF I/O operations using pikepdf.

Handles opening, saving, validating PDF files, and extracting
basic PDF metadata. This module is the sole interface to pikepdf.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pikepdf
from pikepdf import ObjectStreamMode, Pdf

from pdfshrink.errors import InvalidPDF, PasswordRequired

logger = logging.getLogger(__name__)


def open_pdf(path: Path, password: str | None = None) -> Pdf:
    """Open a PDF file with pikepdf.

    Args:
        path: Path to the PDF file.
        password: Optional password for encrypted PDFs.

    Returns:
        An opened pikepdf.Pdf object.

    Raises:
        InvalidPDF: If the file is not a valid PDF or is corrupt.
        PasswordRequired: If the PDF is encrypted and no/wrong password given.
        FileNotFoundError: If the file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    try:
        if password:
            return Pdf.open(path, password=password)
        return Pdf.open(path)
    except pikepdf.PasswordError:
        raise PasswordRequired(str(path))
    except pikepdf.PdfError as e:
        raise InvalidPDF(str(path), f"File tidak valid: {e}")
    except Exception as e:
        raise InvalidPDF(str(path), f"Gagal membuka file: {e}")


def save_pdf(
    pdf: Pdf,
    path: Path,
    compress: bool = True,
    linearize: bool = True,
) -> None:
    """Save a PDF with compression settings.

    Args:
        pdf: The pikepdf.Pdf object to save.
        path: Output file path.
        compress: Whether to compress streams.
        linearize: Whether to linearize for fast web view.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    save_kwargs: dict = {}
    if compress:
        save_kwargs["compress_streams"] = True
        save_kwargs["object_stream_mode"] = ObjectStreamMode.generate
    if linearize:
        save_kwargs["linearize"] = True

    pdf.save(path, **save_kwargs)
    logger.debug("Saved PDF to %s (%d bytes)", path, path.stat().st_size)


def validate_pdf(path: Path) -> bool:
    """Check if a file is a valid, openable PDF.

    Args:
        path: Path to check.

    Returns:
        True if valid PDF, False otherwise.
    """
    try:
        with Pdf.open(path) as _:
            return True
    except Exception:
        return False


def get_pdf_info(path: Path, password: str | None = None) -> dict:
    """Extract basic metadata from a PDF.

    Args:
        path: Path to the PDF file.
        password: Optional password for encrypted PDFs.

    Returns:
        Dict with keys: page_count, has_forms, has_signatures, has_images.
    """
    pdf = open_pdf(path, password)
    try:
        info: dict = {
            "page_count": len(pdf.pages),
            "has_forms": _has_forms(pdf),
            "has_signatures": _has_signatures(pdf),
            "has_images": _has_images(pdf),
        }
        return info
    finally:
        pdf.close()


def lossless_rewrite(src: Path, dst: Path, password: str | None = None) -> int:
    """Tier 0: Lossless rewrite of a PDF.

    Performs:
    - Stream compression
    - Object stream generation
    - Linearization
    - Metadata stripping (/Info optional fields)
    - Thumbnail removal
    - Image stream deduplication (SHA-256)

    Args:
        src: Source PDF path.
        dst: Destination PDF path.
        password: Optional password for encrypted PDFs.

    Returns:
        Size of the output file in bytes.
    """
    pdf = open_pdf(src, password)
    try:
        # Strip optional metadata
        _strip_metadata(pdf)

        # Remove thumbnails
        _remove_thumbnails(pdf)

        # Deduplicate identical image streams
        _deduplicate_images(pdf)

        # Save with maximum compression
        save_pdf(pdf, dst, compress=True, linearize=True)

        return dst.stat().st_size
    finally:
        pdf.close()


def _strip_metadata(pdf: Pdf) -> None:
    """Remove non-essential metadata from PDF."""
    # Remove /Info dictionary optional fields but keep required ones
    if hasattr(pdf, "docinfo") and pdf.docinfo is not None:
        try:
            # Keep nothing — clear all optional metadata
            keys_to_remove = []
            for key in pdf.docinfo.keys():
                keys_to_remove.append(key)
            for key in keys_to_remove:
                try:
                    del pdf.docinfo[key]
                except Exception:
                    pass
        except Exception:
            pass

    # Remove XMP metadata if present
    try:
        if "/Metadata" in pdf.Root:
            del pdf.Root["/Metadata"]
    except Exception:
        pass


def _remove_thumbnails(pdf: Pdf) -> None:
    """Remove page thumbnails to reduce size."""
    for page in pdf.pages:
        try:
            if "/Thumb" in page:
                del page["/Thumb"]
        except Exception:
            pass


def _deduplicate_images(pdf: Pdf) -> None:
    """Deduplicate identical image streams using SHA-256 hashing.

    Replaces duplicate XObject image references with a single shared object.
    """
    # Map SHA-256 hash -> first XObject reference
    seen_hashes: dict[str, pikepdf.Object] = {}
    replacements: list[tuple[pikepdf.Dictionary, str, pikepdf.Object]] = []

    for page in pdf.pages:
        resources = page.get("/Resources", {})
        xobjects = resources.get("/XObject", {})
        if not xobjects:
            continue

        for name, xobj_ref in xobjects.items():
            try:
                xobj = xobj_ref
                if not hasattr(xobj, "read_bytes"):
                    continue
                subtype = str(xobj.get("/Subtype", ""))
                if subtype != "/Image":
                    continue

                raw_data = xobj.read_bytes()
                h = hashlib.sha256(raw_data).hexdigest()

                if h in seen_hashes:
                    # Mark for replacement
                    replacements.append((xobjects, str(name), seen_hashes[h]))
                else:
                    seen_hashes[h] = xobj
            except Exception:
                continue

    # Apply replacements
    for xobjects_dict, name, replacement_obj in replacements:
        try:
            xobjects_dict[name] = replacement_obj
        except Exception:
            pass

    if replacements:
        logger.debug("Deduplicated %d image streams", len(replacements))


def _has_forms(pdf: Pdf) -> bool:
    """Check if PDF contains AcroForm fields."""
    try:
        return "/AcroForm" in pdf.Root
    except Exception:
        return False


def _has_signatures(pdf: Pdf) -> bool:
    """Check if PDF contains digital signatures."""
    try:
        if "/AcroForm" not in pdf.Root:
            return False
        acroform = pdf.Root["/AcroForm"]
        if "/SigFlags" in acroform:
            return True
        # Also check for signature fields
        fields = acroform.get("/Fields", [])
        for field in fields:
            try:
                ft = str(field.get("/FT", ""))
                if ft == "/Sig":
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False


def _has_images(pdf: Pdf) -> bool:
    """Check if any page contains image XObjects."""
    for page in pdf.pages:
        try:
            resources = page.get("/Resources", {})
            xobjects = resources.get("/XObject", {})
            for _, xobj in xobjects.items():
                try:
                    if str(xobj.get("/Subtype", "")) == "/Image":
                        return True
                except Exception:
                    continue
        except Exception:
            continue
    return False
