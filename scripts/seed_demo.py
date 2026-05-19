"""Seed the default user database with demo SKU profile(s).

Run from repo root:
    uv run python scripts/seed_demo.py

This populates ~/.lightburn-bridge/profiles.sqlite — the same database that
`uv run python -m lbb` opens at launch. After seeding, drop a matching demo
PDF (printed at the end) onto the app to see the full flow.

Add more SKUs by extending the `SKUS` table below — schema is data-driven.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.core.models import Material, Sku, SkuProfile, Template

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "templates"
DEMO_PDFS_DIR = REPO_ROOT / "tests" / "fixtures" / "pdfs"

# Same default location as src/lbb/__main__.py.
DEFAULT_DB = Path.home() / ".lightburn-bridge" / "profiles.sqlite"


@dataclass(frozen=True, slots=True)
class _Material:
    name: str
    clb_library: str
    clb_entry: str


@dataclass(frozen=True, slots=True)
class _Template:
    name: str
    filename: str  # under templates/
    canvas_w_mm: float
    canvas_h_mm: float


@dataclass(frozen=True, slots=True)
class _Sku:
    code: str
    template_key: str
    material_key: str
    demo_pdf: str | None  # under tests/fixtures/pdfs/


MATERIALS: dict[str, _Material] = {
    "leather": _Material(
        name="Leather 2mm — Vegetable Tan",
        clb_library="default.clb",
        clb_entry="LeatherVT",
    ),
}

TEMPLATES: dict[str, _Template] = {
    "wallet-s": _Template(
        name="Wallet — Small",
        filename="wallet-small.lbrn2",
        canvas_w_mm=95.0,
        canvas_h_mm=110.0,
    ),
    "wallet-t": _Template(
        name="Wallet — Tall",
        filename="wallet-tall.lbrn2",
        canvas_w_mm=75.0,
        canvas_h_mm=125.0,
    ),
}

SKUS: tuple[_Sku, ...] = (
    _Sku(
        code="LB-WALLET-LEATHER-S",
        template_key="wallet-s",
        material_key="leather",
        demo_pdf="LB-WALLET-LEATHER-S__demo.pdf",
    ),
    # Real customer order PDFs — filename IS the SKU (no `__` delimiter).
    # The MainWindow's lenient lookup auto-flows these to preview on drop.
    _Sku(
        code="305-6737580-7658721",
        template_key="wallet-s",
        material_key="leather",
        demo_pdf=None,
    ),
    _Sku(
        code="304-4865183-6105121",
        template_key="wallet-t",
        material_key="leather",
        demo_pdf=None,
    ),
)


def main() -> None:
    DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)
    repo = SqliteProfileRepository(DEFAULT_DB)

    materials = {
        key: repo.upsert_material(
            Material(id=0, name=m.name, clb_library=m.clb_library, clb_entry=m.clb_entry)
        )
        for key, m in MATERIALS.items()
    }
    templates = {
        key: repo.upsert_template(
            Template(
                id=0,
                name=t.name,
                lbrn2_path=str(TEMPLATES_DIR / t.filename),
                canvas_w_mm=t.canvas_w_mm,
                canvas_h_mm=t.canvas_h_mm,
            )
        )
        for key, t in TEMPLATES.items()
    }

    for s in SKUS:
        repo.upsert(
            SkuProfile(
                sku=Sku(s.code),
                template=templates[s.template_key],
                material=materials[s.material_key],
                overrides={},
            )
        )
        tmpl_name = TEMPLATES[s.template_key].name
        mat_name = MATERIALS[s.material_key].name
        print(f"  ✓ {s.code}  →  {tmpl_name}  /  {mat_name}")

    print(f"\nSeeded {len(SKUS)} SKU profile(s) into {DEFAULT_DB}")
    print("\nDemo flow:")
    print("  1. uv run python -m lbb")
    for s in SKUS:
        if s.demo_pdf:
            print(f"  2. Drop {DEMO_PDFS_DIR / s.demo_pdf}")
    print("  3. Click Send → LightBurn loads the .lbrn2 (requires LightBurn running)")


if __name__ == "__main__":
    main()
