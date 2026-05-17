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
    """LightBurn isn't responding — process not found or UDP listener silent."""

    def __init__(self, msg: str | None = None):
        super().__init__(msg or "LightBurn isn't running. Open LightBurn and try again.")


class LightBurnRejected(LbbError):
    def __init__(self, response: bytes | str):
        super().__init__(f"LightBurn rejected request: {response!r}")
        self.response = response
