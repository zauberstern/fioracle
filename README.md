<p align="center">
  <img src="fi-oracle.png" alt="FIOracle Logo" width="280"/>
</p>

<h1 align="center">FIOracle</h1>

<p align="center">
  <strong>Regime-Aware Fixed Income Oracle</strong>
</p>

<p align="center">
  <sub>
    <em>Kartik Yadav · Leon Förch · Edward Kachatryan · Nicola Copetti · Alessandro Florentino</em>
  </sub>
</p>

<br/>

<p align="center">
  <em>A machine learning framework for dynamic fixed income portfolio allocation that identifies market regimes and adapts positioning to navigate calm, inflationary, and crisis environments.</em>
</p>

<p align="center">
  <a href="#architecture">Architecture</a> •
  <a href="#results">Results</a> •
  <a href="#usage">Usage</a> •
  <a href="#config-manual">Config Manual</a> •
  <a href="#limitations">Limitations</a>
</p>

---

## Overview

FIOracle is a quantitative research framework that combines unsupervised regime detection with supervised regime forecasting to dynamically allocate across a universe of fixed income and safe-haven assets. The system employs a three-layer architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FIOracle Architecture                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐    │
│   │  LAYER A        │    │  LAYER B         │    │  LAYER C           │    │
│   │  Data Pipeline  │───▶│  Regime Engine   │───▶│  Portfolio Engine  │    │
│   └─────────────────┘    └──────────────────┘    └────────────────────┘    │
│           │                       │                        │                │
│     Asset Returns          Jump Model +              MVO / MinVar /         │
│     Macro Features         XGBoost Forecast          Equal Weight           │
│     Forward-Filled         3-State Regimes           Regime-Conditioned     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Asset Universe

| Category | Assets |
|----------|--------|
| **Cash & T-Bills** | US T-Bills |
| **Government Bonds** | US 10Y Treasury, Treasury Index, Sovereign Index |
| **Investment Grade** | US Aggregate Bond, Corporate IG |
| **High Yield** | CDX HY 5Y, USD Liquid HY |
| **Inflation Protection** | US TIPS 0-5Y, Inflation Swaps (1Y, 2Y, 5Y, 10Y) |
| **Safe Havens** | Gold, Swiss Franc (CHF) |
| **Commodities** | WTI Crude Oil |

### Macro Indicators

- **VIX** (Market Volatility)
- **GPRI** (Geopolitical Risk Index)
- **US Inflation Rate** (CPI)
- **US Debt-to-GDP Ratio**
- **US High Yield OAS** (Credit Spreads)
- **Economic Policy Uncertainty** (EPU)

---

<h2 id="architecture">Architecture Deep Dive</h2>

### 1. Jump Model (Unsupervised Regime Detection)

The foundation of regime identification uses a **Jump Model** (L1-regularized Markov-switching model) that partitions historical returns into three states:

- **Calm (State 0)**: Low volatility, positive expected returns
- **Inflationary (State 1)**: Elevated uncertainty, mixed returns
- **Crisis (State 2)**: High volatility, negative expected returns

The regularization parameter λ controls regime persistence vs. responsiveness, tuned via time-series cross-validation on the training set.

### 2. XGBoost Regime Forecaster (Supervised Learning)

A gradient-boosted classifier predicts tomorrow's regime using today's features:

**Defenses Against Overfitting:**
- `max_depth=5` limits tree complexity
- `subsample=0.8` and `colsample_bytree=0.8` introduce randomness
- `early_stopping_rounds` prevents excessive iterations
- Stratified time-series cross-validation (5-fold)
- Hyperparameter grid search on validation set only

**Defenses Against Look-Ahead Bias:**
- **Strict temporal separation**: Training (1945-2004), Validation (2005-2007), Test (2008-2025)
- **Publication lag modeling**: All macro indicators are lagged by their real-world reporting delays (e.g., CPI: 15 days, GDP: 90 days, VIX: 1 day)
- **Walk-forward architecture**: Models trained only on data available at each decision point
- **No future information leakage**: Features computed with causal-only operations (e.g., trailing rolling windows, not centered)

### 3. Portfolio Optimization

Three strategies execute regime-conditioned allocations:

| Strategy | Objective | Risk Profile |
|----------|-----------|--------------|
| **MinVar** | Minimize portfolio variance | Conservative |
| **MVO** | Maximize Sharpe (risk-adjusted returns) | Balanced |
| **EW** | Equal-weight bullish assets | Aggressive |

**Regime-Specific Behavior:**
- **Crisis detected**: Rotate to cash, Treasuries, Gold, CHF
- **Inflationary**: Favor TIPS, commodities, reduce duration
- **Calm**: Full diversification across credit, rates, alternatives

---

<h2 id="results">Results</h2>

### Out-of-Sample Performance (2008–2025)

The test period includes multiple stress events: Global Financial Crisis (2008), European Debt Crisis (2011), COVID Crash (2020), and the 2022 Rate Shock.

| Metric | MinVar | MVO | EW | 60/40 Benchmark |
|--------|--------|-----|----|----|
| **Sharpe Ratio** | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` |
| **Total Return** | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` |
| **Max Drawdown** | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` |
| **Calmar Ratio** | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` |

### Cumulative Wealth Comparison

![Cumulative Returns](output/figures/test/mv/cumulative_returns.png)

### Regime Detection Accuracy

| Asset | XGBoost Accuracy | F1-Score |
|-------|-----------------|----------|
| US 10Y Treasury | `[PLACEHOLDER]` | `[PLACEHOLDER]` |
| US Aggregate Bond | `[PLACEHOLDER]` | `[PLACEHOLDER]` |
| Gold | `[PLACEHOLDER]` | `[PLACEHOLDER]` |
| CHF | `[PLACEHOLDER]` | `[PLACEHOLDER]` |

### Rolling Sharpe Ratio

![Rolling Sharpe](output/figures/test/mv/rolling_sharpe.png)

### Period-Specific Analysis

#### Supply Shock Period (2018–2022)

| Period | Strategy Return | Max Drawdown | Sharpe |
|--------|----------------|--------------|--------|
| Pre-COVID (2018-2020) | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` |
| Supply Shock (2020-2022) | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` |

![Supply Shock Analysis](output/figures/test/supply_shock_analysis/combined_allocation_pies.png)

#### Financial Crisis Period (2006–2010)

| Period | Strategy Return | Max Drawdown | Sharpe |
|--------|----------------|--------------|--------|
| Pre-Crisis (2006-2008) | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` |
| GFC + Recovery (2008-2010) | `[PLACEHOLDER]` | `[PLACEHOLDER]` | `[PLACEHOLDER]` |

### Regime Timeline

![Regime Predictions](output/figures/historical/regime_timeline_US_10Y_GOV_BOND.png)

### Macro Indicators Over Time

![Historical Series](output/figures/historical/combined_historical_series.png)

---

<h2 id="usage">Usage Guide</h2>

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/fioracle.git
cd fioracle

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Quick Start

```bash
# Run full pipeline (quick mode for testing)
python main.py --quick

# Run full pipeline (all data, 1945-present)
python main.py
```

### Adding New Assets

1. Place CSV file in `asset_universe/` with columns: `Date`, `Value` (or similar)
2. Add filename (without `.csv`) to `config/config.yaml` under `assets.investable`
3. Run pipeline—the system auto-detects column formats

### Output Structure

```
output/
├── figures/
│   ├── test/
│   │   ├── mv/                    # Mean-Variance strategy plots
│   │   ├── minvar/                # Minimum Variance plots
│   │   ├── ew/                    # Equal Weight plots
│   │   ├── vix_analysis/          # VIX effectiveness analysis
│   │   ├── supply_shock_analysis/ # 2018-2022 period analysis
│   │   └── advanced_analytics/    # Fat-tail and statistical tests
│   ├── historical/                # Long-term time series
│   └── regime_analysis/           # Macro indicator timelines
├── results/
│   ├── pipeline_summary.json      # Aggregate results
│   └── test/
│       ├── strategy_comparison.json
│       └── {strategy}/benchmark_comparison.csv
└── regime_statistics/             # Regime distributions
```

---

<h2 id="config-manual">Configuration Manual</h2>

The `config/config.yaml` file controls all aspects of the pipeline. Below is a comprehensive reference.

### 📅 Data Configuration

```yaml
data:
  start_date: 1945-01-01        # Earliest date to load
  end_date: 2025-11-28          # Latest date to load
  
  train_start: 1945-01-01       # Training period start
  train_end: 2004-12-31         # Training period end
  
  val_start: 2005-01-01         # Validation period start
  val_end: 2007-12-31           # Validation period end
  
  test_start: 2008-01-01        # Test period start (includes GFC)
  test_end: 2025-11-28          # Test period end
  
  asset_dir: asset_universe     # Directory for asset CSV files
  macro_dir: macro_universe     # Directory for macro CSV files
  ancillary_dir: ancillary      # Directory for ancillary data
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `train_*` | date | Model training window (no test data leakage) |
| `val_*` | date | Lambda tuning and hyperparameter selection |
| `test_*` | date | Out-of-sample evaluation period |

---

### 📊 Asset Universe

```yaml
assets:
  investable:
    - US_CASH_RETURN              # Cash equivalent
    - US_10Y_GOV_BOND_RETURN      # Government bonds
    - GOLD_TOTAL_RETURN           # Safe haven
    # ... add more assets
  
  excluded:
    - IBOXX_USD_LIQ_IG_TOTAL_RETURN  # Excluded from portfolio
  
  categories:
    cash:
      - US_CASH_RETURN
    government_bonds:
      - US_10Y_GOV_BOND_RETURN
    safe_havens:
      - GOLD_TOTAL_RETURN
      - CHF_TOTAL_RETURN
    # ... define more categories
  
  display_names:
    US_CASH_RETURN: "US T-Bills"
    GOLD_TOTAL_RETURN: "Gold"
```

| Section | Purpose |
|---------|---------|
| `investable` | Assets included in portfolio optimization |
| `excluded` | Assets loaded but not traded (for features only) |
| `categories` | Regime-specific allocation buckets |
| `display_names` | Human-readable labels for plots |

**To add a new asset:**
1. Place `MY_ASSET.csv` in `asset_universe/`
2. Add `MY_ASSET` to `assets.investable`
3. (Optional) Assign to a category and add display name

---

### 📈 Macro Indicators

```yaml
macro:
  enabled:
    - VIX                    # Market volatility
    - GPRI                   # Geopolitical Risk Index
    - US_DEBT_TO_GDP         # Fiscal sustainability
    - US_INFLATION_RATE      # CPI
  
  disabled:
    - US_UNEMPLOYMENT_RATE   # Not used currently
    - EPU                    # Economic Policy Uncertainty
  
  params:
    vix_halflife: 63         # Exponential smoothing halflife (days)
    gpr_halflife: 21
    inflation_halflife: 21
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `*_halflife` | 21-63 | Controls smoothing for feature engineering |

---

### ⏱️ Publication Lag Modeling

```yaml
macro_lags:
  enabled: true              # CRITICAL for preventing look-ahead bias
  vix_days: 1                # Real-time market data
  gpr_days: 5                # News aggregation delay
  inflation_days: 15         # CPI released ~15 days after month end
  debt_to_gdp_days: 60       # Quarterly + 60 day reporting delay
  gdp_growth_days: 90        # GDP quarterly + 30 day advance estimate
  unemployment_days: 7       # Monthly, released first Friday
```

> ⚠️ **Warning**: Setting `enabled: false` will cause look-ahead bias in backtests!

---

### 🔀 Regime Configuration

```yaml
regimes:
  jump_model:
    lambda_candidates: [0.0, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0]
    default_lambda: 5.0       # Fallback if tuning fails
    n_states: 3               # 3 = calm/inflationary/crisis
  
  labels:
    0: calm
    1: inflationary
    2: crisis
  
  xgboost:
    max_depth: 5              # Tree depth (overfitting control)
    n_estimators: 100         # Number of boosting rounds
    learning_rate: 0.1        # Step size shrinkage
    subsample: 0.8            # Row sampling ratio
    colsample_bytree: 0.8     # Column sampling ratio
    tune_hyperparameters: true
    
    forecast_horizon:
      mode: shift             # 'shift' = predict next day
      horizon_days: 1
  
  rolling:
    enabled: false            # Walk-forward retraining
    training_years: 11        # Lookback window
    update_frequency_months: 6
  
  diagnostics:
    enabled: true
    shap_plots: true          # Generate SHAP explanations
```

| Parameter | Impact |
|-----------|--------|
| `lambda_candidates` | Higher λ = more persistent regimes, fewer switches |
| `n_states` | Number of market regimes (2 or 3) |
| `max_depth` | Lower = less overfitting, higher bias |
| `subsample` | Lower = more regularization |

---

### 💼 Portfolio Optimization

```yaml
portfolio:
  gamma_risk: 10.0           # Risk aversion coefficient
  gamma_trade: 1.0           # Transaction cost penalty
  transaction_cost: 0.0005   # 5 bps per trade
  
  max_weight: 0.40           # Max allocation to single asset
  min_weight: 0.00           # Min allocation (no shorting)
  max_leverage: 1.0          # Max gross exposure
  
  min_bullish_assets: 3      # Require at least 3 bullish forecasts
  covariance_halflife: 252   # Halflife for covariance estimation
  
  # Regime-specific allocation constraints
  regime_allocation:
    enabled: true
    
    calm:
      preferred_categories:
        - investment_grade
        - government_bonds
      max_category_weights:
        cash: 0.20
        high_yield: 0.25
    
    crisis:
      preferred_categories:
        - cash
        - safe_havens
      max_category_weights:
        cash: 0.60
        high_yield: 0.05
  
  # Gradual risk-off (continuous, not binary)
  gradual_risk_off:
    enabled: true
    crisis_probability_threshold: 0.3   # Start reducing risk
    max_cash_at_crisis: 0.80            # Max cash when P(crisis)=1
  
  # Cash floor (always hold minimum cash)
  cash_floor:
    enabled: true
    c0: 0.05                  # Base 5% minimum
    c1: 0.75                  # Scale with crisis probability
```

| Parameter | Strategy Impact |
|-----------|-----------------|
| `gamma_risk` | Higher = more conservative (MinVar-like) |
| `gamma_trade` | Higher = lower turnover, stickier positions |
| `max_weight` | Diversification constraint |
| `gradual_risk_off` | Smooth transition vs. binary regime switch |

---

### 📊 Benchmarks

```yaml
benchmark_60_40:
  enabled: true
  gov_assets:
    - IBOXX_USD_TREASURY
    - US_10Y_GOV_BOND
  credit_assets:
    - IBOXX_USD_CORPORATE
    - US_AAA_CORP_BOND
  gov_weight: 0.6
  credit_weight: 0.4

evaluation:
  benchmarks:
    - equal_weight            # EW buy-and-hold
    - buy_hold                # Single asset buy-and-hold
    - sixty_forty             # 60/40 gov/credit
```

---

### 📁 Output Configuration

```yaml
output:
  figures_dir: output/figures
  models_dir: output/models
  results_dir: output/results
  regime_stats_dir: output/regime_statistics
  dpi: 150                   # Plot resolution
  format: png                # Output format

logging:
  level: INFO                # DEBUG, INFO, WARNING, ERROR
  file: output/fioracle.log
  console: true
```

---

### 🚀 Quick Customization Recipes

<details>
<summary><b>Recipe 1: Conservative Portfolio</b></summary>

```yaml
portfolio:
  gamma_risk: 15.0           # More risk-averse
  max_weight: 0.30           # More diversified
  gradual_risk_off:
    enabled: true
    crisis_probability_threshold: 0.2   # Earlier risk-off
    max_cash_at_crisis: 0.90
```
</details>

<details>
<summary><b>Recipe 2: Aggressive Portfolio</b></summary>

```yaml
portfolio:
  gamma_risk: 5.0            # Less risk-averse
  max_weight: 0.50           # Allow concentration
  gradual_risk_off:
    enabled: false           # Binary regime switch
```
</details>

<details>
<summary><b>Recipe 3: Fast Development Runs</b></summary>

```yaml
data:
  train_start: 2000-01-01    # Shorter training
  
regimes:
  jump_model:
    lambda_candidates: [1.0, 5.0]  # Fewer candidates
  xgboost:
    n_estimators: 50         # Fewer trees
    tune_hyperparameters: false
  rolling:
    enabled: false
```
</details>

<details>
<summary><b>Recipe 4: Full Walk-Forward Validation</b></summary>

```yaml
regimes:
  rolling:
    enabled: true
    training_years: 15
    validation_years: 3
    update_frequency_months: 6

evaluation:
  use_walk_forward: true
```
</details>

---

<h2 id="limitations">Current Limitations & Future Work</h2>

### Current Limitations

| Limitation | Description |
|------------|-------------|
| **Regime Lag** | Regime detection inherently lags market conditions; crisis signals may arrive 1-3 days after drawdowns begin |
| **Transaction Costs** | Model assumes 5bps per trade; actual costs vary by instrument and market conditions |
| **Liquidity** | No explicit liquidity constraints; some assets (e.g., inflation swaps) may have limited market depth |
| **Short Selling** | Current implementation is long-only; defensive positioning relies on rotation to cash rather than shorting |
| **Single Currency** | USD-denominated portfolio; FX hedging not modeled for non-USD assets |
| **Macro Data Quality** | Historical macro series may have revisions not captured in backtest |

### Future Work

- [ ] **Ensemble Regime Detection**: Combine Jump Model with HMM and LSTM for more robust regime signals
- [ ] **Adaptive Transaction Cost Modeling**: Estimate costs dynamically based on volatility and liquidity
- [ ] **Multi-Currency Extension**: Add FX hedging module for global fixed income allocation
- [ ] **Alternative Data**: Incorporate news sentiment, Fed communication analysis, flow data
- [ ] **Risk Parity Integration**: Add risk parity as alternative allocation strategy
- [ ] **Explainability Dashboard**: Interactive SHAP-based analysis of regime forecasts
- [ ] **Live Trading Integration**: API connectors for execution platforms

---

## Citation

If you use FIOracle in your research, please cite:

```bibtex
@software{fioracle2025,
  title={FIOracle: Regime-Aware Fixed Income Portfolio Optimization},
  author={Yadav, Kartik and Förch, Leon and Kachatryan, Edward and Copetti, Nicola and Florentino, Alessandro},
  year={2025},
  url={https://github.com/your-org/fioracle}
}
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <sub>Built with ❤️ for quantitative research</sub>
</p>
