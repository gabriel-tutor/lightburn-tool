"""Dump text from a PDF (used to read large LightBurn-authored reference docs).

Usage:
    uv run python scripts/dump_pdf_text.py <pdf> [start_page] [end_page]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pypdfium2 as pdfium

# argv positions for the optional start/end page args.
_ARG_START = 2
_ARG_END = 3


def main() -> None:
    pdf_path = Path(sys.argv[1])
    start = int(sys.argv[_ARG_START]) - 1 if len(sys.argv) > _ARG_START else 0
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        end = int(sys.argv[_ARG_END]) if len(sys.argv) > _ARG_END else len(pdf)
        end = min(end, len(pdf))
        print(f"# {pdf_path} — pages {start + 1}..{end} of {len(pdf)}")
        for i in range(start, end):
            print(f"\n=== Page {i + 1} ===")
            text = pdf[i].get_textpage().get_text_bounded()
            print(text)
    finally:
        pdf.close()


if __name__ == "__main__":
    main()
