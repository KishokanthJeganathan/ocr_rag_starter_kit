"""A canned Textract ``analyze_document`` response and a fake client, so OCR
tests need no AWS. Patch it in with:

    monkeypatch.setattr("app.services.ocr._textract_client", lambda: FakeTextractClient())
"""

from __future__ import annotations

from typing import Any

LAYOUT_RESPONSE: dict[str, Any] = {
    "Blocks": [
        {
            "Id": "page",
            "BlockType": "PAGE",
            "Geometry": {"BoundingBox": {"Left": 0.0, "Top": 0.0, "Width": 1.0, "Height": 1.0}},
        },
        {
            "Id": "title",
            "BlockType": "LAYOUT_TITLE",
            "Confidence": 99.2,
            "Geometry": {"BoundingBox": {"Left": 0.1, "Top": 0.05, "Width": 0.8, "Height": 0.04}},
            "Relationships": [{"Type": "CHILD", "Ids": ["l1"]}],
        },
        {
            "Id": "body",
            "BlockType": "LAYOUT_TEXT",
            "Confidence": 97.5,
            "Geometry": {"BoundingBox": {"Left": 0.1, "Top": 0.15, "Width": 0.8, "Height": 0.25}},
            "Relationships": [{"Type": "CHILD", "Ids": ["l2", "l3"]}],
        },
        {"Id": "l1", "BlockType": "LINE", "Text": "NON-DISCLOSURE AGREEMENT"},
        {"Id": "l2", "BlockType": "LINE", "Text": "This Agreement is entered into"},
        {"Id": "l3", "BlockType": "LINE", "Text": "as of March 1, 2026."},
    ]
}


class FakeTextractClient:
    def analyze_document(self, **_: Any) -> dict[str, Any]:
        return LAYOUT_RESPONSE
