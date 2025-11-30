"""
VIX Effectiveness Analysis

Analyzes how VIX affects model performance and portfolio allocations.
Produces visualizations showing:
1. VIX vs Portfolio Returns correlation
2. Regime detection accuracy by VIX level
3. Allocation shifts during VIX spikes
4. Historical VIX events and model response
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from typing import Optional, Dict
import warnings
import yaml

warnings.filterwarnings('ignore')

# Color scheme
COLORS = {
    'vix_low': '#38a169',      # Green - calm markets
    'vix_mid': '#d69e2e',      # Yellow - elevated
    'vix_high': '#e53e3e',     # Red - crisis
    'vix_line': '#805ad5',     # Purple
    'portfolio': '#1a365d',    # Navy
    'benchmark': '#718096',    # Gray
    'grid': '#e2e8f0'
}

VIX_THRESHOLDS = {
    'low': 15,
    'elevated': 25,
    'high': 35
}


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent.parent / 'config' / 'config.yaml'
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}


def _get_display_name(asset_name: str, config: dict) -> str:
    """Get human-readable display name from config."""
    asset_names = config.get('assets', {}).get('display_names', {})
    asset_upper = asset_name.upper()
    
    if asset_upper in asset_names:
        return asset_names[asset_upper]
    
    for suffix in ['', '_TOTAL_RETURN', '_RETURN']:
        test_name = asset_upper + suffix
        if test_name in asset_names:
            return asset_names[test_name]
    
    fallbacks = {
        'US_CASH_RETURN': 'US T-Bills',
        'US_10Y_GOV_BOND_RETURN': 'US 10Y Treasury',
        'US_BOND_AGG_TOTAL_RETURN': 'US Aggregate Bond',
        'GOLD_TOTAL_RETURN': 'Gold',
        'CHF_TOTAL_RETURN': 'Swiss Franc',
        'US_TIPS_0_5_TOTAL_RETURN': 'US TIPS 0-5Y',
        'WTI_TOTAL_RETURN': 'WTI Crude Oil',
    }
    
    if asset_upper in fallbacks:
        return fallbacks[asset_upper]
    
    clean = asset_name.replace('_TOTAL_RETURN', '').replace('_RETURN', '').replace('_', ' ')
    return clean.title()[:20]


def analyze_vix_effectiveness(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    vix_data: pd.Series,
    weights_df: pd.DataFrame,
    regimes_df: pd.DataFrame,
    output_dir: str,
    strategy_name: str = "Strategy",
    all_strategy_returns: Optional[Dict[str, pd.Series]] = None
) -> Dict:
    """
    Run comprehensive VIX effectiveness analysis.
    
    Args:
        portfolio_returns: Strategy returns series
        benchmark_returns: Benchmark returns series
        vix_data: VIX level time series
        weights_df: Portfolio weights over time
        regimes_df: Regime classifications
        output_dir: Directory to save figures
        strategy_name: Name for labeling
        all_strategy_returns: Dict of all strategy returns for comparison
    
    Returns:
        Dict of analysis metrics
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    config = load_config()
    
    # Handle None/empty inputs
    if vix_data is None or len(vix_data) == 0:
        print("VIX data not available for analysis")
        return {}
    if portfolio_returns is None or len(portfolio_returns) == 0:
        print("Portfolio returns not available for VIX analysis")
        return {}
    
    # Remove NaN values from VIX before computing intersection
    vix_data_clean = vix_data.dropna()
    if len(vix_data_clean) == 0:
        print("VIX data is all NaN")
        return {}
    
    # Align all data
    common_idx = portfolio_returns.index.intersection(vix_data_clean.index)
    if len(common_idx) < 100:
        print(f"Insufficient overlapping data for VIX analysis ({len(common_idx)} days)")
        return {}
    
    portfolio = portfolio_returns.loc[common_idx].dropna()
    vix = vix_data_clean.loc[common_idx]
    
    # Re-check after dropna
    common_idx = portfolio.index.intersection(vix.index)
    if len(common_idx) < 100:
        print(f"Insufficient clean data for VIX analysis ({len(common_idx)} days)")
        return {}
    
    portfolio = portfolio.loc[common_idx]
    vix = vix.loc[common_idx]
    bench = benchmark_returns.reindex(common_idx).fillna(0) if benchmark_returns is not None else pd.Series(0, index=common_idx)
    
    # Find best performing strategy if multiple available
    best_strategy_name = strategy_name
    best_strategy_returns = portfolio
    
    if all_strategy_returns:
        best_total_return = -np.inf
        for name, returns in all_strategy_returns.items():
            if returns is not None and len(returns) > 0:
                aligned_returns = returns.reindex(common_idx).dropna()
                if len(aligned_returns) > 0:
                    total_ret = (1 + aligned_returns).prod() - 1
                    if total_ret > best_total_return:
                        best_total_return = total_ret
                        best_strategy_name = name
                        best_strategy_returns = aligned_returns
        
        portfolio = best_strategy_returns.reindex(common_idx).fillna(0)
    
    results = {}
    
    # 1. VIX Regime Classification
    vix_regime = pd.Series(index=common_idx, dtype=str)
    vix_regime[vix <= VIX_THRESHOLDS['low']] = 'Low (≤15)'
    vix_regime[(vix > VIX_THRESHOLDS['low']) & (vix <= VIX_THRESHOLDS['elevated'])] = 'Elevated (15-25)'
    vix_regime[(vix > VIX_THRESHOLDS['elevated']) & (vix <= VIX_THRESHOLDS['high'])] = 'High (25-35)'
    vix_regime[vix > VIX_THRESHOLDS['high']] = 'Crisis (>35)'
    
    # 2. Performance by VIX Regime
    results['performance_by_vix'] = _compute_performance_by_vix(portfolio, bench, vix_regime)
    
    # 3. Generate visualizations (removed unwanted plots)
    _plot_vix_regime_returns(portfolio, bench, vix_regime, output_path, best_strategy_name)
    _plot_vix_vs_allocation(weights_df, vix, output_path, config)
    _plot_vix_events_timeline(portfolio, vix, weights_df, output_path, best_strategy_name, config)
    
    # 4. Summary statistics
    results['vix_correlation'] = portfolio.corr(vix)
    results['vix_beta'] = _compute_vix_beta(portfolio, vix)
    results['best_strategy'] = best_strategy_name
    
    print(f"VIX Analysis complete. Figures saved to {output_path}")
    return results


def _compute_performance_by_vix(portfolio, benchmark, vix_regime):
    """Compute performance metrics by VIX regime."""
    results = {}
    for regime in vix_regime.unique():
        mask = vix_regime == regime
        if mask.sum() < 20:
            continue
            
        port_ret = portfolio[mask]
        bench_ret = benchmark[mask]
        
        results[regime] = {
            'n_days': int(mask.sum()),
            'strategy_return': float(port_ret.mean() * 252),
            'benchmark_return': float(bench_ret.mean() * 252),
            'strategy_vol': float(port_ret.std() * np.sqrt(252)),
            'benchmark_vol': float(bench_ret.std() * np.sqrt(252)),
            'strategy_sharpe': float(port_ret.mean() / (port_ret.std() + 1e-10) * np.sqrt(252)),
            'excess_return': float((port_ret.mean() - bench_ret.mean()) * 252)
        }
    return results


def _compute_vix_beta(returns, vix):
    """Compute beta of returns to VIX changes."""
    vix_changes = vix.pct_change().fillna(0)
    common = returns.index.intersection(vix_changes.index)
    if len(common) < 100:
        return np.nan
    
    cov = np.cov(returns.loc[common], vix_changes.loc[common])[0, 1]
    var = np.var(vix_changes.loc[common])
    return cov / (var + 1e-10)


def _plot_vix_regime_returns(portfolio, benchmark, vix_regime, output_path, strategy_name):
    """Bar chart comparing strategy vs benchmark by VIX regime."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    regimes = ['Low (≤15)', 'Elevated (15-25)', 'High (25-35)', 'Crisis (>35)']
    
    # Align data
    common_idx = portfolio.index.intersection(benchmark.index).intersection(vix_regime.index)
    if len(common_idx) < 30:
        ax.text(0.5, 0.5, 'Insufficient data for VIX regime comparison', 
               ha='center', va='center', fontsize=14)
        plt.savefig(output_path / 'vix_regime_comparison.png', dpi=150, bbox_inches='tight')
        plt.close()
        return
    
    portfolio_aligned = portfolio.loc[common_idx]
    benchmark_aligned = benchmark.loc[common_idx]
    vix_regime_aligned = vix_regime.loc[common_idx]
    
    port_returns = []
    bench_returns = []
    valid_regimes = []
    
    for regime in regimes:
        mask = vix_regime_aligned == regime
        if mask.sum() >= 10:
            port_returns.append(portfolio_aligned[mask].mean() * 252 * 100)
            bench_returns.append(benchmark_aligned[mask].mean() * 252 * 100)
            valid_regimes.append(regime)
    
    if len(valid_regimes) == 0:
        ax.text(0.5, 0.5, 'No VIX regimes with sufficient data', 
               ha='center', va='center', fontsize=14)
        plt.savefig(output_path / 'vix_regime_comparison.png', dpi=150, bbox_inches='tight')
        plt.close()
        return
    
    x = np.arange(len(valid_regimes))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, port_returns, width, label=strategy_name, 
                  color=COLORS['portfolio'], edgecolor='white')
    bars2 = ax.bar(x + width/2, bench_returns, width, label='Benchmark',
                  color=COLORS['benchmark'], edgecolor='white', alpha=0.7)
    
    # Color code based on outperformance
    for i, (p, b) in enumerate(zip(port_returns, bench_returns)):
        if p > b:
            bars1[i].set_edgecolor(COLORS['vix_low'])
            bars1[i].set_linewidth(3)
    
    ax.set_xticks(x)
    ax.set_xticklabels(valid_regimes)
    ax.set_xlabel('VIX Regime', fontsize=12)
    ax.set_ylabel('Annualized Return (%)', fontsize=12)
    ax.set_title(f'{strategy_name} vs Benchmark by VIX Regime', fontsize=14, fontweight='bold')
    ax.legend()
    ax.axhline(0, color='black', linestyle='-', alpha=0.3)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path / 'vix_regime_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()


def _plot_vix_vs_allocation(weights_df, vix, output_path, config):
    """Scatter plot of VIX vs cash/safe-haven allocation."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Resample to weekly for cleaner visualization
    weights_weekly = weights_df.resample('W').mean()
    vix_weekly = vix.resample('W').mean()
    
    common_idx = weights_weekly.index.intersection(vix_weekly.index)
    if len(common_idx) < 10:
        plt.close()
        return
    
    weights_aligned = weights_weekly.loc[common_idx]
    vix_aligned = vix_weekly.loc[common_idx]
    
    # Calculate total risky allocation
    risky_cols = [c for c in weights_aligned.columns if 'rf' not in c.lower() and 'cash' not in c.lower()]
    total_risky = weights_aligned[risky_cols].sum(axis=1)
    
    # Left plot: VIX vs Risky Allocation
    ax1 = axes[0]
    colors = [COLORS['vix_low'] if v <= 15 else COLORS['vix_mid'] if v <= 30 else COLORS['vix_high']
              for v in vix_aligned]
    ax1.scatter(vix_aligned, total_risky * 100, c=colors, alpha=0.6, s=30)
    
    try:
        z = np.polyfit(vix_aligned.values, (total_risky * 100).values, 1, rcond=1e-10)
        p = np.poly1d(z)
        sorted_vix = sorted(vix_aligned)
        ax1.plot(sorted_vix, p(sorted_vix), 
                 color=COLORS['vix_line'], linewidth=2, linestyle='--', label=f'Trend (β={z[0]:.2f})')
    except (np.linalg.LinAlgError, ValueError):
        pass
    
    ax1.set_xlabel('VIX Level', fontsize=12)
    ax1.set_ylabel('Risky Allocation (%)', fontsize=12)
    ax1.set_title('VIX vs Risk Appetite', fontsize=13, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Right plot: VIX change vs Allocation change
    ax2 = axes[1]
    vix_change = vix_aligned.diff().dropna()
    alloc_change = total_risky.diff().dropna() * 100
    
    common = vix_change.index.intersection(alloc_change.index)
    ax2.scatter(vix_change.loc[common], alloc_change.loc[common], 
               alpha=0.5, s=30, color=COLORS['portfolio'])
    
    corr = vix_change.loc[common].corr(alloc_change.loc[common])
    ax2.annotate(f'Correlation: {corr:.3f}', xy=(0.05, 0.95), xycoords='axes fraction',
                fontsize=11, fontweight='bold', 
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    ax2.axhline(0, color='gray', linestyle='-', alpha=0.3)
    ax2.axvline(0, color='gray', linestyle='-', alpha=0.3)
    ax2.set_xlabel('Weekly VIX Change', fontsize=12)
    ax2.set_ylabel('Weekly Allocation Change (%)', fontsize=12)
    ax2.set_title('Model Response to VIX Changes', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path / 'vix_allocation_scatter.png', dpi=150, bbox_inches='tight')
    plt.close()


def _plot_vix_events_timeline(portfolio, vix, weights_df, output_path, strategy_name, config):
    """Timeline showing VIX level and asset allocation timeline."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    
    # Panel 1: VIX Level
    ax1 = axes[0]
    vix_clean = vix.dropna()
    
    if len(vix_clean) > 0:
        ax1.fill_between(vix_clean.index, vix_clean.values, alpha=0.3, color=COLORS['vix_line'])
        ax1.plot(vix_clean.index, vix_clean.values, color=COLORS['vix_line'], linewidth=1.5)
        ax1.axhline(VIX_THRESHOLDS['elevated'], color=COLORS['vix_mid'], linestyle='--', alpha=0.7, label='Elevated (25)')
        ax1.axhline(VIX_THRESHOLDS['high'], color=COLORS['vix_high'], linestyle='--', alpha=0.7, label='High (35)')
        
        # Mark VIX spikes
        vix_spikes = vix_clean[vix_clean > VIX_THRESHOLDS['high']]
        if len(vix_spikes) > 0:
            ax1.scatter(vix_spikes.index, vix_spikes.values, color=COLORS['vix_high'], 
                       s=50, zorder=5, marker='^', label='Crisis Events')
    
    ax1.set_ylabel('VIX Level', fontsize=11)
    ax1.set_title('VIX Timeline and Portfolio Response', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=9)
    ax1.grid(True, alpha=0.3)
    
    # Panel 2: Asset Allocation Timeline (instead of cumulative wealth)
    ax2 = axes[1]
    
    # Filter asset columns and process weights
    excluded_patterns = ['cash_allocation', 'date', 'risk_free', 'sp500', 'yield', 'ancillary']
    asset_cols = [c for c in weights_df.columns
                 if not any(p in c.lower() for p in excluded_patterns)]
    
    if len(asset_cols) > 0:
        weights_weekly = weights_df[asset_cols].resample('W').mean()
        
        # Add cash allocation
        total_risky = weights_weekly.sum(axis=1)
        cash_allocation = (1 - total_risky).clip(lower=0)
        if cash_allocation.mean() > 0.01:
            weights_weekly['Uninvested Cash'] = cash_allocation
        
        # Filter zero columns
        weights_weekly = weights_weekly.loc[:, (weights_weekly > 0.001).any()]
        
        # Get display labels
        display_labels = [_get_display_name(c, config) if c != 'Uninvested Cash' else c
                        for c in weights_weekly.columns]
        
        # Use consistent colors
        n_cols = len(weights_weekly.columns)
        colors = plt.cm.Set3(np.linspace(0, 1, n_cols))
        
        ax2.stackplot(weights_weekly.index, weights_weekly.values.T,
                     labels=display_labels, colors=colors, alpha=0.8)
        
        # Highlight VIX spike periods
        for spike_date in vix_spikes.index[:10] if len(vix_spikes) > 0 else []:
            ax2.axvline(spike_date, color=COLORS['vix_high'], alpha=0.3, linewidth=1)
    
    ax2.set_ylabel('Asset Allocation', fontsize=11)
    ax2.set_ylim(0, 1.05)
    ax2.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=8)
    ax2.grid(True, alpha=0.3)
    
    # Panel 3: Rolling 30-day Return
    ax3 = axes[2]
    rolling_ret = portfolio.rolling(30).sum() * 100
    ax3.fill_between(rolling_ret.index, rolling_ret.values, 0, 
                    where=rolling_ret >= 0, color=COLORS['vix_low'], alpha=0.5)
    ax3.fill_between(rolling_ret.index, rolling_ret.values, 0,
                    where=rolling_ret < 0, color=COLORS['vix_high'], alpha=0.5)
    ax3.axhline(0, color='black', linestyle='-', alpha=0.3)
    ax3.set_ylabel('30-Day Return (%)', fontsize=11)
    ax3.set_xlabel('Date', fontsize=11)
    ax3.grid(True, alpha=0.3)
    
    # Smart date axis
    date_range = (portfolio.index[-1] - portfolio.index[0]).days
    if date_range > 365 * 10:
        ax3.xaxis.set_major_locator(mdates.YearLocator(5))
    elif date_range > 365 * 5:
        ax3.xaxis.set_major_locator(mdates.YearLocator(2))
    else:
        ax3.xaxis.set_major_locator(mdates.YearLocator(1))
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    
    plt.tight_layout()
    plt.savefig(output_path / 'vix_events_timeline.png', dpi=150, bbox_inches='tight')
    plt.close()
