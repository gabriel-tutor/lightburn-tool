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

    def close_running(self) -> None:
        """Force-terminate the running LightBurn instance, if any.

        Used by the "close previous job" flow so the next dispatch lands
        in a fresh LightBurn workspace without the "Save changes?" prompt.
        Safe to call when LightBurn isn't running — implementations must
        not raise in that case.
        """
        ...
