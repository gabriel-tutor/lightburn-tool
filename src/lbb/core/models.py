from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Sku:
    value: str

    def __post_init__(self) -> None:
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
