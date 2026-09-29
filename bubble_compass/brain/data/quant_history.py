"""Expanding-window layer history for Bubble Compass (PIT-safe)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from bubble_compass.brain.data.pit_store import PITStore
from bubble_compass.brain.engines.dlinear import DLinearEngine
from bubble_compass.brain.engines.lppls_engine import LPPLSEngine
from bubble_compass.brain.engines.macro_debt import MacroDebtEngine
from bubble_compass.brain.engines.psy_bsadf import PSYBubbleTest
from bubble_compass.brain.engines.regime_rl import RegimeRLEngine
from bubble_compass.brain.engines.sentiment import SentimentEngine


def _price_series(store: PITStore, asset: str, as_of: pd.Timestamp) -> pd.Series:
    df = store.query_as_of(asset, "price", as_of)
    if df.empty:
        return pd.Series(dtype=float)
    close_col = "close" if "close" in df.columns else "value"
    if close_col not in df.columns:
        return pd.Series(dtype=float)
    s = pd.Series(
        pd.to_numeric(df[close_col], errors="coerce").values,
        index=pd.to_datetime(df["effective_date"]),
    ).dropna()
    return s.sort_index()


def _macro_value(store: PITStore, series_id: str, as_of: pd.Timestamp) -> float | None:
    df = store.query_as_of(series_id, "macro", as_of)
    if df.empty:
        return None
    col = "value" if "value" in df.columns else "close"
    if col not in df.columns:
        return None
    return float(pd.to_numeric(df[col], errors="coerce").dropna().iloc[-1])


def run_history_for_asset(
    *,
    asset: str,
    pit_dir: Path,
    cache_dir: Path,
    start: pd.Timestamp,
    end: pd.Timestamp,
    step_days: int = 1,
    debt_series: str = "US_DEBT_TO_GDP",
    headlines: pd.DataFrame | None = None,
) -> dict[str, Path]:
    store = PITStore(Path(pit_dir))
    cache_dir = Path(cache_dir)
    dates = pd.bdate_range(start, end, freq=f"{max(1, step_days)}B")
    rows: dict[str, list[dict[str, Any]]] = {
        "dlinear": [],
        "bsadf": [],
        "lppls": [],
        "sentiment": [],
        "regime": [],
        "macro_debt": [],
    }
    sentiment_unavailable = headlines is None or (
        isinstance(headlines, pd.DataFrame) and headlines.empty
    )
    # Reuse PSY critical-value cache across as_of dates (expensive MC once).
    # n_simulations=0 → asymptotic CV; stride sparsifies recursive windows.
    psy = PSYBubbleTest(n_simulations=0, window_stride=5)
    max_engine_lookback = 120

    for as_of in dates:
        as_of_ts = pd.Timestamp(as_of)
        prices = _price_series(store, asset, as_of_ts)
        if len(prices) < 30:
            continue
        if len(prices) > max_engine_lookback:
            prices = prices.iloc[-max_engine_lookback:]

        lookback = min(96, len(prices))
        kernel = min(25, max(5, lookback // 3))
        dlinear = DLinearEngine(lookback=lookback, kernel_size=kernel)
        try:
            dlinear.fit(prices)
        except Exception:
            pass
        d_out = dlinear.predict(prices, as_of_ts)
        rows["dlinear"].append(
            {
                "as_of": as_of_ts,
                "trend": d_out.trend,
                "residual": d_out.residual,
                "residual_z": d_out.residual_z,
            }
        )

        p_out = psy.test(prices, as_of_ts)
        rows["bsadf"].append(
            {
                "as_of": as_of_ts,
                "bsadf_stat": p_out.bsadf_stat,
                "critical_value": p_out.critical_value,
                "bubble_flag": bool(p_out.bubble_flag),
            }
        )

        win = min(60, max(20, len(prices)))
        lppls = LPPLSEngine(window_sizes=[win])
        l_out = lppls.compute(prices, as_of_ts)
        rows["lppls"].append(
            {
                "as_of": as_of_ts,
                "lpp_confidence": l_out.lpp_confidence,
                "tc_estimate": getattr(l_out, "tc_estimate", None),
            }
        )

        sent = SentimentEngine()
        if sentiment_unavailable:
            rows["sentiment"].append(
                {
                    "as_of": as_of_ts,
                    "sentiment_level": None,
                    "sentiment_velocity": None,
                    "unavailable": True,
                }
            )
            sent_vel = 0.0
        else:
            s_out = sent.compute(headlines, as_of_ts)  # type: ignore[arg-type]
            rows["sentiment"].append(
                {
                    "as_of": as_of_ts,
                    "sentiment_level": s_out.sentiment_level,
                    "sentiment_velocity": s_out.sentiment_velocity,
                    "unavailable": False,
                }
            )
            sent_vel = float(s_out.sentiment_velocity or 0.0)

        rets = prices.pct_change().dropna()
        r_out = RegimeRLEngine().predict(
            d_out.residual_z if pd.notna(d_out.residual_z) else 0.0,
            p_out.bsadf_stat if pd.notna(p_out.bsadf_stat) else 0.0,
            p_out.critical_value if pd.notna(p_out.critical_value) else 1.0,
            l_out.lpp_confidence,
            sent_vel,
            rets.tail(20),
            as_of_ts,
        )
        rows["regime"].append(
            {
                "as_of": as_of_ts,
                "regime_state": r_out.regime_state.name.lower(),
                "regime_confidence": r_out.regime_confidence,
                "boom_probability": r_out.boom_probability,
                "bust_probability": r_out.bust_probability,
            }
        )

        debt = _macro_value(store, debt_series, as_of_ts)
        if debt is not None:
            m_out = MacroDebtEngine().compute(debt, as_of_ts)
            rows["macro_debt"].append(
                {
                    "as_of": as_of_ts,
                    "debt_to_gdp": m_out.debt_to_gdp,
                    "gap": m_out.gap,
                    "threshold_breach": m_out.threshold_breach,
                }
            )

    written: dict[str, Path] = {}
    for layer, records in rows.items():
        dest_dir = cache_dir / "history" / layer
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{asset}.parquet"
        if records:
            pd.DataFrame(records).to_parquet(dest, index=False)
        else:
            pd.DataFrame(columns=["as_of"]).to_parquet(dest, index=False)
        written[layer] = dest

        # Also refresh _latest.json tip for API compatibility.
        if records:
            tip = {k: v for k, v in records[-1].items() if k != "as_of"}
            # Convert timestamps / numpy types for JSON
            tip_json = {
                k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in tip.items()
            }
            latest_dir = cache_dir / layer
            latest_dir.mkdir(parents=True, exist_ok=True)
            import json

            (latest_dir / f"{asset}_latest.json").write_text(
                json.dumps(tip_json), encoding="utf-8"
            )

    return written
