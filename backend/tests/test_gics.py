from screener.gics import to_gics_sector, YAHOO_TO_GICS_SECTOR


def test_renamed_sectors_map_to_gics():
    # the five Yahoo labels that differ from GICS
    assert to_gics_sector("Technology") == "Information Technology"
    assert to_gics_sector("Financial Services") == "Financials"
    assert to_gics_sector("Consumer Cyclical") == "Consumer Discretionary"
    assert to_gics_sector("Consumer Defensive") == "Consumer Staples"
    assert to_gics_sector("Healthcare") == "Health Care"
    assert to_gics_sector("Basic Materials") == "Materials"


def test_already_gics_sectors_pass_through():
    for s in ("Industrials", "Energy", "Utilities", "Real Estate", "Communication Services"):
        assert to_gics_sector(s) == s


def test_unknown_sector_passes_through_verbatim():
    # never blank out a value we don't recognise — show it as-is
    assert to_gics_sector("Some New Yahoo Sector") == "Some New Yahoo Sector"


def test_none_and_blank_return_none():
    assert to_gics_sector(None) is None
    assert to_gics_sector("") is None


def test_map_covers_eleven_gics_sectors():
    # the mapped-to values, unioned with the pass-through GICS names, are the 11
    assert set(YAHOO_TO_GICS_SECTOR.values()) <= {
        "Energy", "Materials", "Industrials", "Consumer Discretionary",
        "Consumer Staples", "Health Care", "Financials",
        "Information Technology", "Communication Services", "Utilities", "Real Estate",
    }
