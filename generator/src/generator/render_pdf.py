"""Render a :class:`ComposedNda` to a clean, text-layer PDF via fpdf2.

Core PDF fonts only (no font files, Latin-1 range) — output looks like a plain
word-processor export, which is fine and realistic for a fixture. Creation date
is pinned so identical input produces identical bytes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import Align, XPos, YPos

from generator.compose_nda import ComposedNda

_PINNED_DATE = datetime(2026, 1, 1, tzinfo=UTC)


def _latin1(text: str) -> str:
    """Core fonts are Latin-1 only; drop anything outside that range."""
    return text.encode("latin-1", "replace").decode("latin-1")


class _NdaPdf(FPDF):
    def footer(self) -> None:
        self.set_y(-40)
        self.set_font("Times", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()} of {{nb}}", align=Align.C)


def render_clean_pdf(doc: ComposedNda, path: Path) -> None:
    pdf = _NdaPdf(format="Letter", unit="pt")
    pdf.creation_date = _PINNED_DATE
    pdf.set_margins(72, 72, 72)
    pdf.set_auto_page_break(auto=True, margin=54)
    pdf.add_page()

    def para(
        text: str,
        *,
        style: str = "",
        size: int = 11,
        align: Align = Align.J,
        gap: float = 8,
    ) -> None:
        pdf.set_font("Times", style, size)
        pdf.multi_cell(0, 15, text=_latin1(text), align=align, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if gap:
            pdf.ln(gap)

    para(doc.title, style="B", size=15, align=Align.C, gap=18)

    for block in doc.frontmatter:
        para(block)

    for number, section in enumerate(doc.sections, start=1):
        para(f"{number}. {section.heading}", style="B", gap=3)
        para(section.body, gap=10)

    para(doc.closing, gap=24)

    for sig in doc.signatories:
        para(sig.party_name, style="B", gap=4)
        para("By: ______________________________", align=Align.L, gap=0)
        para(f"Name: {sig.name}", align=Align.L, gap=0)
        para(f"Title: {sig.title}", align=Align.L, gap=0)
        para("Date: ______________________________", align=Align.L, gap=20)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(pdf.output()))
