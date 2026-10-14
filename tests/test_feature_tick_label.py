"""Plain tick labels for the saved feature-importance chart."""

from src.core.diagnostics import feature_tick_label


def test_feature_tick_label_names_the_saved_columns():
    assert feature_tick_label("macro_unemployment_change_ewma21") == (
        "Unemployment change, 21-day"
    )
    assert feature_tick_label("macro_vix_logdiff_ewma63") == "VIX change, 63-day"
    assert feature_tick_label("avg_return_hl10") == "10-day average return"
    assert feature_tick_label("log_dd_hl5") == "5-day drawdown"


def test_feature_tick_label_keeps_an_unknown_id():
    assert feature_tick_label("macro_not_a_real_column") == "macro_not_a_real_column"
