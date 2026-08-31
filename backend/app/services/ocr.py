"""OCR & layout via AWS Textract.

One path for every input: rasterize each page to a PNG (PyMuPDF), send the PNG to
Textract's ``analyze_document`` with the LAYOUT feature, and normalize the result
into ``OcrLayout``. The rasterized pages are also the page images the review UI
will show later.

Bounding boxes are normalized to 0..1 of the page (Textract already reports them
that way).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import boto3
import pymupdf

from app.config import settings

RASTER_DPI = 200


@dataclass(frozen=True)
class PageImage:
    png: bytes
    width: int
    height: int


@dataclass(frozen=True)
class OcrBlock:
    text: str
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1), 0..1
    confidence: float  # 0..1
    role: str  # "title", "section_header", "text", "footer", ...


@dataclass(frozen=True)
class OcrPage:
    number: int
    width: int
    height: int
    blocks: list[OcrBlock]


@dataclass(frozen=True)
class OcrLayout:
    engine: str
    pages: list[OcrPage]

    def to_dict(self, image_keys: dict[int, str] | None = None) -> dict[str, Any]:
        keys = image_keys or {}
        return {
            "engine": self.engine,
            "pages": [
                {
                    "number": page.number,
                    "width": page.width,
                    "height": page.height,
                    "image_key": keys.get(page.number),
                    "blocks": [
                        {
                            "text": block.text,
                            "bbox": list(block.bbox),
                            "confidence": block.confidence,
                            "role": block.role,
                        }
                        for block in page.blocks
                    ],
                }
                for page in self.pages
            ],
        }


def _textract_client() -> Any:
    return boto3.client(
        "textract",
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def rasterize(data: bytes, dpi: int = RASTER_DPI) -> list[PageImage]:
    """Render every page (PDF or image) to a PNG."""
    doc = pymupdf.open(stream=data)
    try:
        pages = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            pages.append(PageImage(png=pix.tobytes("png"), width=pix.width, height=pix.height))
        return pages
    finally:
        doc.close()


def analyze_pages(pages: list[PageImage]) -> OcrLayout:
    client = _textract_client()
    result = []
    for number, page in enumerate(pages, start=1):
        response = client.analyze_document(Document={"Bytes": page.png}, FeatureTypes=["LAYOUT"])
        result.append(
            OcrPage(
                number=number,
                width=page.width,
                height=page.height,
                blocks=_parse_blocks(response.get("Blocks", [])),
            )
        )
    return OcrLayout(engine="textract", pages=result)


def _parse_blocks(blocks: list[dict[str, Any]]) -> list[OcrBlock]:
    by_id = {b["Id"]: b for b in blocks}
    parsed = []
    for block in blocks:
        block_type = block.get("BlockType", "")
        if not block_type.startswith("LAYOUT_"):
            continue

        child_ids = [
            child_id
            for rel in block.get("Relationships", [])
            if rel.get("Type") == "CHILD"
            for child_id in rel.get("Ids", [])
        ]
        text = " ".join(
            by_id[cid]["Text"]
            for cid in child_ids
            if by_id.get(cid, {}).get("BlockType") == "LINE" and by_id[cid].get("Text")
        )

        box = block["Geometry"]["BoundingBox"]
        parsed.append(
            OcrBlock(
                text=text,
                bbox=(
                    box["Left"],
                    box["Top"],
                    box["Left"] + box["Width"],
                    box["Top"] + box["Height"],
                ),
                confidence=round(block.get("Confidence", 0.0) / 100, 4),
                role=block_type.removeprefix("LAYOUT_").lower(),
            )
        )
    return parsed
