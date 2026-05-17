import pytest
from hypothesis import given
from hypothesis import strategies as st
from lbb.core.errors import LbbError
from lbb.core.extractor import extract_sku


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

    @given(
        sku=st.text(
            alphabet=st.characters(categories=("Lu", "Ll", "Nd"), include_characters="-"),
            min_size=1,
            max_size=40,
        )
    )
    def test_roundtrip_property(self, sku):
        """Any non-empty SKU placed before '__name.pdf' must roundtrip."""
        assert extract_sku(f"{sku}__x.pdf").value == sku
