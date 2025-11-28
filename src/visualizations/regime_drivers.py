#!/usr/bin/env python3
"""
Regime Drivers Visualization - Separate Plot Files

Creates individual, publication-quality visualizations:
1. Macro risk indicators (VIX, GPR, Debt/GDP)
2. Regime distribution by asset
3. Regime transition analysis
4. Asset regime timeline heatmap
5. Cumulative wealth with regime overlay

Each plot saved as separate file for flexibility.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import LinearSegmentedColormap
import seaborn as sns
import warnings

warnings.filterwarnings('ignore')

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import DataPipeline, engineer_features, RegimeEngine

# Color palette
COLORS = {
    'bull': '#3fb950',
    'bear': '#f85149',
    'neutral': '#58a6ff',
    'gpr': '#f97316',
    'vix': '#ef4444',
    'debt': '#a855f7',
    'primary': '#3b82f6',
    'secondary': '#10b981',
}


def visualize_regime_drivers(
    start_date='2005-01-01',
    end_date='2020-12-31',
    output_dir='output/figures/regime_analysis',
    show_plot=False
):
    """
    Create comprehensive regime driver visualizations as SEPARATE files.
    """
    print("="*70)
    print("REGIME DRIVERS VISUALIZATION")
    print("="*70)
    print(f"Period: {start_date} to {end_date}")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load data
    print("\nLoading data...")
    pipeline = DataPipeline()
    data = pipeline.load(start_date, end_date)
    
    if len(data) == 0:
        print("No data available")
        return None
    
    # Engineer features
    print("Engineering features...")
    asset_features, macro_features = engineer_features(data)
    
    # Build returns
    risk_free_col = [c for c in data.columns if 'risk_free' in c]
    rf_returns = data[risk_free_col[0]].pct_change() if risk_free_col else 0
    
    asset_returns = {}
    for col in data.columns:
        if col.startswith('asset_') and 'yield' not in col.lower() and 'slope' not in col.lower():
            if risk_free_col and col == risk_free_col[0]:
                continue
            asset_return = data[col].pct_change()
            excess_return = asset_return - rf_returns if isinstance(rf_returns, pd.Series) else asset_return
            asset_name = col.replace('asset_', '').upper()
            if asset_name in asset_features:
                asset_returns[asset_name] = excess_return
    
    if not asset_returns:
        print("No asset returns computed")
        return None
    
    returns_df = pd.DataFrame(asset_returns)
    
    # Identify regimes
    print("Identifying regimes...")
    engine = RegimeEngine(lambda_jump=5.0, n_macro_regimes=3)
    results = engine.fit_identify_forecast(
        asset_features, returns_df, macro_features, verbose=False
    )
    
    regimes_df = pd.DataFrame(results['asset_regimes'])
    
    # Extract macro indicators
    gpr = _get_column(data, ['macro_gpr', 'macro_gprd'])
    vix = _get_column(data, ['macro_vix', 'macro_cboe_vix'])
    debt = _get_column(data, ['macro_us_debt_to_gdp', 'macro_debt_gdp'])
    
    print("\nGenerating separate plots...")
    
    # 1. Macro Risk Indicators
    _plot_macro_indicators(gpr, vix, debt, output_path)
    
    # 2. Regime Distribution
    _plot_regime_distribution(regimes_df, output_path)
    
    # 3. Regime Transitions
    _plot_regime_transitions(regimes_df, output_path)
    
    # 4. Regime Timeline Heatmap
    _plot_regime_timeline(regimes_df, output_path)
    
    # 5. Wealth with Regimes
    _plot_wealth_with_regimes(returns_df, regimes_df, output_path)
    
    print(f"\n✓ All plots saved to {output_path}")
    print("="*70)
    
    if show_plot:
        plt.show()
    
    return output_path


def _get_column(data, candidates):
    """Get first matching column."""
    for name in candidates:
        matches = [c for c in data.columns if name.lower() in c.lower()]
        if matches:
            return data[matches[0]].dropna()
    return None


def _plot_macro_indicators(gpr, vix, debt, output_path):
    """Plot macro risk indicators - separate file."""
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    
    if vix is not None and len(vix) > 0:
        ax = axes[0]
        ax.plot(vix.index, vix.values, color=COLORS['vix'], linewidth=1.5)
        ax.fill_between(vix.index, 0, vix.values, alpha=0.3, color=COLORS['vix'])
        ax.set_title('VIX - Market Volatility Index', fontsize=12, fontweight='bold')
        ax.set_ylabel('VIX Level')
        ax.axhline(20, color='gray', linestyle='--', alpha=0.5, label='Normal (20)')
        ax.axhline(30, color='orange', linestyle='--', alpha=0.5, label='Elevated (30)')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)
    
    if gpr is not None and len(gpr) > 0:
        ax = axes[1]
        gpr_norm = (gpr - gpr.mean()) / gpr.std()
        ax.plot(gpr_norm.index, gpr_norm.values, color=COLORS['gpr'], linewidth=1.5)
        ax.fill_between(gpr_norm.index, 0, gpr_norm.values, 
                       where=gpr_norm.values > 0, alpha=0.3, color=COLORS['gpr'])
        ax.set_title('Geopolitical Risk Index (Normalized)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Std Deviations')
        ax.axhline(0, color='gray', linestyle='-', alpha=0.5)
        ax.axhline(2, color='red', linestyle='--', alpha=0.5, label='High Risk (+2σ)')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)
    
    if debt is not None and len(debt) > 0:
        ax = axes[2]
        ax.plot(debt.index, debt.values, color=COLORS['debt'], linewidth=1.5)
        ax.fill_between(debt.index, debt.values.min(), debt.values, alpha=0.3, color=COLORS['debt'])
        ax.set_title('US Debt to GDP Ratio', fontsize=12, fontweight='bold')
        ax.set_ylabel('Debt/GDP (%)')
        ax.grid(True, alpha=0.3)
    
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    axes[-1].xaxis.set_major_locator(mdates.YearLocator(2))
    
    fig.suptitle('Macroeconomic Risk Indicators', fontsize=14, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(output_path / 'macro_indicators.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✓ macro_indicators.png")


def _plot_regime_distribution(regimes_df, output_path):
    """Plot regime distribution by asset."""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    regime_pcts = {}
    for col in regimes_df.columns:
        series = regimes_df[col].dropna()
        if len(series) > 0:
            regime_pcts[col] = (series == 0).sum() / len(series) * 100
    
    if not regime_pcts:
        plt.close()
        return
    
    sorted_assets = sorted(regime_pcts.keys(), key=lambda x: regime_pcts[x], reverse=True)
    bull_pcts = [regime_pcts[a] for a in sorted_assets]
    bear_pcts = [100 - regime_pcts[a] for a in sorted_assets]
    
    y_pos = np.arange(len(sorted_assets))
    
    ax.barh(y_pos, bull_pcts, color=COLORS['bull'], alpha=0.8, label='Bullish')
    ax.barh(y_pos, bear_pcts, left=bull_pcts, color=COLORS['bear'], alpha=0.8, label='Bearish')
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(sorted_assets)
    ax.set_xlabel('Time in Regime (%)')
    ax.set_xlim(0, 100)
    ax.set_title('Regime Distribution by Asset', fontsize=14, fontweight='bold')
    ax.legend(loc='lower right')
    
    for i, (bull, bear) in enumerate(zip(bull_pcts, bear_pcts)):
        if bull > 10:
            ax.text(bull/2, i, f'{bull:.0f}%', ha='center', va='center', 
                   fontsize=9, fontweight='bold', color='white')
        if bear > 10:
            ax.text(bull + bear/2, i, f'{bear:.0f}%', ha='center', va='center',
                   fontsize=9, fontweight='bold', color='white')
    
    plt.tight_layout()
    plt.savefig(output_path / 'regime_distribution.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✓ regime_distribution.png")


def _plot_regime_transitions(regimes_df, output_path):
    """Plot regime transition analysis."""
    fig, ax = plt.subplots(figsize=(14, 6))
    
    transitions = {}
    for col in regimes_df.columns:
        series = regimes_df[col].dropna()
        if len(series) > 0:
            n_switches = (series != series.shift(1)).sum() - 1
            avg_duration = len(series) / max(n_switches, 1)
            transitions[col] = {'switches': n_switches, 'duration': avg_duration}
    
    if not transitions:
        plt.close()
        return
    
    assets = list(transitions.keys())
    switches = [transitions[a]['switches'] for a in assets]
    durations = [transitions[a]['duration'] for a in assets]
    
    x = np.arange(len(assets))
    width = 0.35
    
    ax2 = ax.twinx()
    
    bars1 = ax.bar(x - width/2, switches, width, color=COLORS['primary'], alpha=0.8, label='Regime Switches')
    bars2 = ax2.bar(x + width/2, durations, width, color=COLORS['secondary'], alpha=0.8, label='Avg Duration')
    
    ax.set_xlabel('Asset')
    ax.set_ylabel('Number of Switches', color=COLORS['primary'])
    ax2.set_ylabel('Avg Regime Duration (days)', color=COLORS['secondary'])
    
    ax.set_xticks(x)
    ax.set_xticklabels(assets, rotation=45, ha='right')
    ax.set_title('Regime Persistence Analysis', fontsize=14, fontweight='bold')
    
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
    
    plt.tight_layout()
    plt.savefig(output_path / 'regime_transitions.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✓ regime_transitions.png")


def _plot_regime_timeline(regimes_df, output_path):
    """Plot regime timeline heatmap."""
    if regimes_df.empty:
        return
    
    fig, ax = plt.subplots(figsize=(16, 8))
    
    regime_matrix = regimes_df.T.values
    dates = regimes_df.index
    assets = regimes_df.columns.tolist()
    
    # Downsample
    step = max(1, len(dates) // 300)
    sampled_idx = np.arange(0, len(dates), step)
    sampled_regimes = regime_matrix[:, sampled_idx]
    sampled_dates = dates[sampled_idx]
    
    cmap = LinearSegmentedColormap.from_list('regime', [COLORS['bear'], '#fbbf24', COLORS['bull']])
    im = ax.imshow(sampled_regimes, aspect='auto', cmap=cmap, interpolation='nearest', vmin=0, vmax=1)
    
    ax.set_yticks(range(len(assets)))
    ax.set_yticklabels(assets)
    ax.set_title('Asset Regime Timeline (Green=Bull, Red=Bear)', fontsize=14, fontweight='bold')
    
    n_ticks = min(15, len(sampled_dates))
    tick_positions = np.linspace(0, len(sampled_dates)-1, n_ticks, dtype=int)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([sampled_dates[i].strftime('%Y-%m') for i in tick_positions],
                       rotation=45, ha='right')
    
    cbar = plt.colorbar(im, ax=ax, orientation='vertical', pad=0.02, aspect=30, shrink=0.8)
    cbar.set_label('Regime')
    cbar.set_ticks([0, 0.5, 1])
    cbar.set_ticklabels(['Bear', 'Trans', 'Bull'])
    
    for i in range(len(assets)-1):
        ax.axhline(i + 0.5, color='white', linewidth=0.5, alpha=0.5)
    
    plt.tight_layout()
    plt.savefig(output_path / 'regime_timeline.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✓ regime_timeline.png")


def _plot_wealth_with_regimes(returns_df, regimes_df, output_path):
    """Plot cumulative wealth with regime overlay."""
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # Select top assets by return
    total_returns = {}
    for col in returns_df.columns:
        ret = returns_df[col].dropna()
        if len(ret) > 0:
            total_returns[col] = (1 + ret).prod() - 1
    
    if not total_returns:
        plt.close()
        return
    
    top_assets = sorted(total_returns.keys(), key=lambda x: total_returns[x], reverse=True)[:5]
    colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
    
    for i, asset in enumerate(top_assets):
        ret = returns_df[asset].dropna()
        if len(ret) == 0:
            continue
        
        cum = (1 + ret).cumprod()
        ax.plot(cum.index, cum.values, color=colors[i], linewidth=2, label=asset, alpha=0.9)
    
    # Shade bear regimes for first asset
    if len(top_assets) > 0 and top_assets[0] in regimes_df.columns:
        first_asset = top_assets[0]
        first_cum = (1 + returns_df[first_asset].dropna()).cumprod()
        regimes = regimes_df[first_asset].reindex(first_cum.index)
        bear_mask = regimes == 1
        
        if bear_mask.any():
            ax.fill_between(first_cum.index, 0, first_cum.max() * 1.1,
                           where=bear_mask, alpha=0.1, color=COLORS['bear'],
                           label='Bear Regime', step='mid')
    
    ax.set_title('Cumulative Wealth with Bear Regime Shading', fontsize=14, fontweight='bold')
    ax.set_ylabel('Cumulative Return (Initial = 1)')
    ax.legend(loc='upper left', ncol=3)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    
    plt.tight_layout()
    plt.savefig(output_path / 'wealth_with_regimes.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("  ✓ wealth_with_regimes.png")


if __name__ == '__main__':
    visualize_regime_drivers(
        start_date='2005-01-01',
        end_date='2024-12-31',
        output_dir='output/figures/regime_analysis',
        show_plot=False
    )
