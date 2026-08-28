from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pymupdf
import pytest

from generator import violations
from generator.build import build_document
from generator.compose_nda import format_long_date


def _pdf_text(path: Path) -> str:
    """Extracted text with all runs of whitespace collapsed, so substring
    assertions don't depend on where lines happened to wrap."""
    doc = pymupdf.open(path)
    try:
        raw = "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()
    return " ".join(raw.split())


def test_make_clean_nda_writes_pdf_and_ground_truth(tmp_path: Path) -> None:
    result = build_document(doc_id="nda_t1", seed=1, kind="one-way", out_dir=tmp_path)

    assert result.pdf_path.exists()
    assert result.ground_truth_path.exists()
    assert result.render_mode == "clean"

    gt = json.loads(result.ground_truth_path.read_text())
    assert gt["doc_type"] == "nda"
    assert gt["render"] == {"mode": "clean", "seed": 1}
    assert gt["expected"]["agreement_type"] == "one_way"
    assert gt["injected_violations"] == []

    text = _pdf_text(result.pdf_path)
    assert gt["expected"]["disclosing_party"]["name"] in text
    assert gt["expected"]["receiving_party"]["name"] in text
    assert gt["expected"]["governing_law"] in text
    assert "NON-DISCLOSURE AGREEMENT" in text.upper()


def test_kind_controls_title(tmp_path: Path) -> None:
    mutual = build_document(doc_id="m", seed=2, kind="mutual", out_dir=tmp_path)
    one_way = build_document(doc_id="o", seed=2, kind="one-way", out_dir=tmp_path)

    assert "MUTUAL NON-DISCLOSURE AGREEMENT" in _pdf_text(mutual.pdf_path).upper()
    # "mutual covenants" boilerplate still appears, so compare on the full title.
    assert "MUTUAL NON-DISCLOSURE AGREEMENT" not in _pdf_text(one_way.pdf_path).upper()


def test_violation_date_order(tmp_path: Path) -> None:
    result = build_document(
        doc_id="v_date",
        seed=3,
        kind="one-way",
        violations=(violations.DATE_ORDER,),
        out_dir=tmp_path,
    )
    gt = json.loads(result.ground_truth_path.read_text())

    assert violations.DATE_ORDER in gt["injected_violations"]
    detail = gt["violation_details"][violations.DATE_ORDER]
    rendered = date.fromisoformat(detail["rendered_expiry_date"])
    effective = date.fromisoformat(gt["expected"]["effective_date"])

    assert rendered < effective
    assert format_long_date(rendered) in _pdf_text(result.pdf_path)


def test_violation_missing_party_sig(tmp_path: Path) -> None:
    result = build_document(
        doc_id="v_sig",
        seed=4,
        kind="one-way",
        violations=(violations.MISSING_PARTY_SIG,),
        out_dir=tmp_path,
    )
    gt = json.loads(result.ground_truth_path.read_text())
    text = _pdf_text(result.pdf_path)

    disclosing = gt["expected"]["disclosing_party"]["name"]
    receiving = gt["expected"]["receiving_party"]["name"]

    # Both parties still named in the body...
    assert disclosing in text
    assert receiving in text
    # ...but only one signature block is rendered.
    assert text.count("By: ") == 1
    assert (
        gt["violation_details"][violations.MISSING_PARTY_SIG]["party_missing_from_signatures"]
        == receiving
    )


def test_violation_missing_governing_law(tmp_path: Path) -> None:
    result = build_document(
        doc_id="v_law",
        seed=5,
        kind="mutual",
        violations=(violations.MISSING_GOVERNING_LAW,),
        out_dir=tmp_path,
    )
    gt = json.loads(result.ground_truth_path.read_text())

    assert gt["expected"]["governing_law"] is None
    assert "governed by the laws of the state" not in _pdf_text(result.pdf_path).lower()


def test_scanned_pdf_has_no_text_layer(tmp_path: Path) -> None:
    result = build_document(doc_id="scan_1", seed=6, kind="one-way", scanned=True, out_dir=tmp_path)
    gt = json.loads(result.ground_truth_path.read_text())
    assert gt["render"]["mode"] == "scanned"

    doc = pymupdf.open(result.pdf_path)
    try:
        assert doc.page_count >= 1
        extracted = "".join(page.get_text().strip() for page in doc)
    finally:
        doc.close()
    assert extracted == ""


def test_same_seed_is_deterministic(tmp_path: Path) -> None:
    a = build_document(doc_id="d", seed=7, out_dir=tmp_path / "a")
    b = build_document(doc_id="d", seed=7, out_dir=tmp_path / "b")
    assert a.ground_truth_path.read_text() == b.ground_truth_path.read_text()
    assert a.pdf_path.read_bytes() == b.pdf_path.read_bytes()


def test_unknown_violation_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown violation"):
        build_document(doc_id="bad", seed=8, violations=("not_a_real_one",), out_dir=tmp_path)
