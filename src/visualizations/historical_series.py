"""
Historical Time Series Visualization

Combines multiple asset and macro series in a single beautiful visualization:
1. Total return indices (log-scaled)
2. Macro indicators (smoothed and normalized for comparability)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from typing import Optional, Dict, List
import warnings
import yaml

warnings.filterwarnings('ignore')

# Professional color palette
COLORS = {
    'us_cash': '#2E86AB',
    'us_10y': '#A23B72',
    'us_agg': '#F18F01',
    'chf': '#C73E1D',
    'inflation': '#3B1F2B',
    'gpri': '#6B4226',
    'vix': '#9B5DE5',
    'background': '#FAFBFC',
    'grid': '#E5E7EB',
    'text': '#1F2937',
}


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent.parent / 'config' / 'config.yaml'
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}


def get_display_name(asset_name: str, config: dict) -> str:
    """Get display name from config or fallback."""
    asset_names = config.get('assets', {}).get('display_names', {})
    macro_names = config.get('macro', {}).get('display_names', {})
    
    # Check both asset and macro display names
    if asset_name in asset_names:
        return asset_names[asset_name]
    if asset_name in macro_names:
        return macro_names[asset_name]
    
    # Fallback
    fallbacks = {
        'US_CASH_RETURN': 'US T-Bills',
        'US_10Y_GOV_BOND_RETURN': 'US 10Y Treasury',
        'US_BOND_AGG_TOTAL_RETURN': 'US Aggregate Bond',
        'CHF_TOTAL_RETURN': 'Swiss Franc',
        'US_INFLATION_RATE': 'CPI Inflation',
        'GPRI': 'Geopolitical Risk',
        'VIX': 'VIX Index',
    }
    return fallbacks.get(asset_name, asset_name.replace('_', ' ').title())


def load_series_data(
    series_paths: Dict[str, str],
    start_date: str = '1945-01-01',
    end_date: str = '2025-12-31'
) -> Dict[str, pd.Series]:
    """Load multiple time series from CSV files."""
    data = {}
    
    # Convert date strings to datetime for proper comparison
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    for name, path in series_paths.items():
        try:
            df = pd.read_csv(path)
            
            # Find date column
            date_col = None
            for col in df.columns:
                if 'date' in col.lower():
                    date_col = col
                    break
            
            if date_col is None:
                date_col = df.columns[0]
            
            # Parse dates
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df = df.dropna(subset=[date_col])
            df = df.set_index(date_col)
            
            # Get value column (first non-date numeric column)
            value_col = None
            for col in df.columns:
                if df[col].dtype in [np.float64, np.int64, float, int]:
                    value_col = col
                    break
            
            if value_col is None:
                continue
            
            series = df[value_col].dropna()
            series = series[(series.index >= start_dt) & (series.index <= end_dt)]
            
            if len(series) > 100:
                data[name] = series
                
        except Exception as e:
            print(f"  Warning: Could not load {name}: {e}")
    
    return data


def create_combined_timeseries_plot(
    output_dir: str,
    start_date: str = '1945-01-01',
    end_date: str = '2025-12-31'
) -> None:
    """
    Create a beautiful combined time series visualization.
    
    Transforms:
    - Total return indices: log-scale (base 100)
    - Macro indicators: cumulative normalized (better for GPRI trends)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    config = load_config()
    base_dir = Path(__file__).parent.parent.parent
    
    # Define series paths (all available from 1945)
    asset_series = {
        'US_CASH_RETURN': base_dir / 'asset_universe' / 'US_CASH_RETURN.csv',
        'US_10Y_GOV_BOND_RETURN': base_dir / 'asset_universe' / 'US_10Y_GOV_BOND_RETURN.csv',
        'CHF_TOTAL_RETURN': base_dir / 'asset_universe' / 'CHF_TOTAL_RETURN.csv',
    }
    
    macro_series = {
        'US_INFLATION_RATE': base_dir / 'macro_universe' / 'US_INFLATION_RATE.csv',
        'GPRI': base_dir / 'macro_universe' / 'GPRI.csv',
        'VIX': base_dir / 'macro_universe' / 'VIX.csv',
    }
    
    # Load data
    print("Loading time series data...")
    asset_data = load_series_data({k: str(v) for k, v in asset_series.items()}, start_date, end_date)
    macro_data = load_series_data({k: str(v) for k, v in macro_series.items()}, start_date, end_date)
    
    if not asset_data and not macro_data:
        print("No data available for visualization")
        return
    
    # Create figure with two subplots (with independent x-axes)
    fig = plt.figure(figsize=(16, 12), facecolor=COLORS['background'])
    gs = fig.add_gridspec(2, 1, height_ratios=[2, 1], hspace=0.20)
    
    # =========================================================================
    # TOP PANEL: Total Return Indices (log scale)
    # =========================================================================
    ax1 = fig.add_subplot(gs[0])
    ax1.set_facecolor(COLORS['background'])
    
    asset_colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D']
    
    # Track date range for assets
    asset_min_date = pd.Timestamp('2100-01-01')
    asset_max_date = pd.Timestamp('1900-01-01')
    
    for i, (name, series) in enumerate(asset_data.items()):
        # Normalize to start at 100
        normalized = (series / series.iloc[0]) * 100
        display_name = get_display_name(name, config)
        color = asset_colors[i % len(asset_colors)]
        
        ax1.plot(normalized.index, normalized.values, 
                linewidth=2, label=display_name, color=color, alpha=0.9)
        
        # Update date range
        if series.index.min() < asset_min_date:
            asset_min_date = series.index.min()
        if series.index.max() > asset_max_date:
            asset_max_date = series.index.max()
    
    ax1.set_yscale('log')
    ax1.set_ylabel('Total Return Index (Log Scale, Base 100)', fontsize=12, fontweight='bold')
    
    # Determine asset date range for title
    asset_start_year = asset_min_date.year if asset_min_date.year < 2000 else 1945
    ax1.set_title(f'Fixed Income & Safe Haven Total Returns ({asset_start_year}–Present)', 
                 fontsize=16, fontweight='bold', pad=20)
    
    # Add legend
    ax1.legend(loc='upper left', frameon=True, fancybox=True, 
              shadow=True, fontsize=10, ncol=2)
    
    # Grid and styling
    ax1.grid(True, alpha=0.3, color=COLORS['grid'], linestyle='-')
    ax1.tick_params(axis='both', which='major', labelsize=10)
    
    # Format x-axis for assets
    ax1.xaxis.set_major_locator(mdates.YearLocator(10))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Add x-axis label showing data availability
    ax1.set_xlabel(f'Asset Data: {asset_min_date.strftime("%Y")} – {asset_max_date.strftime("%Y")}', 
                  fontsize=10, style='italic', color='gray')
    
    # Add final values annotation
    for i, (name, series) in enumerate(asset_data.items()):
        normalized = (series / series.iloc[0]) * 100
        final_val = normalized.iloc[-1]
        display_name = get_display_name(name, config)
        color = asset_colors[i % len(asset_colors)]
        
        ax1.annotate(f'{final_val:.0f}', 
                    xy=(normalized.index[-1], final_val),
                    xytext=(10, 0), textcoords='offset points',
                    fontsize=9, fontweight='bold', color=color,
                    va='center')
    
    # =========================================================================
    # BOTTOM PANEL: Macro Indicators (smoothed cumulative normalization)
    # =========================================================================
    ax2 = fig.add_subplot(gs[1])
    ax2.set_facecolor(COLORS['background'])
    
    macro_colors = ['#3B1F2B', '#6B4226', '#9B5DE5']
    
    # Track date range for macro
    macro_min_date = pd.Timestamp('2100-01-01')
    macro_max_date = pd.Timestamp('1900-01-01')
    
    for i, (name, series) in enumerate(macro_data.items()):
        display_name = get_display_name(name, config)
        color = macro_colors[i % len(macro_colors)]
        
        # Update date range
        if series.index.min() < macro_min_date:
            macro_min_date = series.index.min()
        if series.index.max() > macro_max_date:
            macro_max_date = series.index.max()
        
        # Apply appropriate smoothing based on series type
        if 'GPR' in name.upper():
            # GPRI: Use heavy exponential smoothing + percentile normalization
            # This reduces volatility and shows clear trends
            smoothed = series.ewm(span=63, min_periods=20).mean()  # ~3-month EMA
            
            # Normalize to 0-100 percentile scale
            normalized = (smoothed.rank(pct=True) - 0.5) * 8  # Scale to roughly ±4
            
            ax2.plot(normalized.index, normalized.values,
                    linewidth=2, label=f'{display_name} (Smoothed Percentile)', color=color, alpha=0.8)
        else:
            # For VIX and Inflation: Use rolling z-score with smoothing
            smoothed = series.ewm(span=21, min_periods=10).mean()  # ~1-month EMA first
            rolling_mean = smoothed.rolling(window=252, min_periods=50).mean()
            rolling_std = smoothed.rolling(window=252, min_periods=50).std()
            z_score = (smoothed - rolling_mean) / (rolling_std + 1e-8)
            
            # Clip extreme values
            z_score = z_score.clip(-4, 4)
            
            ax2.plot(z_score.index, z_score.values,
                    linewidth=1.5, label=f'{display_name} (Z-Score)', color=color, alpha=0.8)
    
    ax2.axhline(0, color='black', linestyle='-', alpha=0.3, linewidth=1)
    ax2.axhline(2, color='red', linestyle='--', alpha=0.4, linewidth=1, label='Elevated (+2σ)')
    ax2.axhline(-2, color='green', linestyle='--', alpha=0.4, linewidth=1, label='Low (-2σ)')
    
    ax2.set_ylabel('Normalized Value', fontsize=12, fontweight='bold')
    ax2.set_title('Macro Indicators: Inflation, Geopolitical Risk & Volatility', 
                 fontsize=14, fontweight='bold', pad=10)
    
    ax2.legend(loc='upper left', frameon=True, fancybox=True, 
              fontsize=9, ncol=3)
    ax2.grid(True, alpha=0.3, color=COLORS['grid'], linestyle='-')
    ax2.set_ylim(-4.5, 4.5)
    
    # Format x-axis for macro panel
    ax2.xaxis.set_major_locator(mdates.YearLocator(5))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Add x-axis label showing macro data availability
    ax2.set_xlabel(f'Macro Data: {macro_min_date.strftime("%Y")} – {macro_max_date.strftime("%Y")}', 
                  fontsize=10, style='italic', color='gray')
    
    # Add historical event annotations
    events = [
        ('1973-10-01', 'Oil Crisis'),
        ('1979-01-01', 'Volcker'),
        ('2001-09-11', '9/11'),
        ('2008-09-15', 'GFC'),
        ('2020-03-01', 'COVID'),
        ('2022-02-24', 'Ukraine'),
    ]
    
    for date_str, label in events:
        try:
            event_date = pd.Timestamp(date_str)
            xlim = ax2.get_xlim()
            if event_date.toordinal() >= xlim[0] and event_date.toordinal() <= xlim[1]:
                ax2.axvline(event_date, color='gray', linestyle=':', alpha=0.5, linewidth=1)
                ax2.annotate(label, xy=(event_date, 3.8),
                           fontsize=7, rotation=90, va='top', ha='right',
                           color='gray', alpha=0.7)
        except:
            pass
    
    plt.tight_layout()
    plt.savefig(output_path / 'combined_historical_series.png', dpi=200, bbox_inches='tight',
               facecolor=COLORS['background'])
    plt.close()
    
    print(f"  ✓ Combined historical series saved to {output_path / 'combined_historical_series.png'}")


def create_regime_prediction_timeline(
    output_dir: str,
    start_date: str = '1945-01-01',
    end_date: str = '2025-12-31'
) -> None:
    """
    Create separate regime prediction timeline plots for each asset.
    
    For assets:
    - US_10Y_GOV_BOND_RETURN
    - US_BOND_AGG_TOTAL_RETURN
    - CHF_TOTAL_RETURN
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from core.data import DataPipeline
    from core.features import engineer_features
    from core.regimes import JumpModel, RegimeEngine
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    config = load_config()
    
    # Target assets (keys match feature dictionary format without _RETURN suffix)
    target_assets = [
        'US_10Y_GOV_BOND',
        'US_BOND_AGG', 
        'CHF'
    ]
    
    print("Loading data for regime analysis...")
    
    # Load data
    try:
        pipeline = DataPipeline()
        data = pipeline.load(start_date=start_date, end_date=end_date)
        
        if data.empty:
            print("No data available for regime analysis")
            return
        
        # Engineer features
        asset_features, macro_features = engineer_features(data)
        
        # Build returns
        asset_returns = {}
        for col in data.columns:
            if col.startswith('asset_'):
                asset_name = col.replace('asset_', '').upper()
                asset_returns[asset_name] = data[col].pct_change()
        
        returns_df = pd.DataFrame(asset_returns)
        
    except Exception as e:
        print(f"Data loading failed: {e}")
        return
    
    # Get config parameters
    jm_cfg = config.get('regimes', {}).get('jump_model', {})
    lambda_jump = jm_cfg.get('default_lambda', 5.0)
    n_states = jm_cfg.get('n_states', 3)
    
    print(f"Computing regimes with λ={lambda_jump}, n_states={n_states}...")
    
    regime_colors = {0: '#38A169', 1: '#ECC94B', 2: '#E53E3E'}  # Calm, Inflationary, Crisis
    regime_names = {0: 'Calm', 1: 'Inflationary', 2: 'Crisis'}
    
    for asset_name in target_assets:
        if asset_name not in asset_features:
            print(f"  {asset_name}: No features available")
            continue
        
        if asset_name not in returns_df.columns:
            print(f"  {asset_name}: No returns available")
            continue
        
        try:
            features = asset_features[asset_name].dropna()
            returns = returns_df[asset_name].reindex(features.index)
            
            if len(features) < 500:
                print(f"  {asset_name}: Insufficient data ({len(features)} rows)")
                continue
            
            # Fit Jump Model
            jm = JumpModel(lambda_jump=lambda_jump, n_states=n_states)
            jm_states = jm.fit(features.values)
            jm_regimes = pd.Series(jm_states, index=features.index)
            
            # Assign semantic labels
            state_returns = {}
            for state in range(n_states):
                mask = (jm_regimes == state)
                state_returns[state] = returns[mask].mean()
            
            sorted_states = sorted(state_returns.keys(), key=lambda s: state_returns[s], reverse=True)
            remap = {old: new for new, old in enumerate(sorted_states)}
            jm_regimes = jm_regimes.map(remap)
            
            # Train XGBoost forecaster
            engine = RegimeEngine(lambda_jump=lambda_jump, config=config)
            asset_regimes = {asset_name: jm_regimes}
            
            engine.fit_forecasters(
                {asset_name: features},
                asset_regimes,
                macro_features.reindex(features.index).ffill(),
                asset_returns_dict={asset_name: returns},
                test_size=0.2,
                verbose=False
            )
            
            # Generate XGBoost predictions
            xgb_regimes = pd.Series(index=features.index, dtype=float)
            
            if asset_name in engine.classifiers:
                model = engine.classifiers[asset_name]
                
                X = pd.DataFrame(index=features.index)
                for col in features.columns:
                    X[col] = features[col]
                
                macro_aligned = macro_features.reindex(features.index).ffill()
                for col in macro_aligned.columns:
                    X[f'macro_{col}'] = macro_aligned[col]
                
                X = X.dropna()
                
                if len(X) > 0:
                    preds = model.predict(X.values)
                    xgb_regimes = pd.Series(preds, index=X.index)
            
            # Create individual plot for this asset
            display_name = get_display_name(asset_name, config)
            
            fig, ax = plt.subplots(figsize=(16, 5), facecolor='#FAFBFC')
            ax.set_facecolor('#FAFBFC')
            
            # Plot Jump Model regimes (top half)
            for regime in range(n_states):
                mask = (jm_regimes == regime)
                if mask.any():
                    ax.fill_between(jm_regimes.index, 0.5, 1.0, where=mask, 
                                  color=regime_colors.get(regime, 'gray'), alpha=0.6,
                                  step='mid')
            
            # Plot XGBoost regimes (bottom half)
            for regime in range(n_states):
                mask = (xgb_regimes == regime)
                if mask.any():
                    ax.fill_between(xgb_regimes.index, 0.0, 0.5, where=mask,
                                  color=regime_colors.get(regime, 'gray'), alpha=0.6,
                                  step='mid')
            
            # Separator line
            ax.axhline(0.5, color='white', linewidth=2)
            
            # Labels
            ax.set_ylabel('Model', fontsize=12, fontweight='bold')
            ax.set_ylim(0, 1)
            ax.set_yticks([0.25, 0.75])
            ax.set_yticklabels(['XGBoost', 'Jump Model'], fontsize=10)
            
            ax.set_title(f'{display_name}: Regime Predictions (3-State Model)\n'
                        'Green=Calm | Yellow=Inflationary | Red=Crisis',
                        fontsize=14, fontweight='bold', pad=15)
            
            ax.grid(True, alpha=0.3, axis='x')
            
            # Format x-axis
            ax.xaxis.set_major_locator(mdates.YearLocator(5))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
            ax.set_xlabel('Date', fontsize=12, fontweight='bold')
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
            # Add legend
            from matplotlib.patches import Patch
            legend_elements = [Patch(facecolor=regime_colors[i], alpha=0.6, label=regime_names[i])
                              for i in range(n_states)]
            ax.legend(handles=legend_elements, loc='upper right', fontsize=9, ncol=3)
            
            # Save individual plot
            safe_name = asset_name.replace('/', '_').replace(' ', '_')
            plt.tight_layout()
            plt.savefig(output_path / f'regime_timeline_{safe_name}.png', dpi=200, bbox_inches='tight',
                       facecolor='#FAFBFC')
            plt.close()
            
            print(f"  ✓ {asset_name}: Regime timeline saved")
            
        except Exception as e:
            print(f"  {asset_name}: Failed - {e}")
    
    print(f"  ✓ Individual regime timelines saved to {output_path}")


if __name__ == '__main__':
    import sys
    output_dir = sys.argv[1] if len(sys.argv) > 1 else 'output/figures/historical'
    
    create_combined_timeseries_plot(output_dir)
    create_regime_prediction_timeline(output_dir)
