# LightBurn Bridge — MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship a cross-platform PySide6 desktop app that accepts a PDF whose filename encodes an SKU, looks up the matching template + material profile, generates a configured `.lbrn2` file, and loads it into a running LightBurn instance via UDP — with operator confirmation before send. Operator still presses Start on the laser physically.

**Architecture:** Hexagonal (core / ports / adapters / app / ui). Pure-function pipeline. PySide6 desktop, SQLite local state, lxml for `.lbrn2` XML, pypdfium2 for PDF parsing, raw UDP socket to `127.0.0.1:19840`.

**Tech Stack:** Python 3.12 · uv · PySide6 · lxml · pypdfium2 · SQLite (stdlib) · pytest · pytest-qt · hypothesis · ruff · import-linter · PyInstaller

**Companion doc:** `docs/plans/2026-05-16-lightburn-bridge-design.md` (validated design — read first).

**Conventions:**
- Every task is TDD: write failing test → run-fail → implement → run-pass → commit.
- Commit after every passing test cluster. Small commits.
- Branch: `main` for trunk. Feature branches per phase: `phase-N/<topic>`.
- All paths absolute from repo root (`/Users/gabrieltutor/hauke/lightburn-tool/`).

---

## Phase 0 — Repo scaffold (one sitting, ~2 hours)

### Task 0.1: Initialize repo & tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.python-version`
- Create: `README.md`
- Create: `.editorconfig`

**Step 1:** Initialize uv project.
```bash
cd /Users/gabrieltutor/hauke/lightburn-tool
uv init --package --name lbb --python 3.12
```

**Step 2:** Edit `pyproject.toml` to declare dependencies:
```toml
[project]
name = "lbb"
version = "0.1.0"
description = "LightBurn Bridge — SKU-aware PDF loader for LightBurn"
requires-python = ">=3.12"
dependencies = [
  "PySide6>=6.7",
  "lxml>=5.2",
  "pypdfium2>=4.30",
]

[dependency-groups]
dev = [
  "pytest>=8.2",
  "pytest-qt>=4.4",
  "pytest-cov>=5.0",
  "hypothesis>=6.100",
  "ruff>=0.5",
  "import-linter>=2.0",
  "pre-commit>=3.7",
]

[project.scripts]
lbb = "lbb.__main__:main"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RET", "PL"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
markers = [
  "e2e: requires real LightBurn instance (skipped in CI by default)",
]
```

**Step 3:** Write `.gitignore`:
```
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
dist/
build/
*.egg-info/
.coverage
htmlcov/
profiles.sqlite
audit.log
.DS_Store
```

**Step 4:** Initialize git and install deps.
```bash
git init -b main
uv sync
git add -A
git commit -m "chore: project scaffold (uv, pyproject, gitignore)"
```

### Task 0.2: Architectural lint (import-linter)

**Files:**
- Create: `.importlinter`

**Step 1:** Write `.importlinter`:
```ini
[importlinter]
root_package = lbb

[importlinter:contract:core-purity]
name = core/ has no I/O imports
type = forbidden
source_modules =
    lbb.core
forbidden_modules =
    lbb.adapters
    lbb.ui
    lbb.app

[importlinter:contract:ui-isolation]
name = ui/ cannot reach adapters directly
type = forbidden
source_modules =
    lbb.ui
forbidden_modules =
    lbb.adapters
```

**Step 2:** Verify it fails before package exists, then create stub packages so it passes empty.
```bash
mkdir -p src/lbb/{core,ports,adapters,app,ui}
for d in core ports adapters app ui; do touch src/lbb/$d/__init__.py; done
touch src/lbb/__init__.py
uv run lint-imports
```
Expected: PASS (no violations because modules empty).

**Step 3:** Commit.
```bash
git add .importlinter src/lbb/
git commit -m "chore: import-linter contracts + package skeleton"
```

### Task 0.3: Pre-commit hooks

**Files:**
- Create: `.pre-commit-config.yaml`

**Step 1:** Write config:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: local
    hooks:
      - id: import-linter
        name: import-linter
        entry: uv run lint-imports
        language: system
        pass_filenames: false
```

**Step 2:** Install & verify.
```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

**Step 3:** Commit.
```bash
git add .pre-commit-config.yaml
git commit -m "chore: pre-commit (ruff + import-linter)"
```

### Task 0.4: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1:** Write workflow:
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-extras
      - run: uv run ruff check
      - run: uv run lint-imports
      - run: uv run pytest -m "not e2e"
```

**Step 2:** Commit (CI will run on push).
```bash
git add .github/
git commit -m "ci: matrix test on linux/mac/windows"
```

### Task 0.5: Test harness sanity

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_sanity.py`

**Step 1 (test):**
```python
# tests/test_sanity.py
def test_pytest_works():
    assert 1 + 1 == 2
```

**Step 2:** Run.
```bash
uv run pytest -v
```
Expected: 1 passed.

**Step 3:** Commit.
```bash
git add tests/
git commit -m "test: sanity test, harness verified"
```

---

## Phase 1 — Core domain (pure, no I/O)

### Task 1.1: Domain models

**Files:**
- Create: `src/lbb/core/models.py`
- Create: `tests/unit/core/__init__.py`
- Create: `tests/unit/core/test_models.py`

**Step 1 (test):**
```python
# tests/unit/core/test_models.py
import pytest
from lbb.core.models import Sku, Material, Template, SkuProfile

def test_sku_is_frozen():
    s = Sku("LB-WALLET-LEATHER-S")
    with pytest.raises(AttributeError):
        s.value = "OTHER"

def test_sku_rejects_blank():
    with pytest.raises(ValueError, match="SKU cannot be blank"):
        Sku("   ")

def test_sku_strips_whitespace():
    assert Sku("  LB-X  ").value == "LB-X"

def test_profile_carries_template_and_material():
    t = Template(id=1, name="Wallet S", lbrn2_path="/x.lbrn2", canvas_w_mm=95, canvas_h_mm=110)
    m = Material(id=1, name="Leather 2mm", clb_library="default.clb", clb_entry="LeatherVT")
    p = SkuProfile(sku=Sku("LB-X"), template=t, material=m, overrides={})
    assert p.template.canvas_w_mm == 95
    assert p.material.clb_entry == "LeatherVT"
```

**Step 2:** Run — expect ImportError.
```bash
uv run pytest tests/unit/core/test_models.py -v
```

**Step 3 (implementation):**
```python
# src/lbb/core/models.py
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True, slots=True)
class Sku:
    value: str
    def __post_init__(self):
        stripped = self.value.strip()
        if not stripped:
            raise ValueError("SKU cannot be blank")
        object.__setattr__(self, "value", stripped)

@dataclass(frozen=True, slots=True)
class Material:
    id: int
    name: str
    clb_library: str
    clb_entry: str
    notes: str = ""

@dataclass(frozen=True, slots=True)
class Template:
    id: int
    name: str
    lbrn2_path: str
    canvas_w_mm: float
    canvas_h_mm: float

@dataclass(frozen=True, slots=True)
class SkuProfile:
    sku: Sku
    template: Template
    material: Material
    overrides: dict[str, Any] = field(default_factory=dict)
```

**Step 4:** Run — expect 4 passed.
```bash
uv run pytest tests/unit/core/test_models.py -v
```

**Step 5:** Commit.
```bash
git add src/lbb/core/models.py tests/unit/
git commit -m "feat(core): domain models (Sku, Material, Template, SkuProfile)"
```

### Task 1.2: Typed errors

**Files:**
- Create: `src/lbb/core/errors.py`
- Create: `tests/unit/core/test_errors.py`

**Step 1 (test):**
```python
# tests/unit/core/test_errors.py
from lbb.core.errors import (
    LbbError, SkuNotFound, PreflightFailed, LightBurnNotRunning, LightBurnRejected,
)

def test_hierarchy():
    assert issubclass(SkuNotFound, LbbError)
    assert issubclass(PreflightFailed, LbbError)
    assert issubclass(LightBurnNotRunning, LbbError)
    assert issubclass(LightBurnRejected, LbbError)

def test_preflight_carries_reasons():
    e = PreflightFailed(reasons=["not vector", "stroke color #ABC123 not in palette"])
    assert len(e.reasons) == 2
```

**Step 2:** Run — expect ImportError.

**Step 3 (impl):**
```python
# src/lbb/core/errors.py
from dataclasses import dataclass

class LbbError(Exception):
    """Base for all LBB domain errors."""

class SkuNotFound(LbbError):
    def __init__(self, sku: str):
        super().__init__(f"No profile mapped for SKU: {sku}")
        self.sku = sku

@dataclass
class PreflightFailed(LbbError):
    reasons: list[str]
    def __str__(self) -> str:
        return "Preflight failed: " + "; ".join(self.reasons)

class LightBurnNotRunning(LbbError):
    """LightBurn does not respond to PING on UDP 127.0.0.1:19840"""

class LightBurnRejected(LbbError):
    def __init__(self, response: bytes):
        super().__init__(f"LightBurn rejected request: {response!r}")
        self.response = response
```

**Step 4:** Run — expect 2 passed.

**Step 5:** Commit.
```bash
git add src/lbb/core/errors.py tests/unit/core/test_errors.py
git commit -m "feat(core): typed error hierarchy"
```

### Task 1.3: SKU extractor (filename → SKU)

**Files:**
- Create: `src/lbb/core/extractor.py`
- Create: `tests/unit/core/test_extractor.py`

**Step 1 (test) — including hypothesis property-based:**
```python
# tests/unit/core/test_extractor.py
import pytest
from hypothesis import given, strategies as st
from lbb.core.extractor import extract_sku
from lbb.core.errors import LbbError

class TestExtractSku:
    def test_basic(self):
        assert extract_sku("LB-WALLET-LEATHER-S__order-2381.pdf").value == "LB-WALLET-LEATHER-S"

    def test_alt_extension_case(self):
        assert extract_sku("LB-X__y.PDF").value == "LB-X"

    def test_strips_directory(self):
        assert extract_sku("/some/path/LB-X__y.pdf").value == "LB-X"

    def test_no_double_underscore_raises(self):
        with pytest.raises(LbbError, match="No SKU delimiter"):
            extract_sku("nodelimiter.pdf")

    def test_empty_sku_section_raises(self):
        with pytest.raises(LbbError, match="empty SKU"):
            extract_sku("__name.pdf")

    @given(sku=st.text(alphabet=st.characters(whitelist_categories=("Lu","Ll","Nd"), whitelist_characters="-"), min_size=1, max_size=40))
    def test_roundtrip_property(self, sku):
        # Any non-empty SKU placed before "__name.pdf" must roundtrip
        assert extract_sku(f"{sku}__x.pdf").value == sku
```

**Step 2:** Run — expect ImportError.

**Step 3 (impl):**
```python
# src/lbb/core/extractor.py
from pathlib import Path
from lbb.core.models import Sku
from lbb.core.errors import LbbError

DELIM = "__"

def extract_sku(filename: str) -> Sku:
    """Extract SKU from a filename like `<SKU>__<anything>.pdf`."""
    stem = Path(filename).stem
    if DELIM not in stem:
        raise LbbError(f"No SKU delimiter ('__') in filename: {filename}")
    raw, _ = stem.split(DELIM, 1)
    if not raw.strip():
        raise LbbError(f"Filename has empty SKU section: {filename}")
    return Sku(raw)
```

**Step 4:** Run — expect 6 passed (5 explicit + 1 property).

**Step 5:** Commit.
```bash
git add src/lbb/core/extractor.py tests/unit/core/test_extractor.py
git commit -m "feat(core): SKU extractor + property-based test"
```

### Task 1.4: LightBurn palette constants

**Files:**
- Create: `src/lbb/core/palette.py`
- Create: `tests/unit/core/test_palette.py`

The palette is LightBurn's fixed 30-color layer-mapping table. We need it for preflight checks.

**Step 1 (test):**
```python
# tests/unit/core/test_palette.py
from lbb.core.palette import PALETTE, is_palette_color, layer_index_for_color

def test_palette_has_30_entries():
    assert len(PALETTE) == 30

def test_layer_zero_is_black():
    assert PALETTE[0].lower() == "#000000"

def test_layer_one_is_blue():
    assert PALETTE[1].lower() == "#0000ff"

def test_layer_two_is_red():
    assert PALETTE[2].lower() == "#ff0000"

def test_is_palette_color_case_insensitive():
    assert is_palette_color("#000000")
    assert is_palette_color("#000000".upper())
    assert is_palette_color("#FF0000")
    assert not is_palette_color("#ABCDEF")  # not in palette

def test_layer_index_lookup():
    assert layer_index_for_color("#0000FF") == 1
    assert layer_index_for_color("#abcdef") is None
```

**Step 2:** Run — expect ImportError.

**Step 3 (impl):**
```python
# src/lbb/core/palette.py
# LightBurn's fixed 30-color cut-layer palette.
# Source: https://docs.lightburnsoftware.com/latest/Reference/UI/ColorPalette/
PALETTE: tuple[str, ...] = (
    "#000000", "#0000FF", "#FF0000", "#00E000", "#D0D000",
    "#FF8000", "#00E0E0", "#FF00FF", "#B4B4B4", "#5050FF",
    "#7D4000", "#509050", "#1818A0", "#A03000", "#A050A0",
    "#A0A050", "#505000", "#003030", "#A04030", "#7D6045",
    "#88BB45", "#8000A0", "#404040", "#707000", "#700070",
    "#702070", "#702000", "#207020", "#202070", "#702020",
)
_INDEX = {c.lower(): i for i, c in enumerate(PALETTE)}

def is_palette_color(hex_color: str) -> bool:
    return hex_color.lower() in _INDEX

def layer_index_for_color(hex_color: str) -> int | None:
    return _INDEX.get(hex_color.lower())
```

**Step 4:** Run — expect 6 passed.

**Step 5:** Commit.
```bash
git add src/lbb/core/palette.py tests/unit/core/test_palette.py
git commit -m "feat(core): LightBurn 30-color palette constants"
```

### Task 1.5: PDF preflight (pure rules)

**Files:**
- Create: `src/lbb/core/preflight.py`
- Create: `tests/unit/core/test_preflight.py`
- Create: `tests/fixtures/pdfs/.gitkeep`

We use a `PdfInfo` value object (filled by adapter; preflight stays pure).

**Step 1 (test):**
```python
# tests/unit/core/test_preflight.py
from lbb.core.preflight import PdfInfo, run_preflight, PreflightResult

def _info(**kw) -> PdfInfo:
    defaults = dict(
        page_count=1, is_vector_only=True, stroke_colors={"#000000"},
        bbox_mm=(50.0, 60.0),
    )
    defaults.update(kw)
    return PdfInfo(**defaults)

def test_passes_clean_pdf():
    result = run_preflight(_info(), canvas_mm=(95.0, 110.0))
    assert result.ok
    assert result.reasons == []

def test_fails_when_raster():
    result = run_preflight(_info(is_vector_only=False), canvas_mm=(95.0, 110.0))
    assert not result.ok
    assert any("vector" in r for r in result.reasons)

def test_fails_when_off_palette_color():
    result = run_preflight(_info(stroke_colors={"#ABCDEF"}), canvas_mm=(95.0, 110.0))
    assert not result.ok
    assert any("palette" in r.lower() for r in result.reasons)

def test_fails_when_too_large():
    result = run_preflight(_info(bbox_mm=(200.0, 200.0)), canvas_mm=(95.0, 110.0))
    assert not result.ok
    assert any("canvas" in r.lower() for r in result.reasons)

def test_aggregates_multiple_failures():
    result = run_preflight(_info(is_vector_only=False, stroke_colors={"#ABCDEF"}), canvas_mm=(10.0, 10.0))
    assert len(result.reasons) >= 2
```

**Step 2:** Run — expect ImportError.

**Step 3 (impl):**
```python
# src/lbb/core/preflight.py
from dataclasses import dataclass
from lbb.core.palette import is_palette_color

@dataclass(frozen=True, slots=True)
class PdfInfo:
    page_count: int
    is_vector_only: bool
    stroke_colors: frozenset[str] | set[str]
    bbox_mm: tuple[float, float]  # (width, height)

@dataclass(frozen=True, slots=True)
class PreflightResult:
    ok: bool
    reasons: list[str]

def run_preflight(info: PdfInfo, canvas_mm: tuple[float, float]) -> PreflightResult:
    reasons: list[str] = []
    if info.page_count != 1:
        reasons.append(f"expected 1 page, got {info.page_count}")
    if not info.is_vector_only:
        reasons.append("PDF contains raster content (must be vector-only)")
    off = sorted(c for c in info.stroke_colors if not is_palette_color(c))
    if off:
        reasons.append(f"stroke colors not in LightBurn palette: {', '.join(off)}")
    if info.bbox_mm[0] > canvas_mm[0] or info.bbox_mm[1] > canvas_mm[1]:
        reasons.append(
            f"design {info.bbox_mm[0]:.1f}×{info.bbox_mm[1]:.1f}mm exceeds canvas {canvas_mm[0]:.1f}×{canvas_mm[1]:.1f}mm"
        )
    return PreflightResult(ok=not reasons, reasons=reasons)
```

**Step 4:** Run — expect 5 passed.

**Step 5:** Commit.
```bash
git add src/lbb/core/preflight.py tests/unit/core/test_preflight.py tests/fixtures/
git commit -m "feat(core): preflight rules (vector-only, palette, canvas)"
```

---

## Phase 2 — Ports & adapters

### Task 2.1: Define ports (Protocols)

**Files:**
- Create: `src/lbb/ports/lightburn.py`
- Create: `src/lbb/ports/repository.py`
- Create: `src/lbb/ports/pdf.py`

No tests yet — Protocols are interfaces, exercised via adapter tests below.

**Step 1 (write all three):**

```python
# src/lbb/ports/lightburn.py
from pathlib import Path
from typing import Protocol
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class LBStatus:
    running: bool
    busy: bool = False
    raw: str = ""

class LightBurnPort(Protocol):
    def is_running(self) -> bool: ...
    def load_file(self, path: Path) -> None: ...
    def status(self) -> LBStatus: ...
```

```python
# src/lbb/ports/repository.py
from typing import Protocol
from lbb.core.models import Sku, SkuProfile, Material, Template

class ProfileRepository(Protocol):
    def get(self, sku: Sku) -> SkuProfile | None: ...
    def upsert(self, profile: SkuProfile) -> None: ...
    def list_materials(self) -> list[Material]: ...
    def list_templates(self) -> list[Template]: ...
    def upsert_material(self, m: Material) -> Material: ...
    def upsert_template(self, t: Template) -> Template: ...

class AuditLog(Protocol):
    def record(self, event: str, **fields: object) -> None: ...
```

```python
# src/lbb/ports/pdf.py
from pathlib import Path
from typing import Protocol
from lbb.core.preflight import PdfInfo

class PdfReader(Protocol):
    def read_info(self, path: Path) -> PdfInfo: ...
    def render_thumbnail_png(self, path: Path, max_px: int) -> bytes: ...
```

**Step 2:** Run import-linter to confirm no I/O leak into core.
```bash
uv run lint-imports
```

**Step 3:** Commit.
```bash
git add src/lbb/ports/
git commit -m "feat(ports): LightBurnPort, ProfileRepository, PdfReader, AuditLog"
```

### Task 2.2: LightBurn fake (in-memory adapter for tests)

**Files:**
- Create: `src/lbb/adapters/lightburn_fake.py`
- Create: `tests/unit/adapters/__init__.py`
- Create: `tests/unit/adapters/test_lightburn_fake.py`

**Step 1 (test):**
```python
# tests/unit/adapters/test_lightburn_fake.py
from pathlib import Path
import pytest
from lbb.adapters.lightburn_fake import LightBurnFake
from lbb.core.errors import LightBurnNotRunning

def test_default_is_running():
    fake = LightBurnFake()
    assert fake.is_running()

def test_can_simulate_not_running():
    fake = LightBurnFake(running=False)
    with pytest.raises(LightBurnNotRunning):
        fake.load_file(Path("/tmp/x.lbrn2"))

def test_records_loaded_files():
    fake = LightBurnFake()
    fake.load_file(Path("/tmp/a.lbrn2"))
    fake.load_file(Path("/tmp/b.lbrn2"))
    assert fake.loaded == [Path("/tmp/a.lbrn2"), Path("/tmp/b.lbrn2")]
```

**Step 2:** Run — ImportError.

**Step 3 (impl):**
```python
# src/lbb/adapters/lightburn_fake.py
from pathlib import Path
from lbb.ports.lightburn import LightBurnPort, LBStatus
from lbb.core.errors import LightBurnNotRunning

class LightBurnFake(LightBurnPort):
    def __init__(self, running: bool = True):
        self._running = running
        self.loaded: list[Path] = []

    def is_running(self) -> bool:
        return self._running

    def load_file(self, path: Path) -> None:
        if not self._running:
            raise LightBurnNotRunning()
        self.loaded.append(path)

    def status(self) -> LBStatus:
        return LBStatus(running=self._running, raw="FAKE")
```

**Step 4:** Run — 3 passed.

**Step 5:** Commit.
```bash
git add src/lbb/adapters/lightburn_fake.py tests/unit/adapters/
git commit -m "feat(adapters): in-memory LightBurnFake"
```

### Task 2.3: LightBurn UDP adapter (real)

**Files:**
- Create: `src/lbb/adapters/lightburn_udp.py`
- Create: `tests/unit/adapters/test_lightburn_udp.py`

We use a real UDP socket in tests by binding a local listener that echoes. This keeps the test fast (~50ms) and avoids mocking the socket library.

**Step 1 (test):**
```python
# tests/unit/adapters/test_lightburn_udp.py
import socket
import threading
import pytest
from pathlib import Path
from lbb.adapters.lightburn_udp import LightBurnUDPAdapter
from lbb.core.errors import LightBurnNotRunning, LightBurnRejected

class _FakeLightBurn:
    """Mini UDP listener that mimics LightBurn's protocol."""
    def __init__(self, responses: dict[bytes, bytes]):
        self.responses = responses
        self.received: list[bytes] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("127.0.0.1", 0))
        self.port = self._sock.getsockname()[1]
        self._stop = False
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self):
        self._sock.settimeout(0.1)
        while not self._stop:
            try:
                data, addr = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            self.received.append(data)
            resp = self.responses.get(data, b"")
            if resp:
                self._sock.sendto(resp, addr)

    def stop(self):
        self._stop = True
        self._t.join(timeout=1)
        self._sock.close()

@pytest.fixture
def fake_lb():
    lb = _FakeLightBurn({b"PING": b"OK"})
    yield lb
    lb.stop()

def test_is_running_true_when_responds(fake_lb):
    a = LightBurnUDPAdapter(host="127.0.0.1", port=fake_lb.port)
    assert a.is_running()

def test_is_running_false_when_no_response():
    a = LightBurnUDPAdapter(host="127.0.0.1", port=1, timeout=0.1)  # nothing on port 1
    assert not a.is_running()

def test_load_file_sends_correct_command(tmp_path):
    fake = _FakeLightBurn({b"PING": b"OK", f"LOADFILE://{tmp_path/'x.lbrn2'}".encode(): b"OK"})
    try:
        a = LightBurnUDPAdapter(host="127.0.0.1", port=fake.port)
        a.load_file(tmp_path / "x.lbrn2")
        assert any(d.startswith(b"LOADFILE://") for d in fake.received)
    finally:
        fake.stop()

def test_load_file_raises_when_not_running():
    a = LightBurnUDPAdapter(host="127.0.0.1", port=1, timeout=0.1)
    with pytest.raises(LightBurnNotRunning):
        a.load_file(Path("/tmp/x.lbrn2"))

def test_load_file_raises_on_non_ok_response(tmp_path):
    fake = _FakeLightBurn({b"PING": b"OK", f"LOADFILE://{tmp_path/'x.lbrn2'}".encode(): b"NACK"})
    try:
        a = LightBurnUDPAdapter(host="127.0.0.1", port=fake.port)
        with pytest.raises(LightBurnRejected):
            a.load_file(tmp_path / "x.lbrn2")
    finally:
        fake.stop()
```

**Step 2:** Run — ImportError.

**Step 3 (impl):**
```python
# src/lbb/adapters/lightburn_udp.py
import socket
from pathlib import Path
from lbb.ports.lightburn import LightBurnPort, LBStatus
from lbb.core.errors import LightBurnNotRunning, LightBurnRejected

DEFAULT_PORT = 19840

class LightBurnUDPAdapter(LightBurnPort):
    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT, timeout: float = 2.0):
        self.host, self.port, self.timeout = host, port, timeout

    def _roundtrip(self, payload: bytes) -> bytes | None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        try:
            sock.sendto(payload, (self.host, self.port))
            try:
                data, _ = sock.recvfrom(4096)
                return data
            except socket.timeout:
                return None
        finally:
            sock.close()

    def is_running(self) -> bool:
        return self._roundtrip(b"PING") == b"OK"

    def load_file(self, path: Path) -> None:
        if not self.is_running():
            raise LightBurnNotRunning()
        resp = self._roundtrip(f"LOADFILE://{path}".encode())
        if resp != b"OK":
            raise LightBurnRejected(resp or b"")

    def status(self) -> LBStatus:
        raw = self._roundtrip(b"STATUS")
        return LBStatus(running=raw is not None, raw=(raw or b"").decode(errors="replace"))
```

**Step 4:** Run — 5 passed.

**Step 5:** Commit.
```bash
git add src/lbb/adapters/lightburn_udp.py tests/unit/adapters/test_lightburn_udp.py
git commit -m "feat(adapters): LightBurnUDPAdapter (real UDP) + integration tests"
```

### Task 2.4: SQLite repository

**Files:**
- Create: `src/lbb/adapters/sqlite_repo.py`
- Create: `src/lbb/adapters/migrations.py`
- Create: `tests/unit/adapters/test_sqlite_repo.py`

**Step 1 (test):**
```python
# tests/unit/adapters/test_sqlite_repo.py
import pytest
from pathlib import Path
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.core.models import Sku, Material, Template, SkuProfile

@pytest.fixture
def repo(tmp_path):
    return SqliteProfileRepository(tmp_path / "p.sqlite")

def test_returns_none_for_unknown_sku(repo):
    assert repo.get(Sku("MISSING")) is None

def test_upsert_and_get(repo):
    t = repo.upsert_template(Template(id=0, name="W S", lbrn2_path="/x.lbrn2",
                                       canvas_w_mm=95, canvas_h_mm=110))
    m = repo.upsert_material(Material(id=0, name="Leather", clb_library="d.clb", clb_entry="L"))
    repo.upsert(SkuProfile(sku=Sku("LB-X"), template=t, material=m, overrides={}))
    got = repo.get(Sku("LB-X"))
    assert got is not None
    assert got.template.name == "W S"
    assert got.material.name == "Leather"

def test_list_materials_and_templates(repo):
    repo.upsert_material(Material(id=0, name="A", clb_library="x", clb_entry="A"))
    repo.upsert_material(Material(id=0, name="B", clb_library="x", clb_entry="B"))
    assert {m.name for m in repo.list_materials()} == {"A", "B"}
```

**Step 2:** Run — ImportError.

**Step 3 (impl):**
```python
# src/lbb/adapters/migrations.py
SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS materials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  clb_library TEXT NOT NULL,
  clb_entry TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  lbrn2_path TEXT NOT NULL,
  canvas_w_mm REAL NOT NULL,
  canvas_h_mm REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sku_profiles (
  sku TEXT PRIMARY KEY,
  template_id INTEGER REFERENCES templates(id),
  material_id INTEGER REFERENCES materials(id),
  overrides_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_by TEXT NOT NULL DEFAULT 'system'
);
"""
```

```python
# src/lbb/adapters/sqlite_repo.py
import json
import sqlite3
from pathlib import Path
from lbb.core.models import Sku, SkuProfile, Material, Template
from lbb.ports.repository import ProfileRepository
from lbb.adapters.migrations import SCHEMA_V1

class SqliteProfileRepository(ProfileRepository):
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_V1)

    def get(self, sku: Sku) -> SkuProfile | None:
        cur = self._conn.execute(
            "SELECT sp.sku, sp.overrides_json, "
            "       t.id AS tid, t.name AS tname, t.lbrn2_path, t.canvas_w_mm, t.canvas_h_mm, "
            "       m.id AS mid, m.name AS mname, m.clb_library, m.clb_entry, m.notes "
            "FROM sku_profiles sp "
            "JOIN templates t ON t.id = sp.template_id "
            "JOIN materials m ON m.id = sp.material_id "
            "WHERE sp.sku = ?", (sku.value,))
        row = cur.fetchone()
        if not row:
            return None
        return SkuProfile(
            sku=Sku(row["sku"]),
            template=Template(id=row["tid"], name=row["tname"], lbrn2_path=row["lbrn2_path"],
                              canvas_w_mm=row["canvas_w_mm"], canvas_h_mm=row["canvas_h_mm"]),
            material=Material(id=row["mid"], name=row["mname"], clb_library=row["clb_library"],
                              clb_entry=row["clb_entry"], notes=row["notes"]),
            overrides=json.loads(row["overrides_json"] or "{}"),
        )

    def upsert(self, profile: SkuProfile) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO sku_profiles (sku, template_id, material_id, overrides_json) "
                "VALUES (?,?,?,?) "
                "ON CONFLICT(sku) DO UPDATE SET template_id=excluded.template_id, "
                "  material_id=excluded.material_id, overrides_json=excluded.overrides_json, "
                "  updated_at=datetime('now')",
                (profile.sku.value, profile.template.id, profile.material.id,
                 json.dumps(profile.overrides)),
            )

    def upsert_material(self, m: Material) -> Material:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO materials (name, clb_library, clb_entry, notes) VALUES (?,?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET clb_library=excluded.clb_library, "
                "  clb_entry=excluded.clb_entry, notes=excluded.notes RETURNING id",
                (m.name, m.clb_library, m.clb_entry, m.notes))
            new_id = cur.fetchone()[0]
        return Material(id=new_id, name=m.name, clb_library=m.clb_library,
                        clb_entry=m.clb_entry, notes=m.notes)

    def upsert_template(self, t: Template) -> Template:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO templates (name, lbrn2_path, canvas_w_mm, canvas_h_mm) VALUES (?,?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET lbrn2_path=excluded.lbrn2_path, "
                "  canvas_w_mm=excluded.canvas_w_mm, canvas_h_mm=excluded.canvas_h_mm RETURNING id",
                (t.name, t.lbrn2_path, t.canvas_w_mm, t.canvas_h_mm))
            new_id = cur.fetchone()[0]
        return Template(id=new_id, name=t.name, lbrn2_path=t.lbrn2_path,
                        canvas_w_mm=t.canvas_w_mm, canvas_h_mm=t.canvas_h_mm)

    def list_materials(self) -> list[Material]:
        return [Material(id=r["id"], name=r["name"], clb_library=r["clb_library"],
                         clb_entry=r["clb_entry"], notes=r["notes"])
                for r in self._conn.execute("SELECT * FROM materials ORDER BY name")]

    def list_templates(self) -> list[Template]:
        return [Template(id=r["id"], name=r["name"], lbrn2_path=r["lbrn2_path"],
                         canvas_w_mm=r["canvas_w_mm"], canvas_h_mm=r["canvas_h_mm"])
                for r in self._conn.execute("SELECT * FROM templates ORDER BY name")]
```

**Step 4:** Run — 3 passed.

**Step 5:** Commit.
```bash
git add src/lbb/adapters/sqlite_repo.py src/lbb/adapters/migrations.py tests/unit/adapters/test_sqlite_repo.py
git commit -m "feat(adapters): SQLite ProfileRepository"
```

### Task 2.5: PDF reader adapter (pypdfium2)

**Files:**
- Create: `src/lbb/adapters/pdfium_reader.py`
- Create: `tests/unit/adapters/test_pdfium_reader.py`
- Add fixture: `tests/fixtures/pdfs/sample-vector.pdf` (manually create or generate via reportlab in conftest — see Step 0 below)

**Step 0 (fixture conftest):**
```python
# tests/conftest.py
import pytest
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "pdfs"

@pytest.fixture(scope="session")
def sample_vector_pdf() -> Path:
    """Generate a deterministic vector-only PDF for tests."""
    # We use pypdfium2 to create a minimal PDF in code so the test is self-contained.
    # Alternatively, ship a fixture .pdf in the repo. Pick one and document.
    path = FIXTURE_DIR / "sample-vector.pdf"
    if path.exists():
        return path
    import pypdfium2 as pdfium
    # Minimal vector PDF (50×60mm box with a black stroke).
    # Use lower-level pdfium APIs to create vectors; in practice we'll commit a hand-authored
    # PDF as the fixture rather than generate it.
    raise pytest.skip("Commit tests/fixtures/pdfs/sample-vector.pdf manually for now")
```

**Note:** For Task 2.5 we keep the test surface small. We commit a real fixture PDF (50×60mm, single black stroke) under `tests/fixtures/pdfs/`. The engineer authors this in Inkscape/Illustrator using `#000000` stroke and exports.

**Step 1 (test):**
```python
# tests/unit/adapters/test_pdfium_reader.py
import pytest
from lbb.adapters.pdfium_reader import PdfiumReader
from pathlib import Path

FIXTURE = Path(__file__).parents[2] / "fixtures" / "pdfs" / "sample-vector.pdf"
pytestmark = pytest.mark.skipif(not FIXTURE.exists(), reason="fixture PDF missing")

def test_reads_basic_info():
    r = PdfiumReader()
    info = r.read_info(FIXTURE)
    assert info.page_count == 1
    assert info.is_vector_only is True
    assert "#000000" in {c.lower() for c in info.stroke_colors}
    assert info.bbox_mm[0] > 0 and info.bbox_mm[1] > 0
```

**Step 2:** Run — fixture-skip (which counts as PASS for our gate).

**Step 3 (impl):**
```python
# src/lbb/adapters/pdfium_reader.py
from pathlib import Path
import pypdfium2 as pdfium
from lbb.ports.pdf import PdfReader
from lbb.core.preflight import PdfInfo

class PdfiumReader(PdfReader):
    def read_info(self, path: Path) -> PdfInfo:
        pdf = pdfium.PdfDocument(str(path))
        try:
            n_pages = len(pdf)
            page = pdf[0]
            # 1 PDF unit = 1/72 inch; 1 inch = 25.4 mm.
            pt_to_mm = 25.4 / 72
            w_mm = page.get_width() * pt_to_mm
            h_mm = page.get_height() * pt_to_mm
            # Vector vs. raster: walk page objects.
            is_vector_only = True
            stroke_colors: set[str] = set()
            for obj in page.get_objects():
                obj_type = obj.type
                if obj_type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                    is_vector_only = False
                if obj_type == pdfium.raw.FPDF_PAGEOBJ_PATH:
                    r, g, b, _ = obj.get_stroke_color()
                    stroke_colors.add(f"#{r:02X}{g:02X}{b:02X}")
            return PdfInfo(
                page_count=n_pages,
                is_vector_only=is_vector_only,
                stroke_colors=stroke_colors,
                bbox_mm=(w_mm, h_mm),
            )
        finally:
            pdf.close()

    def render_thumbnail_png(self, path: Path, max_px: int) -> bytes:
        import io
        pdf = pdfium.PdfDocument(str(path))
        try:
            page = pdf[0]
            scale = max_px / max(page.get_width(), page.get_height())
            pil = page.render(scale=scale).to_pil()
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            return buf.getvalue()
        finally:
            pdf.close()
```

**Step 4:** Run. If fixture present → PASS. If absent → SKIP. Either is acceptable for now.

**Step 5:** Commit.
```bash
git add src/lbb/adapters/pdfium_reader.py tests/unit/adapters/test_pdfium_reader.py tests/conftest.py
git commit -m "feat(adapters): PdfiumReader using pypdfium2"
```

---

## Phase 3 — Template builder (.lbrn2 generation)

This is the highest-risk phase because the `.lbrn2` schema is reverse-engineered. Use golden-file testing aggressively.

### Task 3.1: Author the first base template by hand in LightBurn

**Manual step (no code yet).** The engineer must:

1. Open LightBurn (on a Windows or Mac dev machine).
2. Set canvas to 95×110mm.
3. Add a layer-00 (black) cut layer linked to a Material Library entry `LeatherVT` in library `default.clb`. Don't worry about real cut parameters; the entry just needs to exist.
4. Draw a rectangle as a placeholder (we'll replace it).
5. Group the rectangle, set group name in the XML by saving the file then editing: rename the group's `Name` attribute to `DESIGN_PLACEHOLDER`.
6. Save as `templates/wallet-small.lbrn2`.
7. Commit this fixture template.

```bash
mkdir -p templates
# manually save the file via LightBurn into the above path, then:
git add templates/wallet-small.lbrn2
git commit -m "feat: hand-authored Wallet-Small base template"
```

### Task 3.2: Read template + extract placeholder

**Files:**
- Create: `src/lbb/core/template_builder.py`
- Create: `tests/unit/core/test_template_builder.py`

**Step 1 (test):**
```python
# tests/unit/core/test_template_builder.py
from pathlib import Path
from lxml import etree
from lbb.core.template_builder import locate_placeholder, TemplateError
import pytest

TEMPLATE = Path(__file__).parents[2] / "fixtures" / "wallet-small.lbrn2"
pytestmark = pytest.mark.skipif(not TEMPLATE.exists(), reason="template fixture missing")

def test_finds_placeholder_group():
    tree = etree.parse(str(TEMPLATE))
    node = locate_placeholder(tree)
    assert node is not None
    assert node.get("Name") == "DESIGN_PLACEHOLDER"

def test_raises_when_missing(tmp_path):
    bare = tmp_path / "bare.lbrn2"
    bare.write_text("<?xml version='1.0'?><LightBurnProject><CutSettings/></LightBurnProject>")
    tree = etree.parse(str(bare))
    with pytest.raises(TemplateError):
        locate_placeholder(tree)
```

**Step 2:** Copy template fixture into `tests/fixtures/` (engineer step):
```bash
cp templates/wallet-small.lbrn2 tests/fixtures/wallet-small.lbrn2
git add tests/fixtures/wallet-small.lbrn2
```

**Step 3 (impl):**
```python
# src/lbb/core/template_builder.py
from lxml import etree

class TemplateError(Exception):
    pass

PLACEHOLDER_NAME = "DESIGN_PLACEHOLDER"

def locate_placeholder(tree: etree._ElementTree) -> etree._Element:
    """Find the <Shape Type='Group' Name='DESIGN_PLACEHOLDER'> element."""
    for el in tree.iter():
        if el.get("Name") == PLACEHOLDER_NAME:
            return el
    raise TemplateError(f"Template missing group named '{PLACEHOLDER_NAME}'")
```

**Step 4:** Run — 2 passed (or skipped if fixture absent).

**Step 5:** Commit.
```bash
git add src/lbb/core/template_builder.py tests/unit/core/test_template_builder.py
git commit -m "feat(core): locate template placeholder group"
```

### Task 3.3: Convert PDF vectors to LightBurn shapes

**Files:**
- Modify: `src/lbb/core/template_builder.py`
- Modify: `tests/unit/core/test_template_builder.py`

This is the most schema-dependent piece. Strategy: parse PDF paths to a normalized vector list `(layer_index, [(cmd, points), ...])`, then emit them as `<Shape Type="Path">` elements that LightBurn understands.

**Step 1 (test — golden-file):**
```python
# add to tests/unit/core/test_template_builder.py
from lbb.core.template_builder import build_lbrn2
from lbb.core.preflight import PdfInfo

def test_build_lbrn2_golden(tmp_path):
    out = build_lbrn2(
        template_path=TEMPLATE,
        shapes=[("M 10 10 L 60 10 L 60 50 L 10 50 Z", 0)],  # single black rectangle path
    )
    # Snapshot byte-stable
    golden = (Path(__file__).parents[2] / "golden" / "wallet-small-rect.lbrn2").read_bytes()
    assert out.strip() == golden.strip(), "lbrn2 output drifted; regenerate golden if intended"
```

**Step 2:** Run — fails (no `build_lbrn2`).

**Step 3 (impl) — add to template_builder.py:**
```python
from pathlib import Path
from lxml import etree

def build_lbrn2(*, template_path: Path, shapes: list[tuple[str, int]]) -> bytes:
    """
    Build a .lbrn2 by cloning template and inserting shapes (SVG path strings + cut-layer index)
    into the DESIGN_PLACEHOLDER group.
    """
    tree = etree.parse(str(template_path))
    placeholder = locate_placeholder(tree)
    # Remove existing children of placeholder
    for child in list(placeholder):
        placeholder.remove(child)
    for d, layer in shapes:
        shape = etree.SubElement(placeholder, "Shape", attrib={"Type": "Path", "CutIndex": str(layer)})
        verts = etree.SubElement(shape, "VertList")
        prims = etree.SubElement(shape, "PrimList")
        # Convert SVG path 'd' into VertList + PrimList per LBRN2 schema.
        _emit_svg_path(d, verts, prims)
    return etree.tostring(tree, xml_declaration=True, encoding="UTF-8", pretty_print=True)

def _emit_svg_path(d: str, verts: etree._Element, prims: etree._Element) -> None:
    """
    Minimal SVG path → LBRN2 verts/prims emitter.
    Supports M, L, Z commands only; expand for curves in later phase.
    """
    import re
    tokens = re.findall(r"([MLZmlz])\s*([0-9.\-\s]*)", d)
    points: list[tuple[float, float]] = []
    start_idx = None
    for cmd, args in tokens:
        nums = [float(x) for x in args.replace(",", " ").split()] if args.strip() else []
        if cmd in ("M", "m"):
            x, y = nums[0], nums[1]
            points.append((x, y))
            start_idx = len(points) - 1
        elif cmd in ("L", "l"):
            for i in range(0, len(nums), 2):
                points.append((nums[i], nums[i+1]))
        elif cmd in ("Z", "z"):
            # close: add edge from last point back to start_idx via prim "LineClosed"
            pass
    for i, (x, y) in enumerate(points):
        etree.SubElement(verts, "V", attrib={"vx": f"{x:.4f}", "vy": f"{y:.4f}", "c": "0x0"})
    for i in range(len(points) - 1):
        etree.SubElement(prims, "P", attrib={"T": "L", "p0": str(i), "p1": str(i+1)})
    if start_idx is not None:
        etree.SubElement(prims, "P", attrib={"T": "L", "p0": str(len(points)-1), "p1": str(start_idx)})
```

**Step 4:** Generate golden file once (engineer step). After confirming the output opens correctly in LightBurn:
```bash
python -c "from pathlib import Path; from lbb.core.template_builder import build_lbrn2; \
out = build_lbrn2(template_path=Path('tests/fixtures/wallet-small.lbrn2'), \
                  shapes=[('M 10 10 L 60 10 L 60 50 L 10 50 Z', 0)]); \
Path('tests/golden/wallet-small-rect.lbrn2').write_bytes(out)"
```
Then **open it in LightBurn and verify** the rectangle appears on layer 00.

**Step 5:** Run — 1 passed.

**Step 6:** Commit.
```bash
git add src/lbb/core/template_builder.py tests/unit/core/test_template_builder.py tests/golden/
git commit -m "feat(core): build_lbrn2 — minimal SVG-path → LBRN2 emitter (M/L/Z)"
```

### Task 3.4: PDF vector → SVG path strings (adapter side)

**Files:**
- Modify: `src/lbb/adapters/pdfium_reader.py` — add `extract_paths(path) -> list[(svg_d, hex_color)]`
- Modify: `tests/unit/adapters/test_pdfium_reader.py` — add test

**Step 1 (test):**
```python
def test_extract_paths_finds_rectangle():
    r = PdfiumReader()
    paths = r.extract_paths(FIXTURE)
    assert len(paths) >= 1
    d, color = paths[0]
    assert color.lower() == "#000000"
    assert "M" in d  # SVG path command
```

**Step 2:** Run — AttributeError.

**Step 3 (impl) — append to `PdfiumReader`:**
```python
def extract_paths(self, path: Path) -> list[tuple[str, str]]:
    pdf = pdfium.PdfDocument(str(path))
    try:
        page = pdf[0]
        paths: list[tuple[str, str]] = []
        for obj in page.get_objects():
            if obj.type != pdfium.raw.FPDF_PAGEOBJ_PATH:
                continue
            r, g, b, _ = obj.get_stroke_color()
            color = f"#{r:02X}{g:02X}{b:02X}"
            d = _path_segments_to_svg_d(obj)
            if d:
                paths.append((d, color))
        return paths
    finally:
        pdf.close()

def _path_segments_to_svg_d(path_obj) -> str:
    # Iterate pdfium path segments (PointType.MOVE / LINE / BEZIER / CLOSE) into an SVG-d string.
    # Inline here for clarity; refactor to module-level if reused.
    pts = []
    for seg in path_obj.get_segments():
        pt_type = seg.get_type()  # see pypdfium2 docs
        x, y = seg.get_point()
        if pt_type == "M":
            pts.append(f"M {x:.4f} {y:.4f}")
        elif pt_type == "L":
            pts.append(f"L {x:.4f} {y:.4f}")
        elif pt_type == "Z":
            pts.append("Z")
        # Curves: phase-2 enhancement
    return " ".join(pts)
```

**Step 4:** Run — 1 passed (assuming fixture has a vector path).

**Step 5:** Commit.
```bash
git add src/lbb/adapters/pdfium_reader.py tests/unit/adapters/test_pdfium_reader.py
git commit -m "feat(adapters): PdfiumReader.extract_paths → SVG-d strings"
```

---

## Phase 4 — Pipeline + DI

### Task 4.1: Job state + pipeline

**Files:**
- Create: `src/lbb/app/__init__.py`
- Create: `src/lbb/app/job.py`
- Create: `src/lbb/app/pipeline.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_pipeline.py`

**Step 1 (test — full happy path with fakes):**
```python
# tests/integration/test_pipeline.py
from pathlib import Path
import pytest
from lbb.app.pipeline import run_pipeline, PipelineDeps
from lbb.app.job import Job
from lbb.adapters.lightburn_fake import LightBurnFake
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.adapters.pdfium_reader import PdfiumReader
from lbb.core.models import Sku, Material, Template, SkuProfile

FIXTURE_PDF = Path(__file__).parents[1] / "fixtures" / "pdfs" / "LB-WALLET-LEATHER-S__demo.pdf"
TEMPLATE = Path(__file__).parents[1] / "fixtures" / "wallet-small.lbrn2"

@pytest.mark.skipif(not (FIXTURE_PDF.exists() and TEMPLATE.exists()), reason="fixtures missing")
def test_happy_path_loads_to_lightburn(tmp_path):
    repo = SqliteProfileRepository(tmp_path / "p.sqlite")
    t = repo.upsert_template(Template(id=0, name="Wallet S", lbrn2_path=str(TEMPLATE),
                                       canvas_w_mm=95, canvas_h_mm=110))
    m = repo.upsert_material(Material(id=0, name="Leather", clb_library="default.clb", clb_entry="LeatherVT"))
    repo.upsert(SkuProfile(sku=Sku("LB-WALLET-LEATHER-S"), template=t, material=m, overrides={}))

    lb = LightBurnFake()
    deps = PipelineDeps(repo=repo, pdf=PdfiumReader(), lightburn=lb, temp_dir=tmp_path / "out")
    result = run_pipeline(Job(source_pdf=FIXTURE_PDF), deps)

    assert result.ok, result.error
    assert len(lb.loaded) == 1
    assert lb.loaded[0].suffix == ".lbrn2"
```

**Step 2:** Run — ImportError.

**Step 3 (impl):**
```python
# src/lbb/app/job.py
from dataclasses import dataclass
from pathlib import Path
from lbb.core.models import SkuProfile, Sku

@dataclass(frozen=True, slots=True)
class Job:
    source_pdf: Path

@dataclass(frozen=True, slots=True)
class JobResult:
    ok: bool
    output_path: Path | None = None
    sku: Sku | None = None
    profile: SkuProfile | None = None
    error: str | None = None
```

```python
# src/lbb/app/pipeline.py
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from lbb.app.job import Job, JobResult
from lbb.core.extractor import extract_sku
from lbb.core.preflight import run_preflight
from lbb.core.template_builder import build_lbrn2
from lbb.core.errors import SkuNotFound, PreflightFailed, LbbError
from lbb.ports.lightburn import LightBurnPort
from lbb.ports.repository import ProfileRepository
from lbb.ports.pdf import PdfReader

@dataclass(frozen=True, slots=True)
class PipelineDeps:
    repo: ProfileRepository
    pdf: PdfReader
    lightburn: LightBurnPort
    temp_dir: Path

def run_pipeline(job: Job, deps: PipelineDeps) -> JobResult:
    try:
        sku = extract_sku(job.source_pdf.name)
        profile = deps.repo.get(sku)
        if not profile:
            raise SkuNotFound(sku.value)
        info = deps.pdf.read_info(job.source_pdf)
        pf = run_preflight(info, canvas_mm=(profile.template.canvas_w_mm, profile.template.canvas_h_mm))
        if not pf.ok:
            raise PreflightFailed(reasons=pf.reasons)
        paths = deps.pdf.extract_paths(job.source_pdf)
        # Default everything to layer 0 for MVP; phase 2 maps color → layer index via palette
        shapes = [(d, 0) for d, _color in paths]
        out_bytes = build_lbrn2(template_path=Path(profile.template.lbrn2_path), shapes=shapes)
        deps.temp_dir.mkdir(parents=True, exist_ok=True)
        out_path = deps.temp_dir / f"{sku.value}-{datetime.now():%Y%m%d-%H%M%S}.lbrn2"
        out_path.write_bytes(out_bytes)
        deps.lightburn.load_file(out_path)
        return JobResult(ok=True, output_path=out_path, sku=sku, profile=profile)
    except LbbError as e:
        return JobResult(ok=False, error=str(e))
```

**Step 4:** Run — 1 passed (or skipped if fixtures absent — generate fixtures first).

**Step 5:** Commit.
```bash
git add src/lbb/app/ tests/integration/
git commit -m "feat(app): job pipeline (extract→resolve→preflight→build→dispatch)"
```

### Task 4.2: DI container (composition root)

**Files:**
- Create: `src/lbb/app/container.py`

**Step 1 (no test — wiring is exercised by integration tests already).**

**Step 2 (impl):**
```python
# src/lbb/app/container.py
from dataclasses import dataclass
from pathlib import Path
from lbb.adapters.lightburn_udp import LightBurnUDPAdapter
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.adapters.pdfium_reader import PdfiumReader
from lbb.app.pipeline import PipelineDeps

@dataclass(frozen=True)
class AppPaths:
    db_path: Path
    temp_dir: Path

def build_pipeline_deps(paths: AppPaths) -> PipelineDeps:
    return PipelineDeps(
        repo=SqliteProfileRepository(paths.db_path),
        pdf=PdfiumReader(),
        lightburn=LightBurnUDPAdapter(),
        temp_dir=paths.temp_dir,
    )
```

**Step 3:** Commit.
```bash
git add src/lbb/app/container.py
git commit -m "feat(app): DI composition root"
```

---

## Phase 5 — UI (PySide6)

### Task 5.1: Theme/QSS tokens

**Files:**
- Create: `src/lbb/ui/__init__.py`
- Create: `src/lbb/ui/theme/__init__.py`
- Create: `src/lbb/ui/theme/tokens.py`
- Create: `src/lbb/ui/theme/app.qss`

**Step 1:** Write `tokens.py`:
```python
# src/lbb/ui/theme/tokens.py
class Color:
    BG          = "#0B0D12"
    SURFACE     = "#141821"
    SURFACE_ALT = "#1B2030"
    BORDER      = "#252A38"
    TEXT        = "#E5E7EB"
    TEXT_DIM    = "#94A3B8"
    ACCENT      = "#7DD3FC"
    OK          = "#A3E635"
    WARN        = "#FBBF24"
    ERROR       = "#FB7185"
```

**Step 2:** Write `app.qss`:
```css
/* src/lbb/ui/theme/app.qss */
* { font-family: "Inter", "IBM Plex Sans", "SF Pro Text", "Segoe UI", sans-serif; color: #E5E7EB; }
QMainWindow, QDialog { background: #0B0D12; }
QPushButton { background: #1B2030; border: 1px solid #252A38; border-radius: 8px; padding: 8px 16px; }
QPushButton:hover { border-color: #7DD3FC; }
QPushButton#sendButton { background: #7DD3FC; color: #0B0D12; font-weight: 600; }
QPushButton#sendButton:disabled { background: #252A38; color: #94A3B8; }
QLabel { color: #E5E7EB; }
QLabel#statusOk { color: #A3E635; }
QLabel#statusWarn { color: #FBBF24; }
QLabel#statusError { color: #FB7185; }
QFrame#dropZone {
    border: 2px dashed #252A38;
    border-radius: 16px;
    background: #141821;
}
QFrame#dropZone[active="true"] { border-color: #7DD3FC; background: #1B2030; }
```

**Step 3:** Commit.
```bash
git add src/lbb/ui/
git commit -m "feat(ui): dark theme tokens + QSS"
```

### Task 5.2: Status pill widget

**Files:**
- Create: `src/lbb/ui/widgets/__init__.py`
- Create: `src/lbb/ui/widgets/status_pill.py`
- Create: `tests/ui/__init__.py`
- Create: `tests/ui/test_status_pill.py`

**Step 1 (test):**
```python
# tests/ui/test_status_pill.py
import pytest
from lbb.ui.widgets.status_pill import StatusPill

@pytest.fixture
def app(qtbot):
    return qtbot

def test_starts_disconnected(qtbot):
    p = StatusPill()
    qtbot.addWidget(p)
    assert p.objectName() == "statusError"
    assert "Not connected" in p.text()

def test_sets_ready_state(qtbot):
    p = StatusPill()
    qtbot.addWidget(p)
    p.set_running(True)
    assert p.objectName() == "statusOk"
    assert "Ready" in p.text()
```

**Step 2:** Run — ImportError.

**Step 3 (impl):**
```python
# src/lbb/ui/widgets/status_pill.py
from PySide6.QtWidgets import QLabel

class StatusPill(QLabel):
    def __init__(self):
        super().__init__("● LightBurn — Not connected")
        self.setObjectName("statusError")

    def set_running(self, running: bool) -> None:
        if running:
            self.setText("● LightBurn — Ready")
            self.setObjectName("statusOk")
        else:
            self.setText("● LightBurn — Not connected")
            self.setObjectName("statusError")
        self.style().unpolish(self); self.style().polish(self)  # re-apply QSS
```

**Step 4:** Run — 2 passed.

**Step 5:** Commit.
```bash
git add src/lbb/ui/widgets/status_pill.py tests/ui/
git commit -m "feat(ui): StatusPill widget"
```

### Task 5.3: Drop zone widget

**Files:**
- Create: `src/lbb/ui/widgets/drop_zone.py`
- Create: `tests/ui/test_drop_zone.py`

**Step 1 (test):**
```python
# tests/ui/test_drop_zone.py
from PySide6.QtCore import Qt, QMimeData, QUrl, QPoint
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from lbb.ui.widgets.drop_zone import DropZone

def test_emits_dropped_signal(qtbot, tmp_path):
    pdf = tmp_path / "LB-X__demo.pdf"; pdf.write_bytes(b"%PDF-1.4")
    zone = DropZone()
    qtbot.addWidget(zone)
    received = []
    zone.pdf_dropped.connect(lambda p: received.append(p))
    mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(pdf))])
    enter = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    zone.dragEnterEvent(enter)
    drop = QDropEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    zone.dropEvent(drop)
    assert received == [pdf]
```

**Step 2:** Run — ImportError.

**Step 3 (impl):**
```python
# src/lbb/ui/widgets/drop_zone.py
from pathlib import Path
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

class DropZone(QFrame):
    pdf_dropped = Signal(Path)

    def __init__(self):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self._label = QLabel("⤓  Drop PDF here\nor click to browse\n\nfilename must contain SKU")
        self._label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label)

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if any(u.toLocalFile().lower().endswith(".pdf") for u in urls):
            event.acceptProposedAction()
            self.setProperty("active", True)
            self.style().unpolish(self); self.style().polish(self)

    def dragLeaveEvent(self, event):
        self.setProperty("active", False)
        self.style().unpolish(self); self.style().polish(self)

    def dropEvent(self, event):
        for u in event.mimeData().urls():
            local = u.toLocalFile()
            if local.lower().endswith(".pdf"):
                self.pdf_dropped.emit(Path(local))
                break
        self.setProperty("active", False)
        self.style().unpolish(self); self.style().polish(self)
```

**Step 4:** Run — 1 passed.

**Step 5:** Commit.
```bash
git add src/lbb/ui/widgets/drop_zone.py tests/ui/test_drop_zone.py
git commit -m "feat(ui): DropZone widget with QSS active state"
```

### Task 5.4: Home view

**Files:**
- Create: `src/lbb/ui/views/__init__.py`
- Create: `src/lbb/ui/views/home.py`

Wire StatusPill + DropZone. Poll LightBurn every 2s via QTimer. Pass dropped PDF to a handler callback.

**Step 1 (impl — no new test; manual smoke):**
```python
# src/lbb/ui/views/home.py
from pathlib import Path
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from lbb.ui.widgets.drop_zone import DropZone
from lbb.ui.widgets.status_pill import StatusPill
from lbb.ports.lightburn import LightBurnPort

class HomeView(QWidget):
    pdf_chosen = Signal(Path)
    open_admin = Signal()
    open_audit = Signal()

    def __init__(self, lightburn: LightBurnPort):
        super().__init__()
        self._lb = lightburn
        layout = QVBoxLayout(self)
        # Header
        header = QHBoxLayout()
        title = QLabel("◐  LightBurn Bridge")
        self.status = StatusPill()
        header.addWidget(title); header.addStretch(); header.addWidget(self.status)
        layout.addLayout(header)
        # Drop zone
        self.zone = DropZone()
        self.zone.pdf_dropped.connect(self.pdf_chosen.emit)
        layout.addWidget(self.zone, stretch=1)
        # Bottom buttons
        bottom = QHBoxLayout()
        admin = QPushButton("⚙ Admin"); admin.clicked.connect(self.open_admin.emit)
        audit = QPushButton("📋 Audit"); audit.clicked.connect(self.open_audit.emit)
        bottom.addStretch(); bottom.addWidget(admin); bottom.addWidget(audit)
        layout.addLayout(bottom)
        # Status poll
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(2000)
        self._poll()

    def _poll(self) -> None:
        self.status.set_running(self._lb.is_running())
```

**Step 2:** Commit.
```bash
git add src/lbb/ui/views/home.py
git commit -m "feat(ui): HomeView (status + drop zone + nav)"
```

### Task 5.5: Job preview view

**Files:**
- Create: `src/lbb/ui/views/job_preview.py`

Renders PDF thumbnail (left), profile metadata (right), preflight checks (left-bottom). Send button enabled only if all preflight checks pass.

**Step 1 (impl):**
```python
# src/lbb/ui/views/job_preview.py
from pathlib import Path
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame,
)
from lbb.core.models import SkuProfile
from lbb.core.preflight import PreflightResult

class JobPreviewView(QWidget):
    send_requested = Signal()
    cancel_requested = Signal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        body = QHBoxLayout()
        self.thumb = QLabel("Loading…"); self.thumb.setFixedSize(360, 360); self.thumb.setAlignment(Qt.AlignCenter)
        body.addWidget(self.thumb)
        right = QVBoxLayout()
        self.sku_label = QLabel(); self.sku_label.setStyleSheet("font-size: 18pt;")
        self.template_label = QLabel(); self.material_label = QLabel()
        self.params_label = QLabel()
        self.preflight_label = QLabel()
        right.addWidget(QLabel("SKU detected")); right.addWidget(self.sku_label)
        right.addSpacing(12); right.addWidget(QLabel("Product template")); right.addWidget(self.template_label)
        right.addSpacing(12); right.addWidget(QLabel("Material profile")); right.addWidget(self.material_label)
        right.addWidget(self.params_label); right.addStretch()
        right.addWidget(self.preflight_label)
        body.addLayout(right)
        outer.addLayout(body)
        # Buttons
        btn_row = QHBoxLayout()
        self.cancel = QPushButton("✕ Cancel"); self.cancel.clicked.connect(self.cancel_requested.emit)
        self.send = QPushButton("⏎ Send →"); self.send.setObjectName("sendButton")
        self.send.clicked.connect(self.send_requested.emit)
        btn_row.addStretch(); btn_row.addWidget(self.cancel); btn_row.addWidget(self.send)
        outer.addLayout(btn_row)

    def populate(self, *, thumbnail_png: bytes, profile: SkuProfile, preflight: PreflightResult) -> None:
        pix = QPixmap(); pix.loadFromData(thumbnail_png, "PNG")
        self.thumb.setPixmap(pix.scaled(self.thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.sku_label.setText(profile.sku.value)
        self.template_label.setText(f"{profile.template.name} ({profile.template.canvas_w_mm:.0f} × {profile.template.canvas_h_mm:.0f} mm)")
        self.material_label.setText(profile.material.name)
        self.params_label.setText(f"Library: {profile.material.clb_library}\nEntry: {profile.material.clb_entry}")
        if preflight.ok:
            self.preflight_label.setText("✓ All preflight checks passed")
            self.preflight_label.setObjectName("statusOk")
            self.send.setEnabled(True)
        else:
            self.preflight_label.setText("✕ Preflight failed:\n• " + "\n• ".join(preflight.reasons))
            self.preflight_label.setObjectName("statusError")
            self.send.setEnabled(False)
        self.preflight_label.style().unpolish(self.preflight_label); self.preflight_label.style().polish(self.preflight_label)
```

**Step 2:** Commit.
```bash
git add src/lbb/ui/views/job_preview.py
git commit -m "feat(ui): JobPreviewView with preflight gating"
```

### Task 5.6: Main window + controller

**Files:**
- Create: `src/lbb/ui/main_window.py`
- Create: `src/lbb/__main__.py`

**Step 1 (impl) — main window:**
```python
# src/lbb/ui/main_window.py
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox
from lbb.app.pipeline import PipelineDeps, run_pipeline
from lbb.app.job import Job
from lbb.core.extractor import extract_sku
from lbb.core.errors import SkuNotFound, LbbError
from lbb.ui.views.home import HomeView
from lbb.ui.views.job_preview import JobPreviewView

class MainWindow(QMainWindow):
    def __init__(self, deps: PipelineDeps):
        super().__init__()
        self.deps = deps
        self.setWindowTitle("LightBurn Bridge")
        self.resize(960, 640)
        self.stack = QStackedWidget()
        self.home = HomeView(deps.lightburn)
        self.preview = JobPreviewView()
        self.stack.addWidget(self.home); self.stack.addWidget(self.preview)
        self.setCentralWidget(self.stack)
        self.home.pdf_chosen.connect(self._on_pdf)
        self.preview.cancel_requested.connect(lambda: self.stack.setCurrentWidget(self.home))
        self.preview.send_requested.connect(self._send)
        self._pending_pdf: Path | None = None
        self._pending_profile = None

    def _on_pdf(self, path: Path) -> None:
        try:
            sku = extract_sku(path.name)
        except LbbError as e:
            QMessageBox.warning(self, "Filename problem", str(e)); return
        profile = self.deps.repo.get(sku)
        if not profile:
            QMessageBox.warning(self, "Unknown SKU",
                f"No profile for {sku.value}. Add one in Admin first (MVP).")
            return
        info = self.deps.pdf.read_info(path)
        from lbb.core.preflight import run_preflight
        pf = run_preflight(info, canvas_mm=(profile.template.canvas_w_mm, profile.template.canvas_h_mm))
        png = self.deps.pdf.render_thumbnail_png(path, 720)
        self.preview.populate(thumbnail_png=png, profile=profile, preflight=pf)
        self._pending_pdf, self._pending_profile = path, profile
        self.stack.setCurrentWidget(self.preview)

    def _send(self) -> None:
        if not self._pending_pdf: return
        result = run_pipeline(Job(source_pdf=self._pending_pdf), self.deps)
        if result.ok:
            QMessageBox.information(self, "Sent",
                f"Loaded into LightBurn:\n{result.output_path.name}\n\nPress Start on the laser.")
            self.stack.setCurrentWidget(self.home)
        else:
            QMessageBox.critical(self, "Send failed", result.error or "Unknown error")
```

**Step 2 (impl) — entrypoint:**
```python
# src/lbb/__main__.py
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from lbb.app.container import build_pipeline_deps, AppPaths
from lbb.ui.main_window import MainWindow

def _resource(name: str) -> Path:
    return Path(__file__).parent / "ui" / "theme" / name

def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(_resource("app.qss").read_text())
    paths = AppPaths(
        db_path=Path.home() / ".lightburn-bridge" / "profiles.sqlite",
        temp_dir=Path.home() / ".lightburn-bridge" / "jobs",
    )
    deps = build_pipeline_deps(paths)
    window = MainWindow(deps)
    window.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
```

**Step 3:** Smoke test by hand.
```bash
uv run python -m lbb
```
Expected: Window opens with dark theme. Drag a non-PDF — no action. Drag a PDF named `LB-X__demo.pdf` — warning popup (no profile yet, that's correct).

**Step 4:** Commit.
```bash
git add src/lbb/ui/main_window.py src/lbb/__main__.py
git commit -m "feat(ui): MainWindow + entrypoint, end-to-end smoke runnable"
```

### Task 5.7: Admin view (minimal CRUD)

**Files:**
- Create: `src/lbb/ui/views/admin.py`
- Modify: `src/lbb/ui/main_window.py` (add Admin route)

For MVP, three sortable QTableView tabs: SKUs, Templates, Materials. Inline-editable. Add/Delete buttons.

**Step 1 (impl outline — leave detailed code to the engineer; the pattern is standard PySide6 QTableView + QAbstractTableModel backed by the repository):**
```python
# src/lbb/ui/views/admin.py
from PySide6.QtWidgets import QWidget, QTabWidget, QVBoxLayout
from lbb.ports.repository import ProfileRepository

class AdminView(QWidget):
    def __init__(self, repo: ProfileRepository):
        super().__init__()
        self._repo = repo
        tabs = QTabWidget()
        tabs.addTab(_SkuTab(repo), "SKUs")
        tabs.addTab(_TemplateTab(repo), "Templates")
        tabs.addTab(_MaterialTab(repo), "Materials")
        layout = QVBoxLayout(self); layout.addWidget(tabs)

# Implement each tab as a QTableView + QAbstractTableModel backed by repo.list_*().
# Provide "Add row" and "Delete row" buttons. Edits trigger repo.upsert_*().
# (Engineer: ~150 lines total. Standard Qt pattern.)
```

**Step 2:** Wire route in `MainWindow.__init__`:
```python
from lbb.ui.views.admin import AdminView
self.admin = AdminView(deps.repo)
self.stack.addWidget(self.admin)
self.home.open_admin.connect(lambda: self.stack.setCurrentWidget(self.admin))
```

**Step 3:** Smoke test — open admin, add a template + material, add a SKU profile. Drop a matching PDF on home — preview screen should now appear.

**Step 4:** Commit.
```bash
git add src/lbb/ui/views/admin.py src/lbb/ui/main_window.py
git commit -m "feat(ui): Admin view (SKU/Template/Material tabs)"
```

---

## Phase 6 — Demo seed + packaging

### Task 6.1: Seed 5 demo SKUs

**Files:**
- Create: `scripts/seed_demo.py`
- Create: `templates/` (commit 5 hand-authored `.lbrn2` templates)
- Create: `tests/fixtures/pdfs/` (5 matching demo PDFs)

**Step 1:** Write seed script:
```python
# scripts/seed_demo.py
from pathlib import Path
from lbb.adapters.sqlite_repo import SqliteProfileRepository
from lbb.core.models import Sku, Material, Template, SkuProfile

DB = Path.home() / ".lightburn-bridge" / "profiles.sqlite"
TEMPLATES = Path(__file__).parent.parent / "templates"

def main():
    repo = SqliteProfileRepository(DB)
    materials = {
        "leather": repo.upsert_material(Material(0, "Leather 2mm — Veg Tan", "default.clb", "LeatherVT")),
        "ss":      repo.upsert_material(Material(0, "Stainless 304", "default.clb", "SS304")),
        "wood":    repo.upsert_material(Material(0, "Birch Plywood 3mm", "default.clb", "Birch3")),
    }
    templates = {
        "wallet-s":   repo.upsert_template(Template(0, "Wallet — Small",     str(TEMPLATES/"wallet-small.lbrn2"),   95, 110)),
        "wallet-m":   repo.upsert_template(Template(0, "Wallet — Medium",    str(TEMPLATES/"wallet-medium.lbrn2"), 110, 140)),
        "tumbler-20": repo.upsert_template(Template(0, "Tumbler 20oz",       str(TEMPLATES/"tumbler-20oz.lbrn2"),  220,  75)),
        "tag":        repo.upsert_template(Template(0, "Pet tag — Round",    str(TEMPLATES/"tag-round.lbrn2"),      50,  50)),
        "plaque":     repo.upsert_template(Template(0, "Plaque — Rectangle", str(TEMPLATES/"plaque-rect.lbrn2"),   200, 150)),
    }
    skus = [
        ("LB-WALLET-LEATHER-S",  "wallet-s",   "leather"),
        ("LB-WALLET-LEATHER-M",  "wallet-m",   "leather"),
        ("LB-TUMBLER-20OZ-SS",   "tumbler-20", "ss"),
        ("LB-TAG-PET-WOOD-R",    "tag",        "wood"),
        ("LB-PLAQUE-WOOD-RECT",  "plaque",     "wood"),
    ]
    for s, t, m in skus:
        repo.upsert(SkuProfile(Sku(s), templates[t], materials[m], {}))
    print(f"Seeded {len(skus)} SKUs into {DB}")

if __name__ == "__main__":
    main()
```

**Step 2:** Hand-author templates (manual LightBurn step — Task 3.1 repeated for the other 4 SKUs).

**Step 3:** Generate matching demo PDFs (vector, palette-correct strokes, filename matches SKU).

**Step 4:** Run seed + smoke test entire flow with LightBurn open.
```bash
uv run python scripts/seed_demo.py
uv run python -m lbb
# drag tests/fixtures/pdfs/LB-WALLET-LEATHER-S__demo.pdf → preview → send → LightBurn opens it
```

**Step 5:** Commit.
```bash
git add scripts/ templates/ tests/fixtures/pdfs/
git commit -m "feat: 5-SKU demo seed with templates + matching PDFs"
```

### Task 6.2: PyInstaller packaging

**Files:**
- Create: `packaging/lbb.spec`
- Modify: `.github/workflows/ci.yml` (add release job)

**Step 1:** Write spec:
```python
# packaging/lbb.spec
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['../src/lbb/__main__.py'],
    pathex=['../src'],
    binaries=[],
    datas=[('../src/lbb/ui/theme/app.qss', 'lbb/ui/theme/')],
    hiddenimports=collect_submodules('PySide6') + ['pypdfium2', 'lxml'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
          name='LightBurn Bridge', console=False)
```

**Step 2:** Test local build.
```bash
uv run pyinstaller packaging/lbb.spec --clean
# Verify dist/LightBurn Bridge launches.
```

**Step 3:** Commit.
```bash
git add packaging/
git commit -m "chore: PyInstaller spec"
```

### Task 6.3: Designer PDF spec document

**Files:**
- Create: `docs/designer-pdf-spec.md`

**Step 1:** Write a one-pager covering:
- Filename: `<SKU>__<anything>.pdf` (two underscores)
- Vector-only (no raster), no embedded fonts (outline text)
- Stroke colors must be from LightBurn's 30-color palette (list the hex values from `core/palette.py`)
- Canvas size matches the product template (table of SKU → canvas size)
- One page only
- Common pitfalls: opacity (not supported on cut layers), gradients (not supported), text-as-text (must be outlined)

**Step 2:** Commit.
```bash
git add docs/designer-pdf-spec.md
git commit -m "docs: designer PDF spec contract"
```

---

## Acceptance criteria (MVP demo checklist)

The client demo passes if **all** of these are true:

- [ ] `uv run python -m lbb` launches a dark-themed window on Win, Mac, and Linux
- [ ] Status pill turns green within 2s when LightBurn is open; red when LightBurn is closed
- [ ] Dragging `LB-WALLET-LEATHER-S__demo.pdf` (or any of the 5 seeded SKUs) onto the drop zone opens the preview screen showing: SKU, template name, material name, PDF thumbnail, "all preflight checks passed"
- [ ] Clicking **Send →** generates a `.lbrn2`, LightBurn opens it, layers/material parameters match expectations
- [ ] Operator presses Start on the laser physically — engraving proceeds correctly
- [ ] Dragging `unknown__file.pdf` shows "Unknown SKU" warning (operator can add via Admin)
- [ ] Dragging a raster-only PDF blocks Send and lists "PDF contains raster content" as reason
- [ ] Admin tab lists 5 SKUs / N materials / M templates; inline editing works; new SKU can be added and immediately used
- [ ] CI is green on all three OS matrix entries
- [ ] All unit + integration tests pass; e2e tests pass on at least one developer's machine with real LightBurn
- [ ] `docs/designer-pdf-spec.md` exists and has been reviewed by the client's design team

---

## Out-of-scope for MVP (deferred to v1/v2)

- Audit log persistence (in-memory only for MVP)
- CSV bulk import/export
- Auto-update channel
- Code signing
- Watched-folder mode
- E-commerce integration
- Multi-workstation central settings
- Curve/Bezier path support (MVP supports straight-line paths only — covers the 80% case for engraving)
- Multi-page PDFs
