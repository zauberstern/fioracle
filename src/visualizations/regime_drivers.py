"""
Regime Drivers Visualization

Generates individual plots for regime analysis:
1. Macro indicators timeline
2. Regime distribution
3. Regime transitions over time
4. Asset regime timeline heatmap
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from typing import Optional, Dict
import warnings

warnings.filterwarnings('ignore')

# Color scheme
COLORS = {
    'bull': '#38a169',
    'bear': '#e53e3e',
    'neutral': '#718096',
    'vix': '#805ad5',
    'gpr': '#dd6b20',
    'debt': '#2b6cb0',
    'inflation': '#d69e2e',
    'spread': '#319795',
}


def visualize_regime_drivers(
    start_date: str,
    end_date: str,
    output_dir: str,
    show_plot: bool = False
) -> None:
    """Generate regime driver visualizations."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load macro data
    from core.data import DataPipeline
    
    try:
        pipeline = DataPipeline()
        data = pipeline.load(start_date=start_date, end_date=end_date)
        
        if data.empty:
            print("No data available for regime drivers visualization")
            return
        
        # Generate individual plots
        _plot_macro_indicators(data, output_path)
        _plot_macro_correlations(data, output_path)
        _plot_macro_regime_summary(data, output_path)
        
        print(f"Regime driver visualizations saved to {output_path}")
        
    except Exception as e:
        print(f"Regime drivers visualization failed: {e}")


def _plot_macro_indicators(data: pd.DataFrame, output_path: Path):
    """Plot macro indicators timeline with appropriate smoothing."""
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    
    # VIX
    vix_col = [c for c in data.columns if 'vix' in c.lower() and 'macro' in c.lower()]
    if vix_col:
        ax = axes[0]
        vix = data[vix_col[0]].dropna()
        ax.plot(vix.index, vix.values, color=COLORS['vix'], linewidth=1, alpha=0.7)
        # Add smoothed version
        vix_smooth = vix.ewm(span=21).mean()
        ax.plot(vix_smooth.index, vix_smooth.values, color=COLORS['vix'], linewidth=2, label='21-day EMA')
        ax.fill_between(vix_smooth.index, vix_smooth.values, alpha=0.2, color=COLORS['vix'])
        ax.axhline(25, color='red', linestyle='--', alpha=0.5, label='Elevated')
        ax.axhline(35, color='darkred', linestyle='--', alpha=0.5, label='Crisis')
        ax.set_ylabel('VIX', fontsize=11)
        ax.set_title('Market Volatility (VIX)', fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)
    
    # GPR - Apply significant smoothing to reduce noise
    gpr_col = [c for c in data.columns if 'gpr' in c.lower() and 'macro' in c.lower()]
    if gpr_col:
        ax = axes[1]
        gpr = data[gpr_col[0]].dropna()
        
        # Raw data in light color
        ax.plot(gpr.index, gpr.values, color=COLORS['gpr'], linewidth=0.5, alpha=0.3, label='Raw')
        
        # Heavy smoothing: 63-day EMA (approximately 3 months)
        gpr_smooth = gpr.ewm(span=63, min_periods=20).mean()
        ax.plot(gpr_smooth.index, gpr_smooth.values, color=COLORS['gpr'], linewidth=2, label='63-day EMA')
        ax.fill_between(gpr_smooth.index, gpr_smooth.values, alpha=0.3, color=COLORS['gpr'])
        
        # Add percentile bands
        gpr_p75 = gpr.rolling(window=252, min_periods=50).quantile(0.75)
        gpr_p25 = gpr.rolling(window=252, min_periods=50).quantile(0.25)
        ax.plot(gpr_p75.index, gpr_p75.values, color='red', linestyle=':', alpha=0.5, label='75th pct')
        ax.plot(gpr_p25.index, gpr_p25.values, color='green', linestyle=':', alpha=0.5, label='25th pct')
        
        ax.set_ylabel('GPR Index', fontsize=11)
        ax.set_title('Geopolitical Risk Index (Smoothed)', fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8, ncol=2)
        ax.grid(True, alpha=0.3)
    
    # US Debt/GDP
    debt_col = [c for c in data.columns if 'debt' in c.lower() and 'macro' in c.lower()]
    if debt_col:
        ax = axes[2]
        debt = data[debt_col[0]].dropna()
        ax.plot(debt.index, debt.values, color=COLORS['debt'], linewidth=1.5)
        ax.fill_between(debt.index, debt.values, alpha=0.3, color=COLORS['debt'])
        ax.set_ylabel('Debt/GDP', fontsize=11)
        ax.set_title('US Debt to GDP Ratio', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
    
    # Inflation
    infl_col = [c for c in data.columns if 'inflation' in c.lower() and 'macro' in c.lower()]
    if infl_col:
        ax = axes[3]
        infl = data[infl_col[0]].dropna()
        ax.plot(infl.index, infl.values, color=COLORS['inflation'], linewidth=1, alpha=0.7)
        # Smoothed version
        infl_smooth = infl.ewm(span=21).mean()
        ax.plot(infl_smooth.index, infl_smooth.values, color=COLORS['inflation'], linewidth=2, label='21-day EMA')
        ax.fill_between(infl_smooth.index, infl_smooth.values, alpha=0.3, color=COLORS['inflation'])
        ax.axhline(2, color='green', linestyle='--', alpha=0.5, label='Target (2%)')
        ax.set_ylabel('Inflation (%)', fontsize=11)
        ax.set_title('US Inflation Rate', fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)
    
    # Smart date axis
    _format_date_axis(axes[-1], data.index)
    axes[-1].set_xlabel('Date', fontsize=11)
    
    plt.tight_layout()
    plt.savefig(output_path / 'macro_indicators_timeline.png', dpi=150, bbox_inches='tight')
    plt.close()


def _plot_macro_correlations(data: pd.DataFrame, output_path: Path):
    """Plot correlation matrix of macro indicators."""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Select macro columns
    macro_cols = [c for c in data.columns if 'macro' in c.lower()]
    if len(macro_cols) < 2:
        plt.close()
        return
    
    macro_data = data[macro_cols].dropna()
    
    # Clean column names for display
    clean_names = [c.replace('macro_', '').replace('_', ' ').title()[:15] for c in macro_cols]
    
    corr = macro_data.corr()
    
    im = ax.imshow(corr.values, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Correlation', fontsize=11)
    
    # Add labels
    ax.set_xticks(range(len(clean_names)))
    ax.set_yticks(range(len(clean_names)))
    ax.set_xticklabels(clean_names, rotation=45, ha='right', fontsize=9)
    ax.set_yticklabels(clean_names, fontsize=9)
    
    # Add correlation values
    for i in range(len(corr)):
        for j in range(len(corr)):
            val = corr.iloc[i, j]
            color = 'white' if abs(val) > 0.5 else 'black'
            ax.text(j, i, f'{val:.2f}', ha='center', va='center', fontsize=8, color=color)
    
    ax.set_title('Macro Indicators Correlation Matrix', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path / 'macro_correlations.png', dpi=150, bbox_inches='tight')
    plt.close()


def _plot_macro_regime_summary(data: pd.DataFrame, output_path: Path):
    """Plot summary of macro regimes."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # VIX Distribution
    ax = axes[0, 0]
    vix_col = [c for c in data.columns if 'vix' in c.lower() and 'macro' in c.lower()]
    if vix_col:
        vix = data[vix_col[0]].dropna()
        ax.hist(vix, bins=50, color=COLORS['vix'], alpha=0.7, edgecolor='white')
        ax.axvline(vix.median(), color='black', linestyle='--', label=f'Median: {vix.median():.1f}')
        ax.axvline(25, color='red', linestyle=':', label='Elevated (25)')
        ax.set_xlabel('VIX Level')
        ax.set_ylabel('Frequency')
        ax.set_title('VIX Distribution', fontsize=12, fontweight='bold')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
    
    # GPR Distribution
    ax = axes[0, 1]
    gpr_col = [c for c in data.columns if 'gpr' in c.lower() and 'macro' in c.lower()]
    if gpr_col:
        gpr = data[gpr_col[0]].dropna()
        ax.hist(gpr, bins=50, color=COLORS['gpr'], alpha=0.7, edgecolor='white')
        ax.axvline(gpr.median(), color='black', linestyle='--', label=f'Median: {gpr.median():.1f}')
        ax.set_xlabel('GPR Index')
        ax.set_ylabel('Frequency')
        ax.set_title('Geopolitical Risk Distribution', fontsize=12, fontweight='bold')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
    
    # VIX vs GPR Scatter
    ax = axes[1, 0]
    if vix_col and gpr_col:
        common = data[[vix_col[0], gpr_col[0]]].dropna()
        ax.scatter(common[vix_col[0]], common[gpr_col[0]], alpha=0.3, s=10, c=COLORS['neutral'])
        ax.set_xlabel('VIX Level')
        ax.set_ylabel('GPR Index')
        ax.set_title('VIX vs Geopolitical Risk', fontsize=12, fontweight='bold')
        
        # Correlation annotation
        corr = common[vix_col[0]].corr(common[gpr_col[0]])
        ax.annotate(f'Correlation: {corr:.3f}', xy=(0.05, 0.95), xycoords='axes fraction',
                   fontsize=11, fontweight='bold',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        ax.grid(True, alpha=0.3)
    
    # Debt/GDP over time (smoothed)
    ax = axes[1, 1]
    debt_col = [c for c in data.columns if 'debt' in c.lower() and 'macro' in c.lower()]
    if debt_col:
        debt = data[debt_col[0]].dropna()
        debt_annual = debt.resample('YE').mean()
        ax.bar(debt_annual.index.year, debt_annual.values, color=COLORS['debt'], alpha=0.7)
        ax.set_xlabel('Year')
        ax.set_ylabel('Debt/GDP Ratio')
        ax.set_title('US Debt/GDP Over Time (Annual Average)', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path / 'macro_regime_summary.png', dpi=150, bbox_inches='tight')
    plt.close()


def _format_date_axis(ax, dates):
    """Smart date axis formatting."""
    if len(dates) == 0:
        return
    
    date_range = (dates[-1] - dates[0]).days
    
    if date_range > 365 * 10:
        ax.xaxis.set_major_locator(mdates.YearLocator(5))
    elif date_range > 365 * 5:
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
    else:
        ax.xaxis.set_major_locator(mdates.YearLocator(1))
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
