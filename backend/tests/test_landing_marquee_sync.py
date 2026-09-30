import re
from pathlib import Path

import main


def test_backend_prewarms_exactly_the_frontend_compare_chips():
    # Two hand-kept copies of one list drift: a chip missing from the backend list is
    # silently never pre-warmed, so its first visitor after each deploy waits.
    src = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "landing"
           / "components" / "Hero.tsx").read_text(encoding="utf-8")
    m = re.search(r"export const COMPARE_TICKERS = \[([^\]]*)\]", src)
    assert m, "COMPARE_TICKERS not found in Hero.tsx"
    chips = re.findall(r"'([A-Z][A-Z.\-]*)'", m.group(1))
    assert chips == main.LANDING_MARQUEE_TICKERS
