"""CLI entry point: ``python -m generator make ...``"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from generator.build import build_document
from generator.violations import VALID_VIOLATIONS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m generator",
        description="Synthetic document generator (fixture factory).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    make = sub.add_parser("make", help="Generate one or more documents.")
    make.add_argument("--type", choices=["nda"], default="nda")
    make.add_argument("--count", type=int, default=1, help="How many to generate.")
    make.add_argument(
        "--kind",
        choices=["one-way", "mutual", "random"],
        default="random",
        help="NDA direction.",
    )
    make.add_argument(
        "--violation",
        action="append",
        default=[],
        choices=sorted(VALID_VIOLATIONS),
        metavar="NAME",
        help="Inject a defect (repeatable). One of: " + ", ".join(sorted(VALID_VIOLATIONS)),
    )
    make.add_argument(
        "--scanned",
        action="store_true",
        help="Emit a degraded, image-only PDF (no text layer).",
    )
    make.add_argument("--seed", type=int, default=0, help="Base seed.")
    make.add_argument("--out", type=Path, default=Path("fixtures"))
    make.add_argument("--prefix", default=None, help="doc_id prefix (default: the --type value).")
    return parser


def _cmd_make(args: argparse.Namespace) -> int:
    prefix = args.prefix or args.type
    for offset in range(args.count):
        seed = args.seed + offset
        doc_id = f"{prefix}_{seed:05d}"
        result = build_document(
            doc_id=doc_id,
            seed=seed,
            kind=args.kind,
            violations=tuple(args.violation),
            scanned=args.scanned,
            out_dir=args.out,
        )
        print(f"  {result.pdf_path}  [{result.render_mode}]  + {result.ground_truth_path.name}")
    print(f"generated {args.count} document(s) into {args.out}/")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "make":
        return _cmd_make(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
