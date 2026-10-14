"""Snap a requested day to a date the run actually stored."""

from scripts.export_sandbox_bundle import snap_on_or_before


def test_snap_uses_the_stored_day_on_or_before():
    dates = ["2008-01-02", "2008-09-15", "2020-03-16"]
    assert snap_on_or_before(dates, "2008-09-15") == "2008-09-15"
    assert snap_on_or_before(dates, "2008-09-20") == "2008-09-15"
    assert snap_on_or_before(dates, "2000-01-01") is None
