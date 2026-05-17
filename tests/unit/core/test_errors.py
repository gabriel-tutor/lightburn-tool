from lbb.core.errors import (
    LbbError,
    LightBurnNotRunning,
    LightBurnRejected,
    PreflightFailed,
    SkuNotFound,
)


def test_hierarchy():
    assert issubclass(SkuNotFound, LbbError)
    assert issubclass(PreflightFailed, LbbError)
    assert issubclass(LightBurnNotRunning, LbbError)
    assert issubclass(LightBurnRejected, LbbError)


def test_preflight_carries_reasons():
    e = PreflightFailed(reasons=["not vector", "stroke color #ABC123 not in palette"])
    assert len(e.reasons) == 2
