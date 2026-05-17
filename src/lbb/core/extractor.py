from pathlib import Path

from lbb.core.errors import LbbError
from lbb.core.models import Sku

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
