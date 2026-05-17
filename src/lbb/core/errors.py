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
    """LightBurn does not respond to PING on UDP 127.0.0.1:19840."""


class LightBurnRejected(LbbError):
    def __init__(self, response: bytes):
        super().__init__(f"LightBurn rejected request: {response!r}")
        self.response = response
