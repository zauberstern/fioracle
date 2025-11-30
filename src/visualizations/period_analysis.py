"""
Period-Specific Analysis Visualization

Creates before/after analysis for specific time periods:
1. 2018-2022: Supply shock analysis (2018-2020 vs 2020-2022)
2. 2006-2010: Financial crisis analysis (2006-2008 vs 2008-2010)

Each period includes:
- Combined allocation pie charts (side-by-side)
- Combined allocation timelines (stacked)
- Cumulative returns with multiple benchmarks
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import warnings
import yaml

warnings.filterwarnings('ignore')

# Professional color palette
COLORS = {
    'primary': '#1a365d',
    'secondary': '#2c5282',
    'accent': '#ed8936',
    'success': '#38a169',
    'danger': '#e53e3e',
    'warning': '#d69e2e',
    'neutral': '#718096',
    'correlation_pos': '#48BB78',
    'correlation_neg': '#F56565',
    'correlation_neutral': '#A0AEC0',
    'benchmark_60_40': '#805AD5',
    'benchmark_barbell': '#D69E2E',
    'benchmark_conservative': '#319795',
}

# Fixed color map for assets (ensures consistency across plots)
ASSET_COLOR_MAP = {}


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent.parent.parent / 'config' / 'config.yaml'
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}


def _format_date_axis(ax, dates):
    """Smart date axis formatting."""
    if len(dates) == 0:
        return
    
    date_range = (dates[-1] - dates[0]).days
    
    if date_range > 365 * 2:
        ax.xaxis.set_major_locator(mdates.YearLocator(1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    elif date_range > 365:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')


def _get_display_name(asset_name: str, config: dict) -> str:
    """Get human-readable display name from config."""
    # Check assets display_names
    asset_names = config.get('assets', {}).get('display_names', {})
    
    # Try exact match (uppercase)
    asset_upper = asset_name.upper()
    if asset_upper in asset_names:
        return asset_names[asset_upper]
    
    # Try with common suffixes added
    for suffix in ['', '_TOTAL_RETURN', '_RETURN']:
        test_name = asset_upper + suffix
        if test_name in asset_names:
            return asset_names[test_name]
    
    # Comprehensive fallback mapping
    fallbacks = {
        'US_CASH_RETURN': 'US T-Bills',
        'US_CASH': 'US T-Bills',
        'US_10Y_GOV_BOND_RETURN': 'US 10Y Treasury',
        'US_10Y_GOV_BOND': 'US 10Y Treasury',
        'IBOXX_USD_TREASURY_TOTAL_RETURN': 'USD Treasury Index',
        'IBOXX_USD_TREASURY': 'USD Treasury Index',
        'US_BOND_AGG_TOTAL_RETURN': 'US Aggregate Bond',
        'US_BOND_AGG': 'US Aggregate Bond',
        'GOLD_TOTAL_RETURN': 'Gold',
        'GOLD': 'Gold',
        'CHF_TOTAL_RETURN': 'Swiss Franc',
        'CHF': 'Swiss Franc',
        'US_TIPS_0_5_TOTAL_RETURN': 'US TIPS 0-5Y',
        'US_TIPS_0_5': 'US TIPS 0-5Y',
        'WTI_TOTAL_RETURN': 'WTI Crude Oil',
        'WTI': 'WTI Crude Oil',
        'CDX_HY_5Y_TOTAL_RETURN': 'CDX High Yield 5Y',
        'CDX_HY_5Y': 'CDX High Yield 5Y',
        'IBOXX_USD_CORPORATE_TOTAL_RETURN': 'USD Corporate IG',
        'IBOXX_USD_CORPORATE': 'USD Corporate IG',
        'US_AAA_CORP_BOND_TOTAL_RETURN': 'US AAA Corporate',
        'US_BAA_CORP_BOND_TOTAL_RETURN': 'US BBB Corporate',
    }
    
    if asset_upper in fallbacks:
        return fallbacks[asset_upper]
    
    # Clean up name as last resort
    clean = asset_name
    for suffix in ['_TOTAL_RETURN', '_RETURN', '_TR']:
        clean = clean.replace(suffix, '').replace(suffix.lower(), '')
    clean = clean.replace('_', ' ').strip().title()
    return clean[:20] if len(clean) > 20 else clean


def _get_consistent_colors(asset_names: List[str]) -> Dict[str, str]:
    """Get consistent colors for assets across all plots."""
    global ASSET_COLOR_MAP
    
    # Predefined color palette (enough for 20+ assets)
    color_palette = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
        '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5',
    ]
    
    result = {}
    color_idx = len(ASSET_COLOR_MAP)
    
    for name in asset_names:
        name_upper = name.upper()
        if name_upper not in ASSET_COLOR_MAP:
            ASSET_COLOR_MAP[name_upper] = color_palette[color_idx % len(color_palette)]
            color_idx += 1
        result[name] = ASSET_COLOR_MAP[name_upper]
    
    # Special colors for common entries
    special_colors = {
        'UNINVESTED CASH': '#A0AEC0',
        'OTHER ASSETS': '#718096',
    }
    for name in asset_names:
        if name.upper() in special_colors:
            result[name] = special_colors[name.upper()]
    
    return result


def compute_stock_bond_correlation(
    portfolio_returns: pd.Series,
    stock_returns: Optional[pd.Series] = None,
    bond_returns: Optional[pd.Series] = None,
    window: int = 63
) -> pd.Series:
    """Compute rolling stock-bond correlation."""
    window = max(window, 10)
    
    if len(portfolio_returns) < window:
        return pd.Series(0.0, index=portfolio_returns.index)
    
    if stock_returns is None or bond_returns is None or len(stock_returns) < window or len(bond_returns) < window:
        rolling_vol = portfolio_returns.rolling(window=window, min_periods=max(window//2, 5)).std()
        rolling_mean = portfolio_returns.rolling(window=window, min_periods=max(window//2, 5)).mean()
        correlation = (rolling_mean / (rolling_vol + 1e-8)).clip(-1, 1)
        return correlation.fillna(0.0)
    
    common_idx = portfolio_returns.index.intersection(stock_returns.index).intersection(bond_returns.index)
    
    if len(common_idx) < window:
        return pd.Series(0.0, index=portfolio_returns.index)
    
    stock_aligned = stock_returns.loc[common_idx]
    bond_aligned = bond_returns.loc[common_idx]
    
    correlation = stock_aligned.rolling(window=window, min_periods=max(window//2, 5)).corr(bond_aligned)
    
    return correlation.reindex(portfolio_returns.index).fillna(0.0)


def plot_cumulative_with_benchmarks(
    portfolio_returns: pd.Series,
    benchmarks: Dict[str, pd.Series],
    stock_bond_corr: pd.Series,
    strategy_name: str,
    period_label: str,
    save_path: Path
) -> None:
    """Plot cumulative returns with multiple benchmarks and stock-bond correlation."""
    fig = plt.figure(figsize=(14, 10), facecolor='#FAFBFC')
    gs = GridSpec(3, 1, height_ratios=[2, 1, 1], hspace=0.15)
    
    # Panel 1: Cumulative Returns
    ax1 = fig.add_subplot(gs[0])
    ax1.set_facecolor('#FAFBFC')
    
    cumulative = (1 + portfolio_returns).cumprod()
    ax1.plot(cumulative.index, cumulative.values, color=COLORS['primary'],
            linewidth=2.5, label=strategy_name)
    
    # Plot benchmarks
    bench_colors = ['#718096', '#805AD5', '#D69E2E', '#319795']
    bench_styles = ['--', '-.', ':', (0, (3, 1, 1, 1))]
    
    for i, (name, bench_ret) in enumerate(benchmarks.items()):
        if bench_ret is None:
            continue
        common_idx = portfolio_returns.index.intersection(bench_ret.index)
        if len(common_idx) > 0:
            bench_aligned = bench_ret.loc[common_idx]
            bench_cum = (1 + bench_aligned).cumprod()
            ax1.plot(bench_cum.index, bench_cum.values, 
                    color=bench_colors[i % len(bench_colors)],
                    linewidth=1.8, linestyle=bench_styles[i % len(bench_styles)], 
                    label=name, alpha=0.8)
    
    final_val = cumulative.iloc[-1]
    ax1.annotate(f'{final_val:.2f}x', xy=(cumulative.index[-1], final_val),
                xytext=(10, 0), textcoords='offset points',
                fontsize=11, fontweight='bold', color=COLORS['primary'])
    
    ax1.set_title(f'Cumulative Returns: {period_label}', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Portfolio Value')
    ax1.legend(loc='upper left', fontsize=9, ncol=2)
    ax1.grid(True, alpha=0.3)
    plt.setp(ax1.get_xticklabels(), visible=False)
    
    # Panel 2: Rolling Sharpe
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax2.set_facecolor('#FAFBFC')
    
    window = min(126, len(portfolio_returns) // 3)
    if window > 20:
        rolling_mean = portfolio_returns.rolling(window=window, min_periods=window//2).mean()
        rolling_std = portfolio_returns.rolling(window=window, min_periods=window//2).std()
        rolling_sharpe = ((rolling_mean / rolling_std) * np.sqrt(252)).clip(-3, 3)
        
        ax2.plot(rolling_sharpe.index, rolling_sharpe.values, color=COLORS['primary'],
                linewidth=1.5, label='Strategy')
    
    ax2.axhline(1.0, color=COLORS['success'], linestyle=':', alpha=0.7, label='Good (1.0)')
    ax2.axhline(0, color=COLORS['neutral'], linestyle='-', alpha=0.3)
    
    ax2.set_ylabel(f'Rolling Sharpe ({window}d)')
    ax2.set_ylim(-3, 3)
    ax2.legend(loc='upper left', fontsize=8, ncol=3)
    ax2.grid(True, alpha=0.3)
    plt.setp(ax2.get_xticklabels(), visible=False)
    
    # Panel 3: Stock-Bond Correlation
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax3.set_facecolor('#FAFBFC')
    
    corr_aligned = stock_bond_corr.reindex(portfolio_returns.index)
    
    ax3.fill_between(corr_aligned.index, 0, corr_aligned.values,
                    where=corr_aligned >= 0, color=COLORS['correlation_pos'], alpha=0.5,
                    label='Positive Correlation')
    ax3.fill_between(corr_aligned.index, 0, corr_aligned.values,
                    where=corr_aligned < 0, color=COLORS['correlation_neg'], alpha=0.5,
                    label='Negative Correlation')
    
    ax3.plot(corr_aligned.index, corr_aligned.values, color='black', linewidth=1, alpha=0.7)
    ax3.axhline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    
    ax3.set_ylabel('Stock-Bond Corr')
    ax3.set_xlabel('Date')
    ax3.set_ylim(-1, 1)
    ax3.legend(loc='upper left', fontsize=8)
    ax3.grid(True, alpha=0.3)
    
    _format_date_axis(ax3, portfolio_returns.index)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='#FAFBFC')
    plt.close()


def plot_combined_allocation_pies(
    weights_before: pd.DataFrame,
    weights_after: pd.DataFrame,
    label_before: str,
    label_after: str,
    save_path: Path,
    config: dict
) -> None:
    """Plot two allocation pies side-by-side with consistent colors."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 8), facecolor='#FAFBFC')
    
    def process_weights(weights_df):
        excluded_patterns = ['RF_WEIGHT', 'RISK_FREE', 'ANCILLARY', 'SP500', 'YIELD']
        asset_cols = [c for c in weights_df.columns
                      if not any(pat in c.upper() for pat in excluded_patterns)]
        
        if len(asset_cols) == 0:
            return pd.Series(), 0
        
        avg_weights = weights_df[asset_cols].mean()
        avg_rf = weights_df['cash_allocation'].mean() if 'cash_allocation' in weights_df.columns else 0
        
        threshold = 0.02
        large = avg_weights[avg_weights >= threshold].copy()
        small_sum = avg_weights[avg_weights < threshold].sum()
        
        if small_sum > 0:
            large['Other Assets'] = small_sum
        if avg_rf > threshold:
            large['Uninvested Cash'] = avg_rf
        
        return large, avg_rf
    
    large_before, rf_before = process_weights(weights_before)
    large_after, rf_after = process_weights(weights_after)
    
    # Get all unique asset names for consistent coloring
    all_assets = list(set(large_before.index.tolist() + large_after.index.tolist()))
    colors = _get_consistent_colors(all_assets)
    
    def plot_pie(ax, data, title):
        if len(data) == 0:
            ax.text(0.5, 0.5, 'No allocation data', ha='center', va='center')
            ax.set_title(title, fontsize=13, fontweight='bold')
            return
        
        display_labels = [_get_display_name(n, config) if n not in ['Other Assets', 'Uninvested Cash'] else n
                        for n in data.index]
        pie_colors = [colors.get(n, '#718096') for n in data.index]
        
        wedges, texts, autotexts = ax.pie(
            data.values, labels=None, autopct='%1.1f%%',
            colors=pie_colors, startangle=90, pctdistance=0.75,
            wedgeprops=dict(width=0.5, edgecolor='white')
        )
        
        for autotext in autotexts:
            autotext.set_fontsize(9)
            autotext.set_fontweight('bold')
        
        ax.set_title(title, fontsize=13, fontweight='bold')
        return wedges, display_labels
    
    result_before = plot_pie(axes[0], large_before, f'Average Allocation: {label_before}')
    result_after = plot_pie(axes[1], large_after, f'Average Allocation: {label_after}')
    
    # Combined legend
    if result_before and result_after:
        wedges_before, labels_before = result_before
        all_handles = []
        all_labels = []
        seen = set()
        
        for w, l in zip(wedges_before, labels_before):
            if l not in seen:
                all_handles.append(w)
                all_labels.append(l)
                seen.add(l)
        
        wedges_after, labels_after = result_after
        for w, l in zip(wedges_after, labels_after):
            if l not in seen:
                all_handles.append(w)
                all_labels.append(l)
                seen.add(l)
        
        fig.legend(all_handles, all_labels, loc='center right', bbox_to_anchor=(1.15, 0.5), fontsize=10)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='#FAFBFC')
    plt.close()


def plot_combined_allocation_timelines(
    weights_before: pd.DataFrame,
    weights_after: pd.DataFrame,
    label_before: str,
    label_after: str,
    save_path: Path,
    config: dict
) -> None:
    """Plot two allocation timelines stacked vertically with consistent colors."""
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), facecolor='#FAFBFC')
    
    def process_weights(weights_df):
        excluded_patterns = ['cash_allocation', 'date', 'risk_free', 'sp500', 'yield', 'ancillary']
        asset_cols = [c for c in weights_df.columns
                     if not any(p in c.lower() for p in excluded_patterns)]
        
        if len(asset_cols) == 0:
            return pd.DataFrame()
        
        weights_weekly = weights_df[asset_cols].resample('W').mean()
        
        total_risky = weights_weekly.sum(axis=1)
        cash_allocation = (1 - total_risky).clip(lower=0)
        if cash_allocation.mean() > 0.01:
            weights_weekly['Uninvested Cash'] = cash_allocation
        
        weights_weekly = weights_weekly.loc[:, (weights_weekly > 0.001).any()]
        return weights_weekly
    
    weights_before_proc = process_weights(weights_before)
    weights_after_proc = process_weights(weights_after)
    
    # Get all unique asset names for consistent coloring
    all_assets = list(set(weights_before_proc.columns.tolist() + weights_after_proc.columns.tolist()))
    colors = _get_consistent_colors(all_assets)
    
    def plot_timeline(ax, weights_weekly, title):
        if len(weights_weekly) == 0:
            ax.text(0.5, 0.5, 'No allocation data', ha='center', va='center')
            ax.set_title(title, fontsize=13, fontweight='bold')
            return None
        
        display_labels = [_get_display_name(c, config) if c != 'Uninvested Cash' else c
                         for c in weights_weekly.columns]
        timeline_colors = [colors.get(c, '#718096') for c in weights_weekly.columns]
        
        ax.stackplot(weights_weekly.index, weights_weekly.values.T,
                    labels=display_labels, colors=timeline_colors, alpha=0.8)
        
        ax.set_title(title, fontsize=13, fontweight='bold')
        ax.set_ylabel('Weight')
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3)
        
        _format_date_axis(ax, weights_weekly.index)
        
        return display_labels
    
    labels_before = plot_timeline(axes[0], weights_before_proc, f'Asset Allocation: {label_before}')
    labels_after = plot_timeline(axes[1], weights_after_proc, f'Asset Allocation: {label_after}')
    
    # Combined legend
    handles, labels = axes[0].get_legend_handles_labels()
    handles2, labels2 = axes[1].get_legend_handles_labels()
    
    seen = set()
    unique_handles = []
    unique_labels = []
    for h, l in zip(handles + handles2, labels + labels2):
        if l not in seen:
            unique_handles.append(h)
            unique_labels.append(l)
            seen.add(l)
    
    fig.legend(unique_handles, unique_labels, loc='center right', bbox_to_anchor=(1.15, 0.5), fontsize=9)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='#FAFBFC')
    plt.close()


def plot_combined_allocation_sharpe_corr(
    weights_before: pd.DataFrame,
    weights_after: pd.DataFrame,
    returns_before: pd.Series,
    returns_after: pd.Series,
    corr_before: Optional[pd.Series],
    corr_after: Optional[pd.Series],
    label_before: str,
    label_after: str,
    strategy_name: str,
    save_path: Path,
    config: dict
) -> None:
    """Plot combined allocation timelines with Sharpe and correlation for two periods side-by-side."""
    fig, axes = plt.subplots(1, 2, figsize=(18, 7), facecolor='#FAFBFC')
    
    def process_weights(weights_df):
        excluded_patterns = ['cash_allocation', 'date', 'risk_free', 'sp500', 'yield', 'ancillary']
        asset_cols = [c for c in weights_df.columns
                     if not any(p in c.lower() for p in excluded_patterns)]
        
        if len(asset_cols) == 0:
            return pd.DataFrame()
        
        weights_weekly = weights_df[asset_cols].resample('W').mean()
        
        total_risky = weights_weekly.sum(axis=1)
        cash = (1 - total_risky).clip(lower=0)
        if cash.mean() > 0.01:
            weights_weekly['Uninvested Cash'] = cash
        
        weights_weekly = weights_weekly.loc[:, (weights_weekly > 0.001).any()]
        return weights_weekly
    
    weights_before_proc = process_weights(weights_before)
    weights_after_proc = process_weights(weights_after)
    
    # Get all unique asset names for consistent coloring
    all_assets = list(set(weights_before_proc.columns.tolist() + weights_after_proc.columns.tolist()))
    colors = _get_consistent_colors(all_assets)
    
    def plot_period(ax, weights_weekly, returns, corr, period_label):
        if len(weights_weekly) == 0:
            ax.text(0.5, 0.5, 'No allocation data', ha='center', va='center')
            ax.set_title(period_label, fontsize=13, fontweight='bold')
            return []
        
        display_labels = [_get_display_name(c, config) if c != 'Uninvested Cash' else c
                         for c in weights_weekly.columns]
        timeline_colors = [colors.get(c, '#718096') for c in weights_weekly.columns]
        
        ax.stackplot(weights_weekly.index, weights_weekly.values.T,
                    labels=display_labels, colors=timeline_colors, alpha=0.8)
        
        ax.set_ylabel('Weight')
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3)
        _format_date_axis(ax, weights_weekly.index)
        
        # Add correlation on secondary axis if available
        if corr is not None and len(corr) > 0:
            ax2 = ax.twinx()
            ax2.plot(corr.index, corr.values, color=COLORS['neutral'], 
                    linewidth=1.5, alpha=0.6, linestyle='-', label='S/B Corr')
            ax2.axhline(y=0, color='gray', linestyle=':', alpha=0.5)
            ax2.set_ylabel('Stock/Bond Corr', fontsize=9, alpha=0.7)
            ax2.set_ylim(-1, 1)
            ax2.tick_params(axis='y', labelsize=8)
        
        # Calculate metrics for title
        total_ret = (1 + returns).prod() - 1
        ann_vol = returns.std() * np.sqrt(252)
        sharpe = (total_ret / len(returns) * 252) / ann_vol if ann_vol > 0 else 0
        
        ax.set_title(f'{period_label}\nReturn: {total_ret*100:.1f}%, Sharpe: {sharpe:.2f}',
                    fontsize=12, fontweight='bold')
        
        return display_labels
    
    labels1 = plot_period(axes[0], weights_before_proc, returns_before, corr_before, label_before)
    labels2 = plot_period(axes[1], weights_after_proc, returns_after, corr_after, label_after)
    
    # Combined legend from both subplots
    handles, labels = axes[0].get_legend_handles_labels()
    handles2, labels2 = axes[1].get_legend_handles_labels()
    
    seen = set()
    unique_handles = []
    unique_labels = []
    for h, l in zip(handles + handles2, labels + labels2):
        if l not in seen:
            unique_handles.append(h)
            unique_labels.append(l)
            seen.add(l)
    
    fig.legend(unique_handles, unique_labels, loc='center right', 
               bbox_to_anchor=(1.12, 0.5), fontsize=9)
    
    fig.suptitle(f'{strategy_name}: Allocation Timeline Comparison', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='#FAFBFC')
    plt.close()


def generate_period_analysis(
    portfolio_returns: pd.Series,
    portfolio_weights: pd.DataFrame,
    benchmarks: Dict[str, pd.Series],
    strategy_name: str,
    periods: Dict[str, Tuple[str, str]],
    output_dir: Path,
    stock_returns: Optional[pd.Series] = None,
    bond_returns: Optional[pd.Series] = None,
    analysis_name: str = 'period_analysis'
) -> Dict:
    """Generate comprehensive period analysis with combined plots."""
    config = load_config()
    analysis_dir = output_dir / analysis_name
    analysis_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    period_data = {}
    
    # First pass: collect data for each period
    for period_name, (start_date, end_date) in periods.items():
        print(f"  Processing data for {period_name}...")
        
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        
        period_returns = portfolio_returns[(portfolio_returns.index >= start_ts) & 
                                           (portfolio_returns.index <= end_ts)]
        
        if len(period_returns) < 20:
            print(f"    Insufficient data for {period_name}")
            continue
        
        period_weights = portfolio_weights[(portfolio_weights.index >= start_ts) & 
                                           (portfolio_weights.index <= end_ts)]
        
        period_benchmarks = {}
        for bench_name, bench_ret in benchmarks.items():
            if bench_ret is not None:
                period_bench = bench_ret[(bench_ret.index >= start_ts) & 
                                          (bench_ret.index <= end_ts)]
                if len(period_bench) > 0:
                    period_benchmarks[bench_name] = period_bench
        
        period_stock = None
        period_bond = None
        if stock_returns is not None:
            period_stock = stock_returns[(stock_returns.index >= start_ts) & 
                                         (stock_returns.index <= end_ts)]
        if bond_returns is not None:
            period_bond = bond_returns[(bond_returns.index >= start_ts) & 
                                       (bond_returns.index <= end_ts)]
        
        stock_bond_corr = compute_stock_bond_correlation(
            period_returns, period_stock, period_bond,
            window=min(63, max(10, len(period_returns) // 3))
        )
        
        period_data[period_name] = {
            'returns': period_returns,
            'weights': period_weights,
            'benchmarks': period_benchmarks,
            'correlation': stock_bond_corr,
            'start_ts': start_ts,
            'end_ts': end_ts
        }
        
        # Compute metrics
        total_return = (1 + period_returns).prod() - 1
        ann_return = (1 + total_return) ** (252 / len(period_returns)) - 1
        ann_vol = period_returns.std() * np.sqrt(252)
        sharpe = ann_return / ann_vol if ann_vol > 0 else 0.0
        
        cumulative = (1 + period_returns).cumprod()
        max_dd = ((cumulative - cumulative.cummax()) / cumulative.cummax()).min()
        
        results[period_name] = {
            'total_return': total_return,
            'ann_return': ann_return,
            'ann_vol': ann_vol,
            'sharpe': sharpe,
            'max_drawdown': max_dd,
            'n_days': len(period_returns)
        }
        
        print(f"    ✓ {period_name}: Return={total_return*100:.1f}%, Sharpe={sharpe:.2f}")
    
    # Generate individual cumulative returns plots
    for period_name, data in period_data.items():
        period_dir = analysis_dir / period_name.replace(' ', '_').replace('/', '_')
        period_dir.mkdir(parents=True, exist_ok=True)
        
        plot_cumulative_with_benchmarks(
            data['returns'], data['benchmarks'], data['correlation'],
            strategy_name, period_name,
            period_dir / 'cumulative_returns_sharpe_corr.png'
        )
    
    # Generate combined plots if we have exactly 2 periods
    period_names = list(period_data.keys())
    if len(period_names) == 2:
        print("  Generating combined comparison plots...")
        
        # Combined allocation pies
        plot_combined_allocation_pies(
            period_data[period_names[0]]['weights'],
            period_data[period_names[1]]['weights'],
            period_names[0], period_names[1],
            analysis_dir / 'combined_allocation_pies.png', config
        )
        
        # Combined allocation timelines
        plot_combined_allocation_timelines(
            period_data[period_names[0]]['weights'],
            period_data[period_names[1]]['weights'],
            period_names[0], period_names[1],
            analysis_dir / 'combined_allocation_timelines.png', config
        )
        
        # Combined allocation timeline with Sharpe and correlation
        plot_combined_allocation_sharpe_corr(
            period_data[period_names[0]]['weights'],
            period_data[period_names[1]]['weights'],
            period_data[period_names[0]]['returns'],
            period_data[period_names[1]]['returns'],
            period_data[period_names[0]]['correlation'],
            period_data[period_names[1]]['correlation'],
            period_names[0], period_names[1],
            strategy_name,
            analysis_dir / 'combined_allocation_sharpe_corr.png',
            config
        )
        
        print(f"    ✓ Combined plots saved to {analysis_dir}")
    
    return results


def generate_supply_shock_analysis(
    portfolio_returns: pd.Series,
    portfolio_weights: pd.DataFrame,
    benchmarks: Dict[str, pd.Series],
    strategy_name: str,
    output_dir: Path,
    stock_returns: Optional[pd.Series] = None,
    bond_returns: Optional[pd.Series] = None
) -> Dict:
    """Generate 2018-2022 supply shock analysis."""
    periods = {
        '2018-2020 (Pre-COVID)': ('2018-01-01', '2019-12-31'),
        '2020-2022 (Supply Shock)': ('2020-01-01', '2022-12-31'),
    }
    
    return generate_period_analysis(
        portfolio_returns, portfolio_weights,
        benchmarks, strategy_name,
        periods, output_dir,
        stock_returns, bond_returns,
        analysis_name='supply_shock_analysis'
    )


def generate_financial_crisis_analysis(
    portfolio_returns: pd.Series,
    portfolio_weights: pd.DataFrame,
    benchmarks: Dict[str, pd.Series],
    strategy_name: str,
    output_dir: Path,
    stock_returns: Optional[pd.Series] = None,
    bond_returns: Optional[pd.Series] = None
) -> Dict:
    """Generate 2006-2010 financial crisis analysis."""
    periods = {
        '2006-2008 (Pre-Crisis)': ('2006-01-01', '2007-12-31'),
        '2008-2010 (GFC + Recovery)': ('2008-01-01', '2010-12-31'),
    }
    
    return generate_period_analysis(
        portfolio_returns, portfolio_weights,
        benchmarks, strategy_name,
        periods, output_dir,
        stock_returns, bond_returns,
        analysis_name='financial_crisis_analysis'
    )


if __name__ == '__main__':
    print("Period analysis module loaded.")
