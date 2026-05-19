from io import BytesIO

import pytest
from PIL import Image

from lbb.core.models import Material, Sku, SkuProfile, Template
from lbb.core.preflight import PreflightResult
from lbb.ui.views.job_preview import JobPreviewView


@pytest.fixture
def tiny_png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (32, 32), "black").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def profile() -> SkuProfile:
    return SkuProfile(
        sku=Sku("LB-WALLET-LEATHER-S"),
        template=Template(
            id=1,
            name="Wallet — Small",
            lbrn2_path="/x.lbrn2",
            canvas_w_mm=95,
            canvas_h_mm=110,
        ),
        material=Material(
            id=1,
            name="Leather 2mm",
            clb_library="default.clb",
            clb_entry="LeatherVT",
            notes="",
        ),
        overrides={},
    )


def test_passing_preflight_enables_send_button(qtbot, tiny_png, profile):
    view = JobPreviewView()
    qtbot.addWidget(view)
    view.populate(
        thumbnail_png=tiny_png,
        profile=profile,
        preflight=PreflightResult(ok=True, reasons=[]),
    )
    assert view.send.isEnabled()
    assert "LB-WALLET-LEATHER-S" in view.sku_label.text()


def test_failing_preflight_disables_send_and_lists_reasons(qtbot, tiny_png, profile):
    view = JobPreviewView()
    qtbot.addWidget(view)
    reasons = [
        "PDF contains raster content (must be vector-only)",
        "stroke colors not in palette: #ABCDEF",
    ]
    view.populate(
        thumbnail_png=tiny_png,
        profile=profile,
        preflight=PreflightResult(ok=False, reasons=reasons),
    )
    assert not view.send.isEnabled()
    label_text = view.preflight_label.text()
    for r in reasons:
        assert r in label_text


def test_layer_setup_block_lists_cut_and_engrave_layer_instructions(qtbot, tiny_png, profile):
    """Direct-Open pivot: since LightBurn now imports the raw PDF, the operator
    must manually assign cut layers. The preview screen tells them which colors
    map to which layers (C00 cut, C01 engrave) so they don't have to remember."""
    view = JobPreviewView()
    qtbot.addWidget(view)
    view.populate(
        thumbnail_png=tiny_png,
        profile=profile,
        preflight=PreflightResult(ok=True, reasons=[]),
    )
    instructions = view.layer_setup_label.text()
    assert "C00" in instructions
    assert "C01" in instructions
    assert "Cut" in instructions or "cut" in instructions.lower()
    assert "Engrave" in instructions or "engrave" in instructions.lower()


def test_send_button_label_says_open_in_lightburn(qtbot):
    """Button language reflects the direct-open behavior — we're handing the
    PDF over to LightBurn, not generating a new file."""
    view = JobPreviewView()
    qtbot.addWidget(view)
    assert "Open in LightBurn" in view.send.text()


def test_cancel_button_emits_cancel_requested(qtbot, tiny_png, profile):
    view = JobPreviewView()
    qtbot.addWidget(view)
    view.populate(
        thumbnail_png=tiny_png,
        profile=profile,
        preflight=PreflightResult(ok=True, reasons=[]),
    )
    received: list[bool] = []
    view.cancel_requested.connect(lambda: received.append(True))
    view.cancel.click()
    assert received == [True]


def test_send_button_emits_send_requested_when_enabled(qtbot, tiny_png, profile):
    view = JobPreviewView()
    qtbot.addWidget(view)
    view.populate(
        thumbnail_png=tiny_png,
        profile=profile,
        preflight=PreflightResult(ok=True, reasons=[]),
    )
    received: list[bool] = []
    view.send_requested.connect(lambda: received.append(True))
    view.send.click()
    assert received == [True]
