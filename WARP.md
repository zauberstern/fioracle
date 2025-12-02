# FIOracle codebase reference (WARP)

This document exhaustively maps the codebase: files, classes, functions, key variables, configuration, data flow, and how parts are wired together. Treat this as the single source of truth before making changes.

Contents
- Overview and layout
- Configuration (config/config.yaml)
- Core modules
  - utils.py
  - data.py
  - features.py
  - regimes.py
  - diagnostics.py
  - portfolio.py
  - evaluation.py
  - benchmarks.py
- Visualizations
  - advanced_analytics.py
  - historical_series.py
  - period_analysis.py
  - regime_drivers.py
  - robustness_grid.py
  - tail_hedge_analysis.py
  - vix_analysis.py
- Top-level runner (main.py)
- Data flow and process diagram
- Change audit: regimes.py (hyperparameter tuning + early stopping)

---

## Overview and layout

```
config/config.yaml                # All runtime flags & parameters
main.py                           # Pipeline entrypoint; orchestrates the end‑to‑end run
src/core/
  __init__.py                     # Exports core symbols
  utils.py                        # Logging, config, caching, paths, dates
  data.py                         # DataPipeline: loads asset, macro, ancillary data
  features.py                     # Asset & macro feature engineering
  regimes.py                      # JumpModel (unsupervised) + XGBoost forecasters
  diagnostics.py                  # SHAP + baselines + summaries
  portfolio.py                    # PortfolioEngine (μ, Σ, constraints, optimizer, backtest)
  evaluation.py                   # Evaluator + plots + benchmark report helpers
  benchmarks.py                   # BenchmarkEngine (EW, 60/40, Barbell, Diversified Core)
src/visualizations/
  *.py                            # Visualization utilities & post‑hoc analytics
asset_universe/*.csv              # Investable assets (total return indices)
macro_universe/*.csv              # Macro indicators
ancillary/*.csv                   # Risk‑free, SP500, yields (features only)
```

---

## Configuration (config/config.yaml)
Key sections (subset; see file for full list):
- data: date ranges and directories.
- assets: investable list, display_names, categories (cash, government_bonds, …).
- macro: enabled/disabled indicators, display_names, smoothing params.
- macro_lags: publication lag modeling (prevents look‑ahead).
- regimes:
  - jump_model: lambda grid, defaults, n_states, l1_penalty.
  - rolling: walk‑forward settings (enabled, training_years, validation_years, update_frequency_months).
  - xgboost: model params; tune_hyperparameters (bool); early_stopping_rounds; forecast_horizon.
  - smoothing_halflives: probability smoothing candidates.
  - diagnostics: enabled, shap_plots, macro_baseline.
- portfolio:
  - gamma_risk, gamma_trade, transaction costs (flat or tiered).
  - constraints: max_weight, min_weight, max_leverage, min_bullish_assets.
  - covariance_halflife; bearish_return_cap; bullish_return_minvar.
  - regime_allocation: enabled + per‑regime preferred_categories & max_category_weights.
  - gradual_risk_off: crisis_probability_threshold, max_cash_at_crisis.
  - mu_model: linear model with macro_features and lookback_years.
  - regime_mixing: enabled (use probability‑weighted investability).
  - cash_floor: enabled, c0, c1 (smooth cash floor based on crisis prob).
  - robustness_grid: enabled + gamma grids (post‑hoc sensitivity).
  - tail_hedges: enabled + asset groups.
- evaluation: walk‑forward toggle; rebalance_frequency; benchmarks.
- output/logging: directories, figure dpi/format, log level.

---

## src/core/utils.py (utilities)
- setup_logging(level='INFO', config=None) -> Logger
  - Honors logging.file + console options; returns logger named 'fioracle'.
- load_config(config_path='config/config.yaml') -> dict
  - Loads YAML and deep‑merges with get_default_config(); warns and falls back on error.
- _deep_merge(base, override) -> dict (internal)
- get_default_config() -> dict
  - Minimal default structure for data, regimes, features, portfolio, evaluation, output, logging.
- cache_to_parquet(df, name, cache_dir='data/cache', compression='snappy') -> Path
- load_from_parquet(name, cache_dir='data/cache') -> Optional[DataFrame]
- get_project_root() / get_data_dir() / get_output_dir() / get_config_dir() -> Path
- ensure_dir(path) -> Path
- parse_date(date) -> Optional[pd.Timestamp]
- validate_date_range(start_date, end_date) -> (start_ts, end_ts)
- get_annualization_factor(frequency='daily') -> int (252/12/1)

Notes
- Centralized helpers used across main, evaluation, plotting.

---

## src/core/data.py (data pipeline)
Class: DataPipeline(asset_dir=None, macro_dir=None, ancillary_dir=None, config=None)
- load(start_date=None, end_date=None) -> DataFrame
  - Loads three blocks then concatenates on the index (de‑duped, sorted):
    1) _load_asset_universe(): columns prefixed 'asset_'; no forward‑fill applied.
    2) _load_macro_universe(): columns prefixed 'macro_'; forward‑fill gaps up to 30 days.
    3) _load_ancillary_data(): columns prefixed 'ancillary_'; forward‑fill gaps up to 30 days.
  - Applies optional date filtering.
- _load_ancillary_data() -> DataFrame
  - Risk‑free, SP500, 2Y yield, 10Y‑2Y slope; robust column detection; deduplicates index.
- _load_asset_universe() -> DataFrame
  - Reads all CSVs; picks best value column; cleans names via _slugify(); prefixes with 'asset_'.
- _load_macro_universe() -> DataFrame
  - Honors config.macro.enabled/disabled (enabled takes priority); partial matching supported.
- _read_csv(path) -> DataFrame (auto date parsing, cleans index & drops date column)
- _select_value_column(columns) -> str | None (preference list, else first non‑date column)
- _slugify(name) -> str (lowercase, underscores, strips _total_return/_return/_tr)
- get_asset_availability(data) -> dict of column->first valid date

Notes
- Ensures no duplicated index rows; macro/ancillary are forward‑filled conservatively.

---

## src/core/features.py (feature engineering)
Constants
- AVG_RETURN_HALFLIVES = [5,10,21]
- DD_HALFLIVES = [5,21]
- SORTINO_HALFLIVES = [5,10,21]

Functions
- engineer_features(raw_data, config=None) -> (asset_features: dict[str->DataFrame], macro_features: DataFrame)
  - Uses _get_risk_free_returns() and _construct_asset_returns().
  - compute_asset_features() for each investable asset.
  - _compute_macro_features(): VIX/GPR/Debt/GDP/HY OAS/EPU/GDP/UNEMP/Inflation/M2V + ancillary yields & stock‑bond correlation.
- _get_risk_free_returns(raw_data) -> Series
- _construct_asset_returns(raw_data, rf_returns) -> dict[ASSET->Series]
  - Excess returns when RF available, else raw returns.
- compute_asset_features(excess_returns) -> DataFrame
  - avg_return_hl{hl}, log_dd_hl{hl}, sortino_hl{hl}; standardized.
- _compute_downside_deviation(returns, halflife) -> Series
- _apply_macro_lag(series, lag_days, enabled) -> Series (publication lag modeling)
- _compute_macro_features(raw_data, asset_returns, config) -> DataFrame
  - Multiple smoothed/normalized macro features; forward‑fill rules by frequency.
- _find_column(df, candidates) / _find_asset_column(asset_returns, candidates)
- _ewm_logdiff(series, halflife) -> Series
- _standardize_features(features) -> DataFrame
- get_expanded_feature_set(asset_features_df, macro_features_df) -> DataFrame

Notes
- Publication lags controlled by config.macro_lags.enabled + *_days.

---

## src/core/regimes.py (regime identification & forecasting)
Class: JumpModel(lambda_jump=5.0, n_states=2|3, l1_penalty=0.0)
- fit(X) -> states (array[int])
  - Standardizes X; init via KMeans; coordinate descent with DP/Viterbi for state path.
- predict(X) -> states (requires fitted centers)

Class: RegimeEngine(lambda_jump=5.0, n_macro_regimes=3, xgb_params=None, config=None)
- fit_asset_regimes(asset_features_dict, asset_returns_df, verbose=True) -> dict[asset->Series]
  - Fits JumpModel per asset (n_states & l1_penalty from config.regimes.jump_model).
  - 2‑state mapping by cumulative returns (bearish=1); 3‑state mapping by volatility (calm=0, infl=1, crisis=2).
- fit_forecasters(asset_features_dict, asset_regimes_dict, macro_features, asset_returns_dict=None, test_size=0.2, verbose=True) -> dict
  - Builds supervised set per asset; maps classes to consecutive integers; trains XGBoost classifier.
  - Smoothing halflife selected via 0/1 strategy Sharpe on training fold.
  - Robust to single‑class cases by using a DummyClassifier.
  - Ensures predictions are 1D labels for sklearn metrics (accuracy/F1) even if estimator returns 2D.
- _prepare_supervised_data(asset_features, asset_regimes, macro_features) -> (X,y)
  - Supports forecast_horizon {mode: 'shift'|'window_majority', horizon_days} from config.
- _train_xgboost(X_train, y_train, X_test, y_test) -> XGBClassifier
  - Honors config.regimes.xgboost.tune_hyperparameters (small grid around provided params).
  - Honors config.regimes.xgboost.early_stopping_rounds via classifier constructor and an internal time‑ordered validation split (no peeking at test).
  - Sets objective/eval_metric for binary vs multi‑class; balances classes via scale_pos_weight when binary.
- tune_lambda(asset_features, asset_returns, lambda_candidates, validation_start, validation_end, verbose=False) -> (best_lambda, results_df)
  - Sharpe of 0/1 strategy over validation window.
- fit_identify_forecast(...) -> dict
  - Fits asset regimes; trains forecasters; outputs dummy macro_probs for compatibility.
- get_regime_probabilities(asset_features_dict, macro_features, date, asset_names) -> ndarray[n_assets, 3]
  - Pulls classifier per asset; builds combined feature vector; returns [P(calm), P(infl), P(crisis)].
- predict_next_regime(asset_name, current_features, previous_prob=None) -> (pred_label, prob_vec)
  - Applies exponential smoothing to probability vector using per‑asset halflife.

Function: rolling_regime_forecasting(...)
- Bi‑annual updates loop: tune lambda on last validation_years; refit engine; forecast next window; returns per‑asset series + optimal lambdas log.

Notes
- Class maps are tracked to safely invert predictions when training had missing classes.
- All metrics use mapped labels; probability smoothing halflife chosen on Sharpe.

---

## src/core/diagnostics.py (model diagnostics)
- compute_xgb_diagnostics(model, X_train, X_test, y_train, y_test, asset_name, output_dir, compute_shap=True, prediction_horizon=1) -> dict
  - Outputs accuracy/balanced_acc/F1, Brier/log loss (handles class mismatch), native feature_importances_, optional SHAP bars & beeswarm, saved to output_dir/shap/.
  - Ensures 1D predictions for metrics across XGBoost versions.
- run_macro_only_baseline(X_train, X_test, y_train, y_test, exclude_vix=True, macro_features_config=None) -> dict | {with_vix/without_vix}
  - Multinomial/binary logistic regression on macro‑only subset (optional VIX ablation).
- _run_logistic_baseline(...) -> dict (helper)
- compute_persistent_baseline(y_train, y_test) -> {'most_frequent', 'persistence'} baselines.
- compute_conditional_returns(y_pred, returns, regime_names=None, horizon=1) -> dict
- run_full_diagnostics(regime_engine, asset_name, X_train, X_test, y_train, y_test, returns, output_dir, config) -> dict
  - Respects config.regimes.diagnostics.enabled/shap_plots/macro_baseline; saves JSON and aggregate plot.
- save_diagnostics_summary(results, output_dir, split_name)
- plot_feature_importance_comparison(all_results, output_dir, top_n=15)

---

## src/core/portfolio.py (portfolio construction & backtest)
Class: PortfolioEngine(..., config=None)
Constructor parameters
- Risk/turnover aversion: gamma_risk, gamma_trade.
- Transaction costs: transaction_cost (flat) or tiered_transaction_costs.enabled + costs_by_asset + default_cost.
- Constraints: min_bullish_assets, max_weight, max_leverage; covariance_halflife; bearish_return_cap; bullish_return_minvar; strategy ('MV'|'MinVar'|'EW').
- Feature flags from config.portfolio: mu_model, regime_mixing, cash_floor, regime_allocation, gradual_risk_off, tail_hedges.
- Asset categories: from config.assets.categories.

Methods
- set_regime_engine(regime_engine, asset_features_dict=None)
  - Enables regime_mixing by pulling probability vectors at optimize time.
- _get_asset_category(asset_name) -> str | None
- _get_regime_category_weights(regime:int) -> dict[category->cap]
- _get_preferred_categories(regime:int) -> list[str]
- _get_transaction_cost(asset_name) / _get_transaction_costs_array(asset_names)
- generate_mu_sigma(date, regime_forecasts, returns_df, regimes_df, available_assets, macro_features=None) -> (μ, Σ)
  - MinVar: μ=+/-bullish_return_minvar based on regime; MV: macro‑conditioned μ via _compute_macro_conditioned_mu() if enabled, else regime‑conditional averages; Σ via EWM covariance with halflife.
- _compute_macro_conditioned_mu(...)
  - Per‑asset ridge regression on [regime dummies, selected macro columns]; predicts μ at date with regime & current macro; applies regime adjustments (inflationary dampening, crisis cap).
- _compute_simple_regime_mu(...)
- _compute_ewmc(returns) -> covariance matrix with regularization.
- optimize_daily(regime_forecasts, expected_returns, covariance_matrix, asset_names, crisis_probability=None, regime_probabilities=None) -> (weights, diagnostics)
  - Investability based on discrete regimes or probability‑weighted scores when regime_mixing enabled.
  - New: Enforces per‑regime category caps when portfolio.regime_allocation.enabled (linear inequality constraints).
  - New: Tail‑hedge minimum allocation when tail_hedges.enabled (scaled by crisis_probability: 0 at ≤0.2, up to ~40% of risky budget near 1.0).
  - Optional smooth cash floor (cash_floor.enabled) and gradual risk‑off (threshold and max cash).
  - Objective: maximize wᵀμ − γ_risk wᵀΣw − γ_trade Σ a_j |Δw_j| with per‑asset costs; SLSQP with bounds 0..max_weight and budget ≤ (1 − min_cash).
- backtest(returns_df, regimes_df, regime_forecasts_df, start_date=None, end_date=None, verbose=True, macro_features=None, risk_free_rate=None) -> dict
  - Iterates daily: selects available assets; computes μ, Σ; computes crisis_prob; optionally gets regime probabilities for mixing; optimizes; rolls one day ahead for returns; records excess return (subtracts 100% RF benchmark) and transaction costs; logs diagnostics.
- reset()
- optimize_portfolio_ra_fipo(...) -> wrapper for backward compatibility.

Notes
- Category caps and tail‑hedge minimums are additive inequality constraints; both are bounded by risky budget (1 − min_cash) to preserve feasibility.

---

## src/core/evaluation.py (metrics & plots)
- build_60_40_benchmark(split_returns, config) -> Optional[(Series, name)]
- build_all_benchmarks(split_returns, config) -> dict[name->Series]
  - Uses BenchmarkEngine where available; otherwise basic fallback.

Class: Evaluator(annualization_factor=252, transaction_cost=0.0005)
- compute_portfolio_metrics(portfolio_returns, portfolio_weights, benchmark_returns=None, risk_free_rate=None, returns_are_excess=True) -> dict
  - Annualized excess return/volatility, Sharpe, total return, max drawdown (computed on total returns), Calmar, turnover, average leverage.
- compute_zero_one_strategy_sharpe(asset_returns, regime_forecasts, risk_free_rate=None, apply_transaction_costs=True) -> float
- tune_lambda_fast(asset_features, asset_returns, lambda_candidates=[0.1,1,5,10], n_splits=5) -> (lambda, results_df)
- generate_all_plots(...)
  - cumulative_returns.png, drawdown.png, allocation_timeline.png, rolling_sharpe.png, monthly_heatmap.png, return_distribution.png, allocation_pie.png
- plot_comprehensive_results (compat alias), plot_essential, evaluate
- compute_sharpe_ratio, compute_all_metrics, generate_benchmark_comparison_report(...)

---

## src/core/benchmarks.py (benchmark engine)
Class: BenchmarkEngine(config=None)
- compute_ew_benchmark(returns_df) -> Series
- compute_60_40_benchmark(returns_df, gov_weight=0.6, credit_weight=0.4, rebalance_freq='Q') -> (Series, weights_df)
- compute_barbell_benchmark(returns_df, safe_weight=0.85, risky_weight=0.15, rebalance_freq='Q') -> (Series, weights_df)
- compute_diversified_core_benchmark(returns_df, rebalance_freq='Q') -> (Series, weights_df)
- compute_all_benchmarks(returns_df) -> dict[name->(Series,weights_df)]

Function: build_all_benchmarks_enhanced(split_returns, config) -> dict[name->Series]

Notes
- Category membership is drawn from config.assets.categories; partial name matching is supported for robustness.

---

## src/visualizations (post‑hoc analysis)
advanced_analytics.py
- generate_fat_tail_analysis(returns, regimes, output_dir, strategy_name='Strategy') -> dict
  - QQ plots, tail indices (Hill), distribution comparisons; saves multiple figures + CSV.
- generate_correlation_regime_analysis(returns_df, sp500_returns, regimes, output_dir) -> dict
- generate_statistical_tests(portfolio_returns, benchmark_returns, output_dir) -> dict

historical_series.py
- create_combined_timeseries_plot(output_dir, start_date, end_date)
- create_regime_prediction_timeline(output_dir, start_date, end_date)
  - Small demo pipeline (DataPipeline → engineer_features → JumpModel/RegimeEngine) to produce per‑asset regime timelines.

period_analysis.py
- generate_supply_shock_analysis(...)
- generate_financial_crisis_analysis(...)
- generate_period_analysis(...)
  - Produces side‑by‑side pies/timelines; cumulative with Sharpe and stock‑bond correlation panel; per‑period metrics.

regime_drivers.py
- visualize_regime_drivers(start_date, end_date, output_dir, show_plot=False)
  - Macro indicator timelines; macro correlation matrix; summary panels (VIX, GPR, Debt/GDP, Inflation).

robustness_grid.py
- evaluate_gamma_grid(config, returns_df, regime_forecasts_df, macro_features, regimes_df, split_name, output_dir, risk_free_rate) -> DataFrame
  - Loops over gamma_risk × gamma_trade; runs a simplified backtest; writes CSV + heatmaps.

tail_hedge_analysis.py
- analyze_tail_hedges(portfolio_returns, portfolio_weights, asset_returns, regime_series, config, output_dir, split_name) -> dict
  - Group performance (CHF, Gold, Gov, Credit) by regime; drawdown decomposition; multiple figures and JSON.
- analyze_regime_coherence(regime_forecasts, output_dir, split_name) -> dict

vix_analysis.py
- analyze_vix_effectiveness(portfolio_returns, benchmark_returns, vix_data, weights_df, regimes_df, output_dir, strategy_name, all_strategy_returns=None) -> dict
  - Performance by VIX regime; allocation response scatterplots; VIX events timeline.

---

## main.py (pipeline runner)
Constants
- CONFIG_PATH, OUTPUT_DIR, SPLITS = ['train','val','test']
- TRAINING_YEARS=11, VALIDATION_YEARS=5, UPDATE_FREQUENCY_MONTHS=6
- QUICK_MODE ('--quick'), TUNE_LAMBDA=True, TRAIN_FORECASTERS=True, VERBOSE=True

High‑level steps in run_pipeline(config, output_dir) -> dict
1) Data loading via DataPipeline.load()
2) Feature engineering via engineer_features()
3) Build asset returns (respect investable/excluded lists; risk‑free series used elsewhere)
4) Train on training period only
   - Optional lambda tuning via Evaluator.tune_lambda_fast()
   - Instantiate RegimeEngine(lambda_jump, xgb_params=config.regimes.xgboost, config=config)
   - RegimeEngine.fit_identify_forecast(train_assets)
5) Evaluate on train/val/test
   - For test: walk‑forward forecasting via rolling_regime_forecasting(...)
   - For each split: run_split_with_trained_model(...)
     • Build regimes_df (training pre‑identified or out‑of‑sample predictions)
     • Save regime stats JSON
     • PortfolioEngine per strategy (MINVAR/MV/EW)
       – Optionally set regime engine for probability mixing
       – Backtest with macro_features & risk‑free rate (excess returns)
     • Evaluate vs benchmarks (Evaluator + build_all_benchmarks)
     • Visuals: strategy plots; benchmark comparison; VIX analysis for best strategy
     • Diagnostics (if regimes.diagnostics.enabled): SHAP, macro‑baseline, summaries
     • Advanced analytics (fat tails, correlation regimes) for best strategy
     • Tail hedge analysis (if portfolio.tail_hedges.enabled)
     • Robustness grid (if portfolio.robustness_grid.enabled)
6) Regime drivers & historical series visualizations
7) Summary report saved to output/results

Notes
- Risk‑free rate is used in backtest to compute excess returns (strategy returns already excess when saved by Evaluator; benchmarks remain raw and are adjusted when reported).

---

## Data flow and process (JM‑XGB → RA‑FIPO)
1) DataPipeline.load() → combined DataFrame with 'asset_', 'macro_', 'ancillary_' columns.
2) engineer_features():
   - asset_features[ASSET] (8 return features per asset), macro_features (smoothed indicators).
3) Regime identification per asset via JumpModel → asset_regimes (2‑ or 3‑state), semantic mapping.
4) Supervised forecasting via RegimeEngine.fit_forecasters():
   - Builds supervised dataset (asset + macro features); trains XGBoost; selects smoothing halflife.
5) Optionally run rolling_regime_forecasting() for test window (walk‑forward updates).
6) PortfolioEngine.backtest():
   - For each day & available assets → compute μ, Σ (macro‑conditioned or regime‑conditional) → optimize with constraints (including category caps, tail‑hedge floors, turnover costs) → compute next‑day return vs RF benchmark → store excess returns & diagnostics.
7) Evaluator: compute metrics/plots; BenchmarkEngine for comparisons; diagnostics & analytics modules for additional insight.

---

## Change audit: regimes.py tuning & early stopping
Goal
- Implement config‑driven tuning and early stopping for XGBoost forecasters, honoring:
  - regimes.xgboost.tune_hyperparameters
  - regimes.xgboost.early_stopping_rounds

What existed before
- _train_xgboost trained with params from self.xgb_params and eval_set=[(X_test, y_test)] but:
  - No grid search implemented; tune_hyperparameters in config was ignored.
  - No early stopping support; early_stopping_rounds in config was ignored.

What was added (and why)
- _train_xgboost now:
  - Uses a time‑ordered inner validation split from X_train for early stopping (so we never peek at test during training).
  - Accepts early_stopping_rounds via the XGBClassifier constructor (required for newer XGBoost sklearn wrappers).
  - Implements a small, robust grid search around provided params when tune_hyperparameters is true; scores by (m)logloss on the inner validation slice; falls back gracefully if early‑stopping best_score is unavailable (computes log loss directly).
  - Normalizes prediction shapes so sklearn metrics always receive 1D class labels.

Compatibility
- Requirements specify xgboost>=2.0.0. Some versions reject early_stopping_rounds and callbacks via fit(); the constructor pattern used here is compatible across 2.x and avoids those errors.

Conclusion
- There was no previous mechanism handling early stopping or tuning; the change correctly wires the config switches into training with a time‑series‑safe validation split and version‑compatible API usage.

---

Appendix: Full function/class index (per file)

src/core/benchmarks.py
- Class BenchmarkEngine(config=None)
  - _find_matching_assets(asset_list, available_cols) -> list[str]
  - _get_category_assets(category, available_cols) -> list[str]
  - compute_ew_benchmark(returns_df) -> Series
  - compute_60_40_benchmark(returns_df, gov_weight=0.6, credit_weight=0.4, rebalance_freq='Q') -> (Series, DataFrame)
  - compute_barbell_benchmark(returns_df, safe_weight=0.85, risky_weight=0.15, rebalance_freq='Q') -> (Series, DataFrame)
  - compute_diversified_core_benchmark(returns_df, rebalance_freq='Q') -> (Series, DataFrame)
  - compute_all_benchmarks(returns_df) -> dict[name->(Series, DataFrame|None)]
- Function build_all_benchmarks_enhanced(split_returns, config) -> dict[name->Series]

src/core/data.py
- Class DataPipeline(asset_dir=None, macro_dir=None, ancillary_dir=None, config=None)
  - load(start_date=None, end_date=None) -> DataFrame
  - _load_ancillary_data() -> DataFrame
  - _load_asset_universe() -> DataFrame
  - _load_macro_universe() -> DataFrame
  - _read_csv(path) -> DataFrame
  - _select_value_column(columns) -> Optional[str]
  - _slugify(name) -> str
  - get_asset_availability(data) -> dict[str, Timestamp]
Notes
- CSV reader handles ambiguous dates and fixes yy century; deduplicates index rows before concat; macro/ancillary forward-filled with limits.

src/core/diagnostics.py
- compute_xgb_diagnostics(model, X_train, X_test, y_train, y_test, asset_name, output_dir, compute_shap=True, prediction_horizon=1) -> dict
- run_macro_only_baseline(X_train, X_test, y_train, y_test, exclude_vix=True, macro_features_config=None) -> dict | {'with_vix','without_vix'}
- _run_logistic_baseline(...) -> dict
- compute_persistent_baseline(y_train, y_test) -> dict
- compute_conditional_returns(y_pred, returns, regime_names=None, horizon=1) -> dict
- run_full_diagnostics(regime_engine, asset_name, X_train, X_test, y_train, y_test, returns, output_dir, config) -> dict
- save_diagnostics_summary(results, output_dir, split_name)
- plot_feature_importance_comparison(all_results, output_dir, top_n=15)
Notes
- Normalizes prediction shapes (argmax for 2D outputs) and ravel() labels to ensure sklearn metrics receive 1D arrays; SHAP gated by compute_shap flag and availability.

src/core/evaluation.py
- Helper: _format_date_axis(ax, dates)
- Benchmarks: build_60_40_benchmark(split_returns, config) -> Optional[(Series, name)]; build_all_benchmarks(split_returns, config) -> dict[name->Series]
- Class Evaluator(annualization_factor=252, transaction_cost=0.0005)
  - compute_portfolio_metrics(portfolio_returns, portfolio_weights, benchmark_returns=None, risk_free_rate=None, returns_are_excess=True) -> dict
  - _empty_metrics() -> dict
  - compute_zero_one_strategy_sharpe(asset_returns, regime_forecasts, risk_free_rate=None, apply_transaction_costs=True) -> float
  - tune_lambda_fast(asset_features, asset_returns, lambda_candidates=[0.1,1.0,5.0,10.0], n_splits=5) -> (float, DataFrame)
  - generate_all_plots(...)
    • _plot_cumulative_returns, _plot_drawdown, _plot_allocation_timeline, _plot_rolling_sharpe, _plot_monthly_heatmap, _plot_return_distribution, _get_display_name
  - plot_comprehensive_results(...), plot_essential(...), evaluate(...)
- Standalone: compute_sharpe_ratio(returns, risk_free_rate=0.0) -> float; compute_all_metrics(...); generate_benchmark_comparison_report(...) -> DataFrame
Notes
- Backtest returns are treated as excess by default (returns_are_excess=True) to avoid double RF subtraction; plotting functions save separate PNGs; benchmark comparison persists CSV and text.

src/core/features.py
- Constants: AVG_RETURN_HALFLIVES, DD_HALFLIVES, SORTINO_HALFLIVES
- engineer_features(raw_data, config=None) -> (dict[str->DataFrame], DataFrame)
- _get_risk_free_returns(raw_data) -> Series (ancillary)
- _construct_asset_returns(raw_data, rf_returns) -> dict[str->Series]
- compute_asset_features(excess_returns) -> DataFrame
- _compute_downside_deviation(returns, halflife) -> Series
- _apply_macro_lag(series, lag_days, enabled) -> Series
- _compute_macro_features(raw_data, asset_returns, config) -> DataFrame
- _find_column(df, candidates) -> Optional[str]; _find_asset_column(asset_returns, candidates) -> Optional[str]
- _ewm_logdiff(series, halflife) -> Series; _standardize_features(features) -> DataFrame
- get_expanded_feature_set(asset_features_df, macro_features_df) -> DataFrame
Notes
- Macro publication lag modeling via config.macro_lags; stock‑bond correlation computed over 252d window on aligned indices.

src/core/portfolio.py
- Class PortfolioEngine(..., config=None)
  - set_regime_engine(regime_engine, asset_features_dict=None)
  - _get_asset_category(name) -> Optional[str]
  - _get_regime_category_weights(regime:int) -> dict; _get_preferred_categories(regime:int) -> list
  - _get_transaction_cost(name) -> float; _get_transaction_costs_array(asset_names) -> ndarray
  - generate_mu_sigma(date, regime_forecasts, returns_df, regimes_df, available_assets, macro_features=None) -> (μ, Σ)
  - _compute_macro_conditioned_mu(...); _compute_simple_regime_mu(...); _compute_ewmc(returns) -> Σ
  - optimize_daily(regime_forecasts, μ, Σ, asset_names, crisis_probability=None, regime_probabilities=None) -> (weights, diagnostics)
  - backtest(returns_df, regimes_df, regime_forecasts_df, start_date=None, end_date=None, verbose=True, macro_features=None, risk_free_rate=None) -> dict
  - reset()
Notes
- Enforces per‑regime category caps when portfolio.regime_allocation.enabled; adds crisis‑scaled tail‑hedge minimum allocation when portfolio.tail_hedges.enabled; supports regime mixing via probability‑weighted investability scores; per‑asset turnover costs.

src/core/regimes.py
- Class JumpModel(lambda_jump=5.0, n_states=2|3, l1_penalty=0.0)
  - fit(X) -> ndarray[int]; predict(X) -> ndarray[int]
- Class RegimeEngine(lambda_jump=5.0, n_macro_regimes=3, xgb_params=None, config=None)
  - fit_asset_regimes(asset_features_dict, asset_returns_df, verbose=True) -> dict[str->Series]
  - _fit_single_asset_regime(features, returns) -> (Series, JumpModel)
  - _assign_bull_bear_labels(states, returns) -> Series; _assign_3state_labels(states, returns) -> Series
  - fit_forecasters(asset_features_dict, asset_regimes_dict, macro_features, asset_returns_dict=None, test_size=0.2, verbose=True) -> dict
  - _prepare_supervised_data(asset_features, asset_regimes, macro_features) -> (DataFrame, Series)
  - _train_xgboost(X_train, y_train, X_test, y_test) -> XGBClassifier
  - tune_lambda(asset_features, asset_returns, lambda_candidates, validation_start, validation_end, verbose=False) -> (float, DataFrame)
  - fit_identify_forecast(... ) -> dict
  - get_regime_probabilities(asset_features_dict, macro_features, date, asset_names) -> ndarray[n_assets,3]
  - predict_next_regime(asset_name, current_features, previous_prob=None) -> (int, ndarray)
Notes
- Early stopping wired via XGBClassifier(early_stopping_rounds=...)+inner validation split (not fit() kwargs); prediction shapes normalized to 1D for sklearn metrics and diagnostics; halflife tuning uses favorable‑prob cutoff strategy on training fold.

src/core/utils.py
- setup_logging(level='INFO', config=None) -> Logger
- load_config(config_path) -> dict; _deep_merge(base, override) -> dict
- get_default_config() -> dict (complete skeleton for all sections)
- cache_to_parquet(df, name, cache_dir='data/cache', compression='snappy') -> Path
- load_from_parquet(name, cache_dir='data/cache') -> Optional[DataFrame]
- get_project_root()/get_data_dir()/get_output_dir()/get_config_dir() -> Path; ensure_dir(path) -> Path
- parse_date(date) -> Optional[Timestamp]; validate_date_range(start, end) -> (Timestamp|None, Timestamp|None)
- get_annualization_factor(frequency='daily'|'monthly'|'annual'|'annualized') -> int

main.py
- log_with_timestamp(message, level='INFO')
- cleanup_output_directory(output_dir: Path)
- run_pipeline(config: dict, output_dir: Path) -> dict
  • Loads data → engineers features → builds returns/RF → trains RegimeEngine (optional λ tuning) → evaluates splits
  • Test split: rolling_regime_forecasting walk‑forward; others: use pre‑trained models
  • Portfolios: MINVAR/MV/EW; regime mixing optional; runs Evaluator + plots; diagnostics (SHAP/macro baseline) gated by config; advanced analytics; tail‑hedge & robustness grid if enabled
- run_split_with_trained_model(split_name, config, asset_features, macro_features, returns_df, risk_free_rate, regime_engine, trained_regimes_df, output_dir, excluded_assets) -> dict
  • Generates split‑specific regimes; builds regime_forecasts_df (shifted one day); runs PortfolioEngine.backtest; evaluates metrics vs multiple benchmarks; runs diagnostics/analytics per flags
- generate_summary(results: dict, output_dir: Path) -> dict
- main() -> results

config/config.yaml
- Captures all switches referenced above. Notable sections besides those documented earlier:
  • benchmark_60_40: enabled + asset lists and weights
  • portfolio.tiered_transaction_costs: pattern‑based costs and default_cost
  • portfolio.tail_hedges: asset groups used by optimizer min‑allocation constraint (now enforced)
  • regimes.diagnostics.shap_plots and macro_baseline: honored by diagnostics pipeline

Verification notes
- The appendix reflects a line‑by‑line pass over the listed files and surfaces each function/class and its role in the pipeline wiring. If any symbol is missing, call it out and we will amend immediately.

---

End of WARP.
