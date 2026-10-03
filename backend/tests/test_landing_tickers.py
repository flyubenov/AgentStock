import json
from pathlib import Path

import pytest

from landing.tickers import normalize, sec_key

_CASES = json.loads((Path(__file__).resolve().parents[2]
                     / "frontend/src/landing/ticker-cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("raw,want", _CASES)
def test_normalize_matches_the_shared_table(raw, want):
    assert normalize(raw) == want


def test_sec_key_uses_the_dash_form():
    assert sec_key("BRK.B") == "BRK-B"
    assert sec_key("NVDA") == "NVDA"
