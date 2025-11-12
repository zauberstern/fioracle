# Fioracle

**Regime-Aware Portfolio Management**

Three-layer regime identification system combining statistical models with XGBoost forecasting for superior risk-adjusted returns.

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Run
python main.py --mode basic --optimize-portfolio

# View results
open output/figures/essential_plots.png
```

## What It Does

**Three-Layer Regime Detection:**
- **Layer C**: Asset bull/bear regimes (Jump Model HMM)
- **Layer B**: Market volatility states (PCA + HMM)
- **Layer A**: Macro-economic environments (N-state HMM)
- **Forecasting**: XGBoost for next-day predictions (>97% accuracy)

**Portfolio Optimization:**
- Regime-conditioned returns & covariance (RA-FIAP)
- Constrained optimization with capital preservation (RA-FIPO)

**Typical Performance** (vs buy-and-hold):
- Sharpe: **+73%** | Max Drawdown: **-90%** | Volatility: **-67%**

## Usage

### Basic
```bash
python main.py --mode basic --optimize-portfolio
```

### Advanced
```bash
# With hyperparameter tuning and walk-forward validation
python main.py --mode full --tune-lambda --walk-forward --optimize-portfolio

# Specific data splits
python main.py --split train  # 1945-2000
python main.py --split val    # 2001-2010
python main.py --split test   # 2011-2025
```

### Python API
```python
from src.core import DataPipeline, engineer_features, RegimeEngine

# Load data
pipeline = DataPipeline(mode='basic')
data = pipeline.load('2001-01-01', '2010-12-31')

# Engineer features
asset_features, macro_features = engineer_features(data)

# Identify regimes
engine = RegimeEngine(lambda_jump=5.0)
results = engine.fit_identify_forecast(
    asset_features, returns, macro_features
)
```

## Data Sources

| Source | Description | Frequency | Coverage |
|--------|-------------|-----------|----------|
| GPR | Geopolitical Risk Index | Daily | 1985-present |
| EPU | Economic Policy Uncertainty | Daily | 1985-present |
| Shiller | Stock/Bond returns, CAPE | Monthly | 1871-present |
| JST | Macrohistory database | Annual | 1870-present |
| EFW | Economic Freedom Index | Annual | 1970-2023 |
| KOF | Globalization Index | Annual | 1970-2022 |

## Project Structure

```
fioracle/
├── main.py                    # Entry point
├── config/config.yaml         # All settings
├── src/core/                  # Core modules (6 files, 2,500 lines)
│   ├── data.py               # Data loading & alignment
│   ├── features.py           # Feature engineering
│   ├── regimes.py            # Regime identification
│   ├── portfolio.py          # Portfolio optimization
│   ├── evaluation.py         # Metrics & visualization
│   └── utils.py              # Shared utilities
├── notebooks/                 # 5 tutorials
├── output/                    # Results & figures
└── tests/                     # Test suite
```

## Configuration

Key parameters in `config/config.yaml`:

```yaml
data:
  mode: basic                  # or 'full'
  train_start: '1945-01-01'   # Training period
  train_end: '2000-12-31'
  val_start: '2001-01-01'     # Validation period
  val_end: '2010-12-31'

regimes:
  jump_model:
    default_lambda: 5.0        # Jump penalty (persistence)
  xgboost:
    max_depth: 5
    learning_rate: 0.1

portfolio:
  gamma_risk: 10.0             # Risk aversion
  max_weight: 0.40             # Max 40% per asset
  capital_preservation_threshold: 2
```

## Output

```
output/
├── results/{split}/
│   ├── asset_regimes.csv
│   ├── portfolio_weights.csv
│   ├── portfolio_returns.csv
│   └── performance_metrics.json
├── figures/{split}/
│   └── essential_plots.png
├── models/{split}/
│   ├── regime_forecasters.pkl
│   └── macro_hmm_model.pkl
└── regime_statistics/{split}/
    └── regime_statistics.json
```

## Features

- **Multi-source data**: 10+ datasets (GPR, EPU, Shiller, JST, EFW, KOF)
- **Smart caching**: Parquet format, 60x faster reloads
- **Three-layer regimes**: Asset, volatility, macro
- **XGBoost forecasting**: >97% accuracy
- **Capital preservation**: Only invests when ≥2 assets bullish
- **Hyperparameter tuning**: Time-series cross-validation
- **Walk-forward validation**: Realistic performance estimation

## Development

```bash
# Run tests
pytest tests/

# Code formatting
black src/

# Linting
flake8 src/
```

## References

- Caldara & Iacoviello (2022). *Measuring Geopolitical Risk*
- Baker, Bloom & Davis (2016). *Measuring Economic Policy Uncertainty*
- Jordà, Schularick & Taylor (2017). *Macrofinancial History*
- Shiller (2000). *Irrational Exuberance*

## License

Academic and research purposes.

---

**Get started:** `python main.py --mode basic --optimize-portfolio`
