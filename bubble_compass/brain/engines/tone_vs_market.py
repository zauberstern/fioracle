"""Management tone vs market pricing gap (-100..100).

Positive gap: market more skeptical than management narrative.
When call transcripts are missing, use a VIX + HY OAS change proxy (documented).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ToneVsMarketResult:
    unavailable: bool
    value: float | None
    source: str | None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "unavailable": self.unavailable,
            "value": self.value,
            "source": self.source,
            "reason": self.reason,
        }


def _clamp_gap(x: float) -> float:
    return float(np.clip(x, -100.0, 100.0))


def compute_tone_vs_market_gap(
    *,
    management_tone: float | None = None,
    hy_oas_level: float | None = None,
    hy_oas_change_20d: float | None = None,
    vix: float | None = None,
    vix_long_run_mean: float = 20.0,
    vix_long_run_std: float = 8.0,
    hy_oas_change_scale_bps: float = 50.0,
) -> ToneVsMarketResult:
    """Compute tone vs market divergence on [-100, 100].

    Transcript path: ``management_tone`` in [-1, 1] (optimistic positive).
    Proxy path: rising VIX and widening HY OAS imply market skepticism without calls.
    """
    if management_tone is not None:
        if hy_oas_change_20d is None and hy_oas_level is None and vix is None:
            return ToneVsMarketResult(
                unavailable=True,
                value=None,
                source=None,
                reason="management_tone requires a market anchor (VIX or HY OAS)",
            )
        market_skeptic = 0.0
        if vix is not None and vix_long_run_std > 0:
            market_skeptic += (float(vix) - vix_long_run_mean) / vix_long_run_std
        if hy_oas_change_20d is not None and hy_oas_change_scale_bps > 0:
            market_skeptic += float(hy_oas_change_20d) / hy_oas_change_scale_bps
        elif hy_oas_level is not None:
            market_skeptic += (float(hy_oas_level) - 400.0) / 200.0
        gap = 100.0 * (market_skeptic - float(management_tone))
        return ToneVsMarketResult(
            unavailable=False,
            value=_clamp_gap(gap),
            source="transcript_vs_market",
            reason=None,
        )

    if vix is None or (hy_oas_change_20d is None and hy_oas_level is None):
        return ToneVsMarketResult(
            unavailable=True,
            value=None,
            source=None,
            reason="need VIX plus HY OAS level or 20d change when transcripts absent",
        )

    market_skeptic = 0.0
    if vix_long_run_std > 0:
        market_skeptic += (float(vix) - vix_long_run_mean) / vix_long_run_std
    if hy_oas_change_20d is not None and hy_oas_change_scale_bps > 0:
        market_skeptic += float(hy_oas_change_20d) / hy_oas_change_scale_bps
    else:
        market_skeptic += (float(hy_oas_level) - 400.0) / 200.0

    gap = -50.0 * market_skeptic
    return ToneVsMarketResult(
        unavailable=False,
        value=_clamp_gap(gap),
        source="vix_oas_proxy",
        reason=None,
    )
