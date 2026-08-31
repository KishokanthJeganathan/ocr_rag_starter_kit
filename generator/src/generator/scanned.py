"""Turn a clean PDF into a degraded, image-only PDF — no text layer, so the
pipeline is forced down the OCR path instead of reading embedded text.
"""

from __future__ import annotations

import io
import random
from pathlib import Path

import pymupdf
from PIL import Image, ImageEnhance, ImageFilter

_RENDER_DPI = 150


def _degrade(img: Image.Image, rng: random.Random) -> Image.Image:
    rgb = img.convert("RGB")

    # Slight skew, as if the page went through a scanner crooked.
    angle = rng.uniform(-1.6, 1.6)
    rgb = rgb.rotate(
        angle, expand=False, resample=Image.Resampling.BICUBIC, fillcolor=(255, 255, 255)
    )

    # Photocopier greyscale.
    rgb = rgb.convert("L").convert("RGB")

    # Sensor noise.
    sigma = rng.uniform(10, 22)
    noise = Image.effect_noise(rgb.size, sigma).convert("RGB")
    rgb = Image.blend(rgb, noise, alpha=0.10)

    # Soft focus + contrast/brightness drift.
    rgb = rgb.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.3, 0.9)))
    rgb = ImageEnhance.Contrast(rgb).enhance(rng.uniform(0.88, 1.12))
    rgb = ImageEnhance.Brightness(rgb).enhance(rng.uniform(0.92, 1.06))
    return rgb


def make_scanned_pdf(clean_pdf: Path, out_pdf: Path, *, seed: int) -> None:
    rng = random.Random(seed)
    src = pymupdf.open(clean_pdf)
    dst = pymupdf.open()
    try:
        for page in src:
            pix = page.get_pixmap(dpi=_RENDER_DPI)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            img = _degrade(img, rng)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=rng.randint(45, 70))

            new_page = dst.new_page(width=pix.width, height=pix.height)
            new_page.insert_image(pymupdf.Rect(0, 0, pix.width, pix.height), stream=buf.getvalue())

        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        dst.set_metadata({})
        dst.save(out_pdf, garbage=4, deflate=True)
    finally:
        dst.close()
        src.close()
