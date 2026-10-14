# Meridian offline holes (this pass)

Documented gaps after max-offline landing. Not bugs; entitled live feeds are out of scope.

| Hole | Status |
|------|--------|
| Headline / Marketaux / FinBERT tape | Unavailable; sentiment layer marked `unavailable` |
| Compustat / issuer CDS / PD points | Not offline; PD / cliff / breach panels stay gated |
| Live WRDS OptionMetrics / IBES pulls | Offline extracts only |
| Empty lake series | `US_EPU`, `US_CORE_CPI` parquet present but 0 rows |
| Live LSEG / Refinitiv IPA surfaces | Directory blobs skipped; aggregate panels only |
| `lppls` package | Declared in `pyproject.toml`; if missing at runtime, LPPLS writes `unavailable` (no slope surrogate) |
| GitHub Pages go-live / `git push` | Not part of this pass |
| Cash PSY stretch flag | On for the whole tape; the weekly page does not rank cash as a bubble |
| 2026 pad zeros | Last 2026 rows are flat zeros after series stop; a zero print is not a quiet market day |
| HY OAS unit shift (~2022-02-01) | About 3 then about 360; credit answer is one shared series, not eight sleeves |

Wired offline: lake ancillaries with data (`US_10Y2Y_SPREAD`, `US_2Y_YIELD`, `US_RISK_FREE_RATE`), WRDS TRACE median + FRB/CRSP panels, LSEG US10Y / SPX PIT n / Worldscope leverage median / IBES rec mean. Macro lags aligned to `config/config.yaml` via `data/cache/macro_lags_compass.json`.

Product history tape rebuilt at 21-business-day stride with PSY `method=coarse_screen` (asymptotic CV + window stride).
