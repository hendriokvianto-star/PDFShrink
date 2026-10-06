"""Image extraction and recompression for PDF XObjects.

Handles extracting images from PDF pages, recompressing as JPEG
via Pillow, and downsampling to target DPI using LANCZOS resampling.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import pikepdf
from PIL import Image
from pikepdf import Pdf

logger = logging.getLogger(__name__)

# Minimum pixel area to process — skip tiny images
MIN_PIXEL_AREA = 10_000


@dataclass
class ImageInfo:
    """Metadata about a single image XObject in the PDF.

    Attributes:
        page_index: Zero-based page number.
        xobj_name: Name of the XObject in the page's Resources.
        width: Image width in pixels.
        height: Image height in pixels.
        is_mask: Whether this is an /ImageMask.
        has_smask: Whether the image has an /SMask (alpha channel).
        page_width_pt: Width of the containing page in points.
    """

    page_index: int
    xobj_name: str
    width: int
    height: int
    is_mask: bool
    has_smask: bool
    page_width_pt: float


def extract_images(pdf: Pdf) -> list[ImageInfo]:
    """Extract metadata for all image XObjects in the PDF.

    Args:
        pdf: An open pikepdf.Pdf object.

    Returns:
        List of ImageInfo for each image XObject found.
    """
    images: list[ImageInfo] = []

    for page_idx, page in enumerate(pdf.pages):
        try:
            page_width_pt = float(page.mediabox[2] - page.mediabox[0])
        except Exception:
            page_width_pt = 612.0  # Default US Letter width

        resources = page.get("/Resources", {})
        xobjects = resources.get("/XObject", {})
        if not xobjects:
            continue

        for name, xobj in xobjects.items():
            try:
                subtype = str(xobj.get("/Subtype", ""))
                if subtype != "/Image":
                    continue

                width = int(xobj.get("/Width", 0))
                height = int(xobj.get("/Height", 0))
                is_mask = bool(xobj.get("/ImageMask", False))
                has_smask = "/SMask" in xobj

                images.append(ImageInfo(
                    page_index=page_idx,
                    xobj_name=str(name),
                    width=width,
                    height=height,
                    is_mask=is_mask,
                    has_smask=has_smask,
                    page_width_pt=page_width_pt,
                ))
            except Exception as e:
                logger.debug("Skip XObject %s on page %d: %s", name, page_idx, e)
                continue

    return images


def should_process_image(info: ImageInfo) -> bool:
    """Determine if an image should be recompressed.

    Skip rules (PRD §6.1):
    - Area < 10,000 pixels
    - /ImageMask (1-bit masks)
    - Has /SMask (uncertain alpha — skip when in doubt)

    Args:
        info: Image metadata.

    Returns:
        True if the image should be processed, False to skip.
    """
    # Skip tiny images
    if info.width * info.height < MIN_PIXEL_AREA:
        return False

    # Skip 1-bit image masks
    if info.is_mask:
        return False

    # Skip images with alpha channel (SMask) — when in doubt, skip
    if info.has_smask:
        return False

    return True


def extract_pillow_image(xobj: pikepdf.Object) -> Image.Image | None:
    """Extract a pikepdf XObject image into a Pillow Image.

    Uses pikepdf.PdfImage as primary extraction method, which handles
    chained filters (e.g. ASCII85Decode+DCTDecode) correctly.
    Falls back to raw bytes extraction if PdfImage fails.

    Args:
        xobj: A pikepdf image XObject.

    Returns:
        Pillow Image, or None if extraction fails.
    """
    # Primary method: pikepdf.PdfImage (handles all filter chains)
    try:
        pdf_image = pikepdf.PdfImage(xobj)
        pil_img = pdf_image.as_pil_image()
        return pil_img
    except Exception as e:
        logger.debug("PdfImage extraction failed, trying fallback: %s", e)

    # Fallback: raw bytes extraction
    try:
        raw_data = xobj.read_bytes()
        pil_filter = str(xobj.get("/Filter", ""))

        # If already JPEG (DCTDecode), load directly
        if "/DCTDecode" in pil_filter:
            return Image.open(io.BytesIO(raw_data))

        width = int(xobj.get("/Width", 0))
        height = int(xobj.get("/Height", 0))
        color_space = str(xobj.get("/ColorSpace", "/DeviceRGB"))
        bpc = int(xobj.get("/BitsPerComponent", 8))

        if width == 0 or height == 0:
            return None

        # Determine mode
        if "/DeviceGray" in color_space or "/CalGray" in color_space:
            mode = "L"
        elif "/DeviceCMYK" in color_space:
            mode = "CMYK"
        else:
            mode = "RGB"

        try:
            img = Image.frombytes(mode, (width, height), raw_data)
            return img
        except Exception:
            try:
                return Image.open(io.BytesIO(raw_data))
            except Exception:
                return None

    except Exception as e:
        logger.debug("Failed to extract image: %s", e)
        return None


def recompress_image_data(
    img: Image.Image,
    quality: int,
    target_dpi: int | None = None,
    page_width_pt: float = 612.0,
) -> bytes:
    """Recompress a Pillow Image as JPEG.

    Optionally downsamples to target DPI using page-width proxy.

    Args:
        img: Source Pillow Image.
        quality: JPEG quality (1-95).
        target_dpi: Target DPI for downsampling, or None for no downsampling.
        page_width_pt: Page width in points, for DPI calculation proxy.

    Returns:
        JPEG-encoded bytes.
    """
    # Convert to RGB if needed (JPEG doesn't support alpha or CMYK well)
    if img.mode in ("RGBA", "LA", "PA"):
        # Composite onto white background
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode == "CMYK":
        img = img.convert("RGB")
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Downsample if target_dpi is specified
    if target_dpi is not None:
        img = _downsample_image(img, target_dpi, page_width_pt)

    # Encode as JPEG
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _downsample_image(
    img: Image.Image,
    target_dpi: int,
    page_width_pt: float,
) -> Image.Image:
    """Downsample image to target DPI using page-width proxy.

    DPI calculation (PRD §6.1 Tier 2):
    Approximate by assuming image spans full page width.
    LIMITATION: Does not account for full CTM. Images at partial
    page width may be downsampled more aggressively than intended.

    Args:
        img: Source image.
        target_dpi: Target resolution in DPI.
        page_width_pt: Page width in points.

    Returns:
        Downsampled image, or original if no downsampling needed.
    """
    page_width_inches = page_width_pt / 72.0
    if page_width_inches <= 0:
        return img

    current_dpi = img.width / page_width_inches

    if current_dpi <= target_dpi:
        return img  # Already at or below target

    scale = target_dpi / current_dpi
    new_width = max(1, int(img.width * scale))
    new_height = max(1, int(img.height * scale))

    logger.debug(
        "Downsample: %dx%d (%.0f DPI) → %dx%d (%d DPI)",
        img.width, img.height, current_dpi,
        new_width, new_height, target_dpi,
    )

    return img.resize((new_width, new_height), Image.LANCZOS)


def apply_recompressed_images(
    pdf: Pdf,
    quality: int,
    target_dpi: int | None = None,
) -> None:
    """Recompress all eligible images in a PDF in-place.

    Args:
        pdf: An open pikepdf.Pdf object (modified in place).
        quality: JPEG quality for recompression.
        target_dpi: Target DPI for downsampling, or None.
    """
    image_infos = extract_images(pdf)
    processed = 0

    for info in image_infos:
        if not should_process_image(info):
            continue

        try:
            page = pdf.pages[info.page_index]
            xobjects = page["/Resources"]["/XObject"]
            xobj = xobjects[info.xobj_name]

            # Extract to Pillow
            pil_img = extract_pillow_image(xobj)
            if pil_img is None:
                continue

            # Recompress
            jpeg_data = recompress_image_data(
                pil_img,
                quality=quality,
                target_dpi=target_dpi,
                page_width_pt=info.page_width_pt,
            )

            # Calculate new dimensions (may have changed due to downsampling)
            with Image.open(io.BytesIO(jpeg_data)) as check_img:
                new_width = check_img.width
                new_height = check_img.height

            # Replace XObject stream
            xobj.write(jpeg_data, filter=pikepdf.Name("/DCTDecode"))
            xobj["/Width"] = new_width
            xobj["/Height"] = new_height
            xobj["/ColorSpace"] = pikepdf.Name("/DeviceRGB")
            xobj["/BitsPerComponent"] = 8

            # Remove stale filters and decode params
            for key in ["/DecodeParms", "/SMask"]:
                if key in xobj:
                    del xobj[key]

            processed += 1

        except Exception as e:
            logger.debug(
                "Failed to recompress image %s on page %d: %s",
                info.xobj_name, info.page_index, e,
            )
            continue

    logger.debug("Recompressed %d of %d images", processed, len(image_infos))
