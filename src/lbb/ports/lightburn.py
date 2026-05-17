from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LBStatus:
    running: bool
    busy: bool = False
    raw: str = ""


class LightBurnPort(Protocol):
    def is_running(self) -> bool: ...

    def load_file(self, path: Path) -> None: ...

    def status(self) -> LBStatus: ...
