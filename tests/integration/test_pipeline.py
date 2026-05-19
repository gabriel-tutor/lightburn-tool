from pathlib import Path

import pytest

from lbb.adapters.lightburn_fake import LightBurnFake
from lbb.adapters.pdfium_reader import PdfiumReader
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.app.job import Job
from lbb.app.pipeline import PipelineDeps, run_pipeline
from lbb.core.models import Material, Sku, SkuProfile, Template

REPO_ROOT = Path(__file__).parents[2]
PDF_DEMO = REPO_ROOT / "tests" / "fixtures" / "pdfs" / "LB-WALLET-LEATHER-S__demo.pdf"
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


def test_happy_path_opens_source_pdf_directly(deps):
    """After the direct-open pivot: pipeline hands the customer's PDF to
    LightBurn unchanged. LightBurn's native importer preserves fidelity."""
    profile = deps.repo.get(Sku("LB-WALLET-LEATHER-S"))
    result = run_pipeline(Job(source_pdf=PDF_DEMO, profile=profile), deps)
    assert result.ok, result.error
    # No .lbrn2 generated — source PDF is what was opened.
    assert result.output_path == PDF_DEMO
    assert result.sku.value == "LB-WALLET-LEATHER-S"
    assert deps.lightburn.loaded == [PDF_DEMO]


def test_lightburn_not_running_returns_error(tmp_path):
    """If LightBurn isn't running, the load_file call raises and the
    pipeline returns a non-ok result. Source PDF wasn't loaded."""
    repo = SqliteProfileRepository(tmp_path / "p.sqlite")
    profile = _seed_wallet_profile(repo)
    deps = PipelineDeps(
        repo=repo,
        pdf=PdfiumReader(),
        lightburn=LightBurnFake(running=False),  # simulate down
        temp_dir=tmp_path / "out",
    )
    result = run_pipeline(Job(source_pdf=PDF_DEMO, profile=profile), deps)
    assert not result.ok
    assert deps.lightburn.loaded == []


def test_pipeline_uses_explicit_profile_for_no_sku_filename(tmp_path):
    """When a profile is passed in the Job (the picker-fallback flow) the
    pipeline opens the customer's PDF directly. Filename can be anything."""
    repo = SqliteProfileRepository(tmp_path / "p.sqlite")
    profile = _seed_wallet_profile(repo)
    deps = PipelineDeps(
        repo=repo,
        pdf=PdfiumReader(),
        lightburn=LightBurnFake(),
        temp_dir=tmp_path / "out",
    )
    no_sku_pdf = tmp_path / "client-order-12345.pdf"
    no_sku_pdf.write_bytes(PDF_DEMO.read_bytes())

    result = run_pipeline(Job(source_pdf=no_sku_pdf, profile=profile), deps)
    assert result.ok, result.error
    assert result.profile is profile
    assert result.output_path == no_sku_pdf
    assert deps.lightburn.loaded == [no_sku_pdf]
