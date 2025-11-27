#!/usr/bin/env python3
"""
Regime Drivers Visualization

Creates a comprehensive plot showing how geopolitical and macroeconomic features
drive asset regime predictions across time.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Rectangle
import warnings

warnings.filterwarnings('ignore')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import DataPipeline, engineer_features, RegimeEngine


# Helper functions
def _get_continuous_periods(mask):
    """Get start/end dates of continuous True periods in boolean mask."""
    periods = []
    in_period = False
    start = None
    
    for i, val in enumerate(mask):
        if val and not in_period:
            start = mask.index[i]
            in_period = True
        elif not val and in_period:
            end = mask.index[i-1]
            periods.append((start, end))
            in_period = False
    
    if in_period:
        periods.append((start, mask.index[-1]))
    
    return periods


def _annotate_events(ax, dates, values):
    """Annotate key historical events."""
    events = {
        '2001-09-11': '9/11',
        '2003-03-20': 'Iraq War',
        '2008-09-15': 'Lehman',
    }
    
    for date_str, label in events.items():
        date = pd.Timestamp(date_str)
        if date in dates:
            idx = dates.get_loc(date)
            if isinstance(idx, slice):
                idx = idx.start
            elif hasattr(idx, '__iter__'):
                idx = list(idx)[0]
            
            y_val = values.iloc[idx] if isinstance(values, pd.Series) else values[idx]
            ax.annotate(label, xy=(date, y_val), 
                       xytext=(0, 15), textcoords='offset points',
                       ha='center', fontsize=7, fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.5),
                       arrowprops=dict(arrowstyle='->', lw=1, color='black'))


def visualize_regime_drivers(start_date='2001-01-01', end_date='2010-12-31', 
                             output_path='output/figures/regime_drivers_visualization.png',
                             show_plot=True):
    """
    Create comprehensive regime drivers visualization.
    
    Parameters
    ----------
    start_date : str
        Start date for analysis
    end_date : str
        End date for analysis
    output_path : str
        Path to save the figure
    show_plot : bool
        Whether to display the plot
        
    Returns
    -------
    fig : matplotlib.figure.Figure
        The generated figure
    """
    
    print("="*80)
    print("REGIME DRIVERS VISUALIZATION")
    print("="*80)
    print(f"Period: {start_date} to {end_date}")
    print("Generating comprehensive regime drivers plot...")
    print()
    
    # Load data
    print("Loading data...")
    pipeline = DataPipeline()
    data = pipeline.load(start_date, end_date)
    
    # Engineer features
    print("Engineering features...")
    asset_features, macro_features = engineer_features(data)
    
    # Build returns from raw data (excess returns vs risk-free)
    risk_free_col = [c for c in data.columns if 'risk_free' in c]
    rf_returns = data[risk_free_col[0]].pct_change() if risk_free_col else 0
    
    asset_returns = {}
    non_return_cols = {'asset_us_treasury_2y_yield', 'asset_us_10y2y_slope'}
    for col in data.columns:
        if col.startswith('asset_') and col not in non_return_cols:
            if risk_free_col and col == risk_free_col[0]:
                continue
            asset_return = data[col].pct_change()
            if isinstance(rf_returns, pd.Series):
                excess_return = asset_return - rf_returns
            else:
                excess_return = asset_return
            asset_name = col.replace('asset_', '').upper()
            if asset_name in asset_features:
                asset_returns[asset_name] = excess_return
    
    returns_df = pd.DataFrame(asset_returns)
    
    # Identify regimes
    print("Identifying regimes...")
    engine = RegimeEngine(lambda_jump=5.0, n_macro_regimes=3)
    results = engine.fit_identify_forecast(
        asset_features, returns_df, macro_features, verbose=False
    )
    
    regimes_df = pd.DataFrame(results['asset_regimes'])
    macro_probs = results['macro_probs']
    
    # Extract key macro indicators from raw data
    gpr_col = [c for c in data.columns if 'gpr' in c.lower()]
    epu_col = [c for c in data.columns if 'epu' in c.lower()]
    
    gpr = data[gpr_col[0]] if gpr_col else None
    epu = data[epu_col[0]] if epu_col else None
    
    # Get VIX (prioritize actual VIX, fall back to proxy)
    vix = None
    if 'vix_level' in macro_features.columns:
        vix = macro_features['vix_level']
    elif 'vix_ewm_63d' in macro_features.columns:
        vix = macro_features['vix_ewm_63d']
    
    print("Creating visualization...")
    
    # Create figure with custom layout
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(4, 3, height_ratios=[1, 1, 0.8, 1.2], hspace=0.4, wspace=0.3,
                         top=0.93, bottom=0.08)
    
    # Color scheme
    BULL_COLOR = '#2ecc71'  # Green
    BEAR_COLOR = '#e74c3c'  # Red
    MACRO_COLORS = ['#3498db', '#9b59b6', '#f39c12']  # Blue, Purple, Orange
    
    # ============================================================================
    # TOP ROW: GEOPOLITICAL & POLICY INDICATORS
    # ============================================================================
    
    # Plot 1: Geopolitical Risk Index
    ax1 = fig.add_subplot(gs[0, 0])
    if gpr is not None:
        gpr_normalized = (gpr - gpr.mean()) / gpr.std()
        ax1.fill_between(gpr.index, 0, gpr_normalized, alpha=0.3, color='#e74c3c', label='GPR Level')
        ax1.plot(gpr.index, gpr_normalized, color='#c0392b', linewidth=1.5, label='GPR')
        
        # Highlight high-risk periods
        high_risk = gpr_normalized > 1.5
        if high_risk.any():
            for start, end in _get_continuous_periods(high_risk):
                ax1.axvspan(start, end, alpha=0.15, color='red')
        
        ax1.axhline(0, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        ax1.set_title('Geopolitical Risk (Normalized)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Std Deviations', fontsize=10)
        ax1.grid(alpha=0.3, linewidth=0.5)
        ax1.legend(loc='upper left', fontsize=9)
        
        # Annotate key events
        _annotate_events(ax1, gpr.index, gpr_normalized)
    
    # Plot 2: Economic Policy Uncertainty
    ax2 = fig.add_subplot(gs[0, 1])
    if epu is not None:
        epu_normalized = (epu - epu.mean()) / epu.std()
        ax2.fill_between(epu.index, 0, epu_normalized, alpha=0.3, color='#e67e22', label='EPU Level')
        ax2.plot(epu.index, epu_normalized, color='#d35400', linewidth=1.5, label='EPU')
        
        # Highlight high uncertainty
        high_uncertainty = epu_normalized > 1.5
        if high_uncertainty.any():
            for start, end in _get_continuous_periods(high_uncertainty):
                ax2.axvspan(start, end, alpha=0.15, color='orange')
        
        ax2.axhline(0, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        ax2.set_title('Economic Policy Uncertainty (Normalized)', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Std Deviations', fontsize=10)
        ax2.grid(alpha=0.3, linewidth=0.5)
        ax2.legend(loc='upper left', fontsize=9)
    
    # Plot 3: Market Volatility (VIX or proxy)
    ax3 = fig.add_subplot(gs[0, 2])
    if vix is not None:
        vix_normalized = (vix - vix.mean()) / vix.std()
        ax3.fill_between(vix.index, 0, vix_normalized, alpha=0.3, color='#8e44ad', label='Volatility')
        ax3.plot(vix.index, vix_normalized, color='#6c3483', linewidth=1.5, label='VIX')
        
        # Highlight high volatility
        high_vol = vix_normalized > 1.5
        if high_vol.any():
            for start, end in _get_continuous_periods(high_vol):
                ax3.axvspan(start, end, alpha=0.15, color='purple')
        
        ax3.axhline(0, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        ax3.set_title('Market Volatility (Normalized)', fontsize=12, fontweight='bold')
        ax3.set_ylabel('Std Deviations', fontsize=10)
        ax3.grid(alpha=0.3, linewidth=0.5)
        ax3.legend(loc='upper left', fontsize=9)
    else:
        # If no VIX data, show placeholder
        ax3.text(0.5, 0.5, 'VIX Data Not Available', 
                ha='center', va='center', fontsize=12, style='italic',
                transform=ax3.transAxes)
        ax3.set_title('Market Volatility (Normalized)', fontsize=12, fontweight='bold')
        ax3.set_xticks([])
        ax3.set_yticks([])
    
    # ============================================================================
    # MIDDLE ROW: MACRO REGIME EVOLUTION
    # ============================================================================
    
    ax4 = fig.add_subplot(gs[1, :])
    
    # Plot macro regime probabilities as stacked area
    if len(macro_probs.columns) >= 3:
        regime_cols = [col for col in macro_probs.columns if 'macro_regime' in col and 'prob' in col][:3]
        
        if regime_cols:
            regime_data = macro_probs[regime_cols].values.T
            
            ax4.stackplot(macro_probs.index, regime_data, 
                         colors=MACRO_COLORS, alpha=0.7,
                         labels=['Risk-Off Environment', 'Transitional', 'Risk-On Environment'])
            
            ax4.set_title('Macro-Economic Regime Evolution (3-State HMM)', fontsize=12, fontweight='bold')
            ax4.set_ylabel('Regime Probability', fontsize=10)
            ax4.set_ylim(0, 1)
            ax4.legend(loc='upper right', fontsize=9)
            ax4.grid(alpha=0.3, linewidth=0.5)
            
            # Add labels for regime interpretation
            ax4.text(0.02, 0.95, 'Higher values = Higher probability', 
                    transform=ax4.transAxes, fontsize=8, va='top', style='italic')
    
    # ============================================================================
    # THIRD ROW: REGIME DETECTION SUMMARY
    # ============================================================================
    
    ax5 = fig.add_subplot(gs[2, :])
    
    # Show regime percentages across assets
    regime_pcts = {}
    for col in regimes_df.columns:
        bull_pct = (regimes_df[col] == 1).sum() / len(regimes_df) * 100
        regime_pcts[col] = bull_pct
    
    # Create horizontal bar chart
    assets = list(regime_pcts.keys())
    bull_pcts = [regime_pcts[a] for a in assets]
    bear_pcts = [100 - regime_pcts[a] for a in assets]
    
    y_pos = np.arange(len(assets))
    
    ax5.barh(y_pos, bull_pcts, color=BULL_COLOR, alpha=0.7, label='Bull Regime')
    ax5.barh(y_pos, bear_pcts, left=bull_pcts, color=BEAR_COLOR, alpha=0.7, label='Bear Regime')
    
    ax5.set_yticks(y_pos)
    ax5.set_yticklabels(assets, fontsize=9)
    ax5.set_xlabel('Time in Regime (%)', fontsize=10)
    ax5.set_title('Asset Regime Distribution (2001-2010)', fontsize=12, fontweight='bold')
    ax5.set_xlim(0, 100)
    ax5.legend(loc='lower right', fontsize=9)
    ax5.grid(axis='x', alpha=0.3, linewidth=0.5)
    
    # Add percentage labels
    for i, (bull, bear) in enumerate(zip(bull_pcts, bear_pcts)):
        if bull > 5:
            ax5.text(bull/2, i, f'{bull:.0f}%', ha='center', va='center', 
                    fontweight='bold', fontsize=8, color='white')
        if bear > 5:
            ax5.text(bull + bear/2, i, f'{bear:.0f}%', ha='center', va='center',
                    fontweight='bold', fontsize=8, color='white')
    
    # ============================================================================
    # BOTTOM ROW: ASSET REGIME TIMELINE
    # ============================================================================
    
    ax6 = fig.add_subplot(gs[3, :])
    
    # Create regime timeline heatmap
    regime_matrix = regimes_df.T.values
    regime_dates = regimes_df.index
    
    # Sample data for visualization (every 5 days for clarity)
    sample_idx = np.arange(0, len(regime_dates), 5)
    sampled_regimes = regime_matrix[:, sample_idx]
    sampled_dates = regime_dates[sample_idx]
    
    # Plot heatmap
    im = ax6.imshow(sampled_regimes, aspect='auto', cmap='RdYlGn', 
                   interpolation='nearest', vmin=0, vmax=1)
    
    ax6.set_yticks(range(len(assets)))
    ax6.set_yticklabels(assets, fontsize=9)
    ax6.set_xlabel('Time', fontsize=10)
    ax6.set_title('Asset Regime Timeline (Green=Bull, Red=Bear)', fontsize=12, fontweight='bold')
    
    # Format x-axis with dates
    num_ticks = 8
    tick_positions = np.linspace(0, len(sampled_dates)-1, num_ticks, dtype=int)
    ax6.set_xticks(tick_positions)
    ax6.set_xticklabels([sampled_dates[i].strftime('%Y-%m') for i in tick_positions], 
                         rotation=45, ha='right', fontsize=8)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax6, orientation='vertical', pad=0.01, aspect=30)
    cbar.set_label('Regime (0=Bear, 1=Bull)', fontsize=9)
    cbar.set_ticks([0, 0.5, 1])
    cbar.set_ticklabels(['Bear', 'Mixed', 'Bull'], fontsize=8)
    
    # Add GFC annotation
    gfc_start = pd.Timestamp('2007-12-01')
    gfc_end = pd.Timestamp('2009-06-01')
    if gfc_start in regime_dates and gfc_end in regime_dates:
        gfc_start_idx = np.where(sampled_dates >= gfc_start)[0]
        gfc_end_idx = np.where(sampled_dates <= gfc_end)[0]
        if len(gfc_start_idx) > 0 and len(gfc_end_idx) > 0:
            rect = Rectangle((gfc_start_idx[0], -0.5), 
                            gfc_end_idx[-1] - gfc_start_idx[0], len(assets),
                            linewidth=2, edgecolor='black', facecolor='none', 
                            linestyle='--', label='GFC Period')
            ax6.add_patch(rect)
            ax6.text(np.mean([gfc_start_idx[0], gfc_end_idx[-1]]), len(assets)-0.5, 
                    'GFC', ha='center', va='bottom', fontsize=10, fontweight='bold',
                    bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
    
    # ============================================================================
    # MAIN TITLE
    # ============================================================================
    
    fig.suptitle('Geopolitical & Macroeconomic Drivers → Asset Regimes',
                fontsize=16, fontweight='bold', y=0.98)
    
    # Add clean summary text at bottom
    summary_text = (
        f'Three-Layer Framework: Macro Inputs (GPR, EPU, VIX) → '
        f'Regime Detection (3-State HMM) → Asset Classification (Jump Model + XGBoost) | '
        f'Period: {start_date} to {end_date}'
    )
    
    fig.text(0.5, 0.02, summary_text, ha='center', fontsize=9, 
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.2),
            family='sans-serif')
    
    # Save figure
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved visualization: {output_file}")
    print(f"  Size: {output_file.stat().st_size / 1024:.1f} KB")
    print()
    print("="*80)
    print("VISUALIZATION COMPLETE")
    print("="*80)
    
    if show_plot:
        plt.show()
    
    return fig


if __name__ == '__main__':
    # Default configuration
    START_DATE = '2001-01-01'
    END_DATE = '2010-12-31'
    
    visualize_regime_drivers(
        start_date=START_DATE,
        end_date=END_DATE,
        output_path='output/figures/regime_drivers_visualization.png',
        show_plot=True
    )
