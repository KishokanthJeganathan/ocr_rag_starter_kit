"""Orchestrate one document: spec -> composed text -> PDF (optionally scanned)
-> ``.pdf`` + ``.gt.json`` on disk.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from generator.compose_nda import compose_nda
from generator.render_pdf import render_clean_pdf
from generator.sample import sample_nda_spec
from generator.scanned import make_scanned_pdf
from generator.violations import normalise


@dataclass(frozen=True)
class BuildResult:
    doc_id: str
    pdf_path: Path
    ground_truth_path: Path
    render_mode: str


def build_document(
    *,
    doc_id: str,
    seed: int,
    kind: str = "random",
    violations: tuple[str, ...] = (),
    scanned: bool = False,
    out_dir: Path,
) -> BuildResult:
    injected = normalise(violations)
    spec = sample_nda_spec(seed=seed, doc_id=doc_id, kind=kind, injected_violations=injected)
    composed = compose_nda(spec)

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{doc_id}.pdf"
    render_mode = "scanned" if scanned else "clean"

    if scanned:
        with tempfile.TemporaryDirectory() as tmp:
            clean_pdf = Path(tmp) / "clean.pdf"
            render_clean_pdf(composed, clean_pdf)
            make_scanned_pdf(clean_pdf, pdf_path, seed=seed)
    else:
        render_clean_pdf(composed, pdf_path)

    gt_path = out_dir / f"{doc_id}.gt.json"
    gt_path.write_text(
        json.dumps(spec.to_ground_truth(render_mode=render_mode, seed=seed), indent=2) + "\n"
    )

    return BuildResult(
        doc_id=doc_id,
        pdf_path=pdf_path,
        ground_truth_path=gt_path,
        render_mode=render_mode,
    )
