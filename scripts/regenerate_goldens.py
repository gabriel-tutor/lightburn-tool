"""Regenerate golden .lbrn2 fixtures used by build_lbrn2 tests.

Run from repo root:
    uv run python scripts/regenerate_goldens.py

Each entry below maps an input (template + shapes) → output filename.
Adding a new golden = add an entry, run the script, eyeball the diff,
commit the result.

Goldens guard against schema drift: if a future change to lxml output,
the .lbrn2 schema, or our builder logic alters the bytes, the affected
golden test fails loudly. Regenerate only after deliberate review.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lbb.core.template_builder import build_lbrn2

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "templates"
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"


@dataclass(frozen=True, slots=True)
class GoldenCase:
    name: str
    template: str
    shapes: tuple[tuple[str, int], ...]


CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        name="wallet-small-rect.lbrn2",
        template="wallet-small.lbrn2",
        shapes=(("M 10 10 L 60 10 L 60 50 L 10 50 Z", 0),),
    ),
)


def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        out = build_lbrn2(
            template_path=TEMPLATE_DIR / case.template,
            shapes=list(case.shapes),
        )
        target = GOLDEN_DIR / case.name
        target.write_bytes(out)
        print(f"  ✓ {target.relative_to(REPO_ROOT)} ({len(out)} bytes)")
    print(f"\nWrote {len(CASES)} golden(s) to {GOLDEN_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
