from pathlib import Path

import pytest
from lxml import etree

from lbb.adapters.lightburn_fake import LightBurnFake
from lbb.adapters.pdfium_reader import PdfiumReader
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.app.job import Job
from lbb.app.pipeline import PipelineDeps, run_pipeline
from lbb.core.models import Material, Sku, SkuProfile, Template

REPO_ROOT = Path(__file__).parents[2]
PDF_DEMO = REPO_ROOT / "tests" / "fixtures" / "pdfs" / "LB-WALLET-LEATHER-S__demo.pdf"
PDF_SHOWCASE = REPO_ROOT / "tests" / "fixtures" / "pdfs" / "LB-WALLET-LEATHER-S__showcase.pdf"
TEMPLATE = REPO_ROOT / "templates" / "wallet-small.lbrn2"


def _seed_wallet_profile(repo: SqliteProfileRepository) -> SkuProfile:
    t = repo.upsert_template(
        Template(
            id=0,
            name="Wallet — Small",
            lbrn2_path=str(TEMPLATE),
            canvas_w_mm=95,
            canvas_h_mm=110,
        )
    )
    m = repo.upsert_material(
        Material(id=0, name="Leather 2mm", clb_library="default.clb", clb_entry="LeatherVT")
    )
    profile = SkuProfile(sku=Sku("LB-WALLET-LEATHER-S"), template=t, material=m, overrides={})
    repo.upsert(profile)
    return profile


@pytest.fixture
def deps(tmp_path):
    repo = SqliteProfileRepository(tmp_path / "p.sqlite")
    _seed_wallet_profile(repo)
    return PipelineDeps(
        repo=repo,
        pdf=PdfiumReader(),
        lightburn=LightBurnFake(),
        temp_dir=tmp_path / "out",
    )


def test_happy_path_loads_to_lightburn(deps):
    result = run_pipeline(Job(source_pdf=PDF_DEMO), deps)
    assert result.ok, result.error
    assert result.sku.value == "LB-WALLET-LEATHER-S"
    assert result.output_path.suffix == ".lbrn2"
    assert result.output_path.exists()
    assert deps.lightburn.loaded == [result.output_path]


def test_unknown_sku_returns_error(tmp_path):
    # Empty repo (no profile seeded)
    repo = SqliteProfileRepository(tmp_path / "p.sqlite")
    deps = PipelineDeps(
        repo=repo, pdf=PdfiumReader(), lightburn=LightBurnFake(), temp_dir=tmp_path / "out"
    )
    result = run_pipeline(Job(source_pdf=PDF_DEMO), deps)
    assert not result.ok
    assert "LB-WALLET-LEATHER-S" in result.error
    assert deps.lightburn.loaded == []  # never reached dispatch


def test_lightburn_not_running_returns_error(tmp_path):
    repo = SqliteProfileRepository(tmp_path / "p.sqlite")
    _seed_wallet_profile(repo)
    deps = PipelineDeps(
        repo=repo,
        pdf=PdfiumReader(),
        lightburn=LightBurnFake(running=False),  # simulate down
        temp_dir=tmp_path / "out",
    )
    result = run_pipeline(Job(source_pdf=PDF_DEMO), deps)
    assert not result.ok
    # File was built but not dispatched
    assert deps.lightburn.loaded == []


def test_strokes_route_to_correct_cut_layer(deps):
    """Black strokes → CutIndex 0 (cut), blue strokes → CutIndex 1 (engrave).
    The showcase PDF has both #000000 and #0000FF paths."""
    result = run_pipeline(Job(source_pdf=PDF_SHOWCASE), deps)
    assert result.ok, result.error
    tree = etree.parse(str(result.output_path))
    shapes = tree.findall(".//Shape[@Type='Path']")
    cut_indexes = [int(s.get("CutIndex")) for s in shapes]
    assert 0 in cut_indexes, f"no shape on layer 0 (cut); indexes: {set(cut_indexes)}"
    assert 1 in cut_indexes, f"no shape on layer 1 (engrave); indexes: {set(cut_indexes)}"


def test_filename_without_sku_returns_error(tmp_path):
    repo = SqliteProfileRepository(tmp_path / "p.sqlite")
    deps = PipelineDeps(
        repo=repo, pdf=PdfiumReader(), lightburn=LightBurnFake(), temp_dir=tmp_path / "out"
    )
    # Copy the demo PDF to a path with no SKU delimiter
    bad = tmp_path / "nosku.pdf"
    bad.write_bytes(PDF_DEMO.read_bytes())
    result = run_pipeline(Job(source_pdf=bad), deps)
    assert not result.ok
    assert "delimiter" in result.error.lower() or "sku" in result.error.lower()
