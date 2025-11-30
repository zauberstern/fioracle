"""
Advanced Analytics Visualizations

Provides comprehensive visualizations for:
1. Fat-Tail Distribution Analysis (QQ plots, tail indices)
2. Barbell vs Diversified Portfolio Comparison
3. Stock-Bond Correlation Regime Analysis
4. Volatility Regime Performance Attribution
5. Statistical Significance Testing
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import seaborn as sns
from scipy import stats
from scipy.stats import t as student_t, jarque_bera, norm
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import warnings

warnings.filterwarnings('ignore')

COLORS = {
    'calm': '#38a169',
    'inflationary': '#d69e2e',
    'crisis': '#e53e3e',
    'portfolio': '#1a365d',
    'benchmark': '#718096',
    'normal': '#805ad5',
    'student_t': '#dd6b20',
}


def generate_fat_tail_analysis(
    returns: pd.Series,
    regimes: Optional[pd.Series],
    output_dir: str,
    strategy_name: str = "Strategy"
) -> Dict:
    """
    Generate comprehensive fat-tail distribution analysis.
    
    Creates:
    1. QQ plot vs Normal distribution
    2. QQ plot vs Student-t distribution
    3. Tail index analysis (Hill estimator)
    4. Distribution comparison histogram
    """
    output_path = Path(output_dir) / 'fat_tail_analysis'
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    # Handle None regimes
    if regimes is None:
        regimes = pd.Series(0, index=returns.index, name='regime')
    
    # Align data
    common_idx = returns.index.intersection(regimes.index)
    returns_aligned = returns.loc[common_idx].dropna()
    regimes_aligned = regimes.loc[common_idx].reindex(returns_aligned.index).fillna(0)
    
    if len(returns_aligned) < 100:  # Reduced threshold
        print(f"Insufficient data for fat-tail analysis ({len(returns_aligned)} days)")
        return results
    
    # Overall statistics
    results['overall'] = _compute_tail_stats(returns_aligned, "Overall")
    
    # Per-regime statistics
    for regime in regimes_aligned.unique():
        regime_mask = regimes_aligned == regime
        if regime_mask.sum() > 50:
            regime_returns = returns_aligned[regime_mask]
            regime_name = {0: 'Calm', 1: 'Inflationary', 2: 'Crisis'}.get(regime, f'Regime {regime}')
            results[f'regime_{regime}'] = _compute_tail_stats(regime_returns, regime_name)
    
    # Generate plots
    _plot_qq_normal(returns_aligned, output_path, strategy_name)
    _plot_qq_student_t(returns_aligned, output_path, strategy_name)
    _plot_distribution_comparison(returns_aligned, regimes_aligned, output_path, strategy_name)
    _plot_distribution_histograms(returns_aligned, regimes_aligned, output_path, strategy_name)
    _plot_tail_index_analysis(returns_aligned, output_path, strategy_name)
    
    # Save results
    results_df = pd.DataFrame(results).T
    results_df.to_csv(output_path / 'fat_tail_statistics.csv')
    
    print(f"Fat-tail analysis saved to {output_path}")
    return results


def _compute_tail_stats(returns: pd.Series, name: str) -> Dict:
    """Compute tail statistics for a return series."""
    stats_dict = {
        'name': name,
        'n_observations': len(returns),
        'mean': float(returns.mean()),
        'std': float(returns.std()),
        'skewness': float(stats.skew(returns)),
        'excess_kurtosis': float(stats.kurtosis(returns)),
    }
    
    # Jarque-Bera test for normality
    jb_stat, jb_pval = jarque_bera(returns)
    stats_dict['jarque_bera_stat'] = float(jb_stat)
    stats_dict['jarque_bera_pval'] = float(jb_pval)
    stats_dict['reject_normality'] = jb_pval < 0.05
    
    # VaR and CVaR
    stats_dict['var_95'] = float(np.percentile(returns, 5))
    stats_dict['var_99'] = float(np.percentile(returns, 1))
    stats_dict['cvar_95'] = float(returns[returns <= np.percentile(returns, 5)].mean())
    
    # Hill estimator for tail index (right tail)
    sorted_abs = np.sort(np.abs(returns))[::-1]
    k = min(100, len(sorted_abs) // 10)  # Use top 10% or 100 observations
    if k > 10:
        hill_est = k / np.sum(np.log(sorted_abs[:k] / sorted_abs[k]))
        stats_dict['tail_index_hill'] = float(hill_est)
    
    # Fit Student-t distribution
    try:
        df, loc, scale = student_t.fit(returns)
        stats_dict['student_t_df'] = float(df)
        stats_dict['student_t_scale'] = float(scale)
    except:
        pass
    
    return stats_dict


def _plot_qq_normal(returns: pd.Series, output_path: Path, strategy_name: str):
    """QQ plot against normal distribution."""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Standardize returns
    z_returns = (returns - returns.mean()) / returns.std()
    
    # Generate theoretical quantiles
    (osm, osr), (slope, intercept, r) = stats.probplot(z_returns, dist='norm', plot=None)
    
    ax.scatter(osm, osr, alpha=0.5, s=10, color=COLORS['portfolio'])
    ax.plot([-4, 4], [-4, 4], 'r--', linewidth=2, label='Normal')
    
    # Highlight tail departures
    ax.fill_between([-4, -2], -10, 10, alpha=0.1, color=COLORS['crisis'], label='Left Tail')
    ax.fill_between([2, 4], -10, 10, alpha=0.1, color=COLORS['calm'], label='Right Tail')
    
    ax.set_xlim(-4, 4)
    ax.set_ylim(min(osr) - 0.5, max(osr) + 0.5)
    ax.set_xlabel('Theoretical Quantiles (Normal)', fontsize=12)
    ax.set_ylabel('Sample Quantiles', fontsize=12)
    ax.set_title(f'{strategy_name}: QQ Plot vs Normal Distribution', fontsize=14, fontweight='bold')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    
    # Add statistics
    kurtosis = stats.kurtosis(returns)
    ax.text(0.95, 0.05, f'Excess Kurtosis: {kurtosis:.2f}\n(Normal = 0)',
           transform=ax.transAxes, ha='right', va='bottom',
           bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig(output_path / 'qq_normal.png', dpi=150, bbox_inches='tight')
    plt.close()


def _plot_qq_student_t(returns: pd.Series, output_path: Path, strategy_name: str):
    """QQ plot against fitted Student-t distribution."""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Fit Student-t
    try:
        df, loc, scale = student_t.fit(returns)
    except:
        df, loc, scale = 5, returns.mean(), returns.std()
    
    # Generate theoretical quantiles from fitted t
    standardized = (returns - loc) / scale
    theoretical = student_t.ppf(np.linspace(0.001, 0.999, len(returns)), df)
    sample = np.sort(standardized)
    
    ax.scatter(theoretical, sample, alpha=0.5, s=10, color=COLORS['student_t'])
    ax.plot([min(theoretical), max(theoretical)], [min(theoretical), max(theoretical)], 
           'r--', linewidth=2, label=f'Student-t (df={df:.1f})')
    
    ax.set_xlabel(f'Theoretical Quantiles (Student-t, df={df:.1f})', fontsize=12)
    ax.set_ylabel('Sample Quantiles', fontsize=12)
    ax.set_title(f'{strategy_name}: QQ Plot vs Student-t Distribution', fontsize=14, fontweight='bold')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    
    # Better fit annotation
    ks_stat, ks_pval = stats.kstest(standardized, lambda x: student_t.cdf(x, df))
    ax.text(0.95, 0.05, f'KS Test p-value: {ks_pval:.4f}\n(p > 0.05 = good fit)',
           transform=ax.transAxes, ha='right', va='bottom',
           bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig(output_path / 'qq_student_t.png', dpi=150, bbox_inches='tight')
    plt.close()


def _plot_distribution_comparison(returns: pd.Series, regimes: pd.Series, 
                                  output_path: Path, strategy_name: str):
    """Timeline showing returns colored by regime."""
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    
    # Panel 1: Cumulative returns with regime shading
    ax1 = axes[0]
    cumulative = (1 + returns).cumprod()
    ax1.plot(cumulative.index, cumulative.values, color=COLORS['portfolio'], linewidth=1.5)
    
    # Add regime shading
    regime_colors = {0: COLORS['calm'], 1: COLORS['inflationary'], 2: COLORS['crisis']}
    regime_names = {0: 'Calm', 1: 'Inflationary', 2: 'Crisis'}
    
    for regime in regimes.unique():
        mask = regimes == regime
        if mask.sum() > 0:
            ax1.fill_between(cumulative.index, 0, cumulative.max() * 1.1,
                           where=mask.reindex(cumulative.index, fill_value=False),
                           alpha=0.2, color=regime_colors.get(regime, 'gray'),
                           label=regime_names.get(regime, f'Regime {regime}'), step='mid')
    
    ax1.set_ylabel('Cumulative Wealth', fontsize=11)
    ax1.set_title(f'{strategy_name}: Returns by Regime (Timeline)', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)
    
    # Panel 2: Rolling 30-day returns by regime
    ax2 = axes[1]
    rolling_ret = returns.rolling(30).mean() * 252 * 100  # Annualized %
    ax2.plot(rolling_ret.index, rolling_ret.values, color=COLORS['portfolio'], linewidth=1)
    ax2.axhline(0, color='black', linestyle='-', alpha=0.3)
    
    # Color fill by regime
    for regime in [0, 1, 2]:
        mask = regimes == regime
        if mask.sum() > 0:
            ax2.fill_between(rolling_ret.index, 0, rolling_ret,
                           where=mask.reindex(rolling_ret.index, fill_value=False),
                           alpha=0.4, color=regime_colors.get(regime, 'gray'), step='mid')
    
    ax2.set_ylabel('Rolling 30d Ann. Return (%)', fontsize=11)
    ax2.grid(True, alpha=0.3)
    
    # Panel 3: Regime timeline (binary indicators)
    ax3 = axes[2]
    for i, regime in enumerate([0, 1, 2]):
        regime_indicator = (regimes == regime).astype(float)
        regime_indicator = regime_indicator.reindex(returns.index, fill_value=0)
        ax3.fill_between(regime_indicator.index, i, i + regime_indicator * 0.9,
                        color=regime_colors.get(regime, 'gray'), alpha=0.7,
                        label=regime_names.get(regime, f'Regime {regime}'), step='mid')
    
    ax3.set_yticks([0.45, 1.45, 2.45])
    ax3.set_yticklabels(['Calm', 'Inflationary', 'Crisis'])
    ax3.set_ylabel('Active Regime', fontsize=11)
    ax3.set_xlabel('Date', fontsize=11)
    ax3.set_ylim(0, 3)
    ax3.grid(True, alpha=0.3, axis='x')
    
    # Format date axis
    date_range = (returns.index[-1] - returns.index[0]).days
    if date_range > 365 * 10:
        ax3.xaxis.set_major_locator(mdates.YearLocator(5))
    elif date_range > 365 * 5:
        ax3.xaxis.set_major_locator(mdates.YearLocator(2))
    else:
        ax3.xaxis.set_major_locator(mdates.YearLocator(1))
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    
    plt.tight_layout()
    plt.savefig(output_path / 'distribution_by_regime.png', dpi=150, bbox_inches='tight')
    plt.close()


def _plot_distribution_histograms(returns: pd.Series, regimes: pd.Series, 
                                   output_path: Path, strategy_name: str):
    """Histogram comparison of return distributions by regime."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Overall histogram with fits
    ax = axes[0, 0]
    n, bins, patches = ax.hist(returns * 100, bins=50, density=True, alpha=0.7, 
                                color=COLORS['portfolio'], label='Actual')
    
    # Normal fit
    mu, sigma = returns.mean() * 100, returns.std() * 100
    x = np.linspace(bins[0], bins[-1], 100)
    ax.plot(x, norm.pdf(x, mu, sigma), color=COLORS['normal'], linewidth=2, 
           linestyle='--', label='Normal')
    
    # Student-t fit
    try:
        df, loc, scale = student_t.fit(returns * 100)
        ax.plot(x, student_t.pdf(x, df, loc, scale), color=COLORS['student_t'], 
               linewidth=2, label=f'Student-t (df={df:.1f})')
    except:
        pass
    
    ax.set_title('Overall Return Distribution', fontsize=12, fontweight='bold')
    ax.set_xlabel('Daily Return (%)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Per-regime histograms
    regime_names = {0: 'Calm', 1: 'Inflationary', 2: 'Crisis'}
    regime_colors = {0: COLORS['calm'], 1: COLORS['inflationary'], 2: COLORS['crisis']}
    
    for i, regime in enumerate([0, 1, 2]):
        if i >= 3:
            break
        ax = axes.flatten()[i + 1]
        regime_mask = regimes == regime
        if regime_mask.sum() > 50:
            regime_returns = returns[regime_mask] * 100
            ax.hist(regime_returns, bins=30, density=True, alpha=0.7,
                   color=regime_colors.get(regime, 'gray'))
            
            # Stats
            kurt = stats.kurtosis(regime_returns)
            skew = stats.skew(regime_returns)
            ax.text(0.95, 0.95, f'Kurt: {kurt:.2f}\nSkew: {skew:.2f}',
                   transform=ax.transAxes, ha='right', va='top',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        ax.set_title(f'{regime_names.get(regime, f"Regime {regime}")} ({regime_mask.sum()} days)',
                    fontsize=12, fontweight='bold')
        ax.set_xlabel('Daily Return (%)')
        ax.grid(True, alpha=0.3)
    
    plt.suptitle(f'{strategy_name}: Return Distribution Histograms', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path / 'distribution_histograms.png', dpi=150, bbox_inches='tight')
    plt.close()


def _plot_tail_index_analysis(returns: pd.Series, output_path: Path, strategy_name: str):
    """Plot tail index analysis using Hill estimator."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Left tail
    sorted_left = np.sort(returns[returns < 0])
    k_range = range(20, min(200, len(sorted_left)))
    hill_left = []
    for k in k_range:
        tail = -sorted_left[:k]
        hill = k / np.sum(np.log(tail / tail[-1] + 1e-10))
        hill_left.append(hill)
    
    axes[0].plot(list(k_range), hill_left, color=COLORS['crisis'], linewidth=2)
    axes[0].axhline(3, color='gray', linestyle='--', alpha=0.7, label='Normal (α=∞, approx 3)')
    axes[0].set_xlabel('Number of Tail Observations (k)')
    axes[0].set_ylabel('Hill Estimator (α)')
    axes[0].set_title('Left Tail Index (Lower = Fatter)', fontsize=12, fontweight='bold')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Right tail
    sorted_right = np.sort(returns[returns > 0])[::-1]
    k_range = range(20, min(200, len(sorted_right)))
    hill_right = []
    for k in k_range:
        tail = sorted_right[:k]
        hill = k / np.sum(np.log(tail / tail[-1] + 1e-10))
        hill_right.append(hill)
    
    axes[1].plot(list(k_range), hill_right, color=COLORS['calm'], linewidth=2)
    axes[1].axhline(3, color='gray', linestyle='--', alpha=0.7, label='Normal (α=∞, approx 3)')
    axes[1].set_xlabel('Number of Tail Observations (k)')
    axes[1].set_ylabel('Hill Estimator (α)')
    axes[1].set_title('Right Tail Index', fontsize=12, fontweight='bold')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.suptitle(f'{strategy_name}: Tail Index Analysis', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path / 'tail_index.png', dpi=150, bbox_inches='tight')
    plt.close()


def generate_correlation_regime_analysis(
    returns_df: pd.DataFrame,
    sp500_returns: pd.Series,
    regimes: pd.Series,
    output_dir: str
) -> Dict:
    """
    Analyze stock-bond correlation across regimes.
    
    Creates:
    1. Rolling correlation timeline
    2. Correlation by regime heatmap
    3. Diversification ratio analysis
    """
    output_path = Path(output_dir) / 'correlation_analysis'
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    # Find bond-like assets
    bond_cols = [c for c in returns_df.columns if any(
        x in c.upper() for x in ['TREASURY', 'GOV', 'BOND', 'TIPS', 'CORP', 'AGG']
    )]
    
    if len(bond_cols) == 0 or len(sp500_returns) < 252:
        print("Insufficient data for correlation analysis")
        return results
    
    # Aggregate bond returns
    bond_returns = returns_df[bond_cols].mean(axis=1)
    
    # Align data
    common_idx = bond_returns.index.intersection(sp500_returns.index)
    bond_aligned = bond_returns.loc[common_idx]
    sp500_aligned = sp500_returns.loc[common_idx]
    
    # Rolling correlation
    rolling_corr = bond_aligned.rolling(252).corr(sp500_aligned)
    
    # Generate plots
    _plot_rolling_correlation(rolling_corr, regimes, output_path)
    _plot_correlation_by_regime(bond_aligned, sp500_aligned, regimes, output_path)
    _plot_diversification_ratio(returns_df, regimes, output_path)
    
    # Statistics
    results['avg_correlation'] = float(rolling_corr.mean())
    results['correlation_std'] = float(rolling_corr.std())
    results['pos_corr_pct'] = float((rolling_corr > 0).mean())
    
    print(f"Correlation analysis saved to {output_path}")
    return results


def _plot_rolling_correlation(rolling_corr: pd.Series, regimes: pd.Series, output_path: Path):
    """Plot rolling stock-bond correlation timeline."""
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Main line
    ax.plot(rolling_corr.index, rolling_corr.values, color=COLORS['portfolio'], linewidth=1)
    
    # Fill based on positive/negative
    ax.fill_between(rolling_corr.index, rolling_corr.values, 0,
                   where=rolling_corr > 0, color=COLORS['crisis'], alpha=0.3, label='Positive (Risk)')
    ax.fill_between(rolling_corr.index, rolling_corr.values, 0,
                   where=rolling_corr <= 0, color=COLORS['calm'], alpha=0.3, label='Negative (Diversifying)')
    
    ax.axhline(0, color='black', linestyle='-', linewidth=1)
    ax.axhline(0.3, color='red', linestyle='--', alpha=0.5, label='High Risk Threshold')
    ax.axhline(-0.3, color='green', linestyle='--', alpha=0.5, label='Diversification Threshold')
    
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('252-Day Rolling Correlation', fontsize=12)
    ax.set_title('Stock-Bond Correlation Over Time', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    
    # Format date axis
    date_range = (rolling_corr.index[-1] - rolling_corr.index[0]).days
    if date_range > 365 * 10:
        ax.xaxis.set_major_locator(mdates.YearLocator(5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    
    plt.tight_layout()
    plt.savefig(output_path / 'rolling_correlation.png', dpi=150, bbox_inches='tight')
    plt.close()


def _plot_correlation_by_regime(bond_returns: pd.Series, sp500_returns: pd.Series,
                               regimes: pd.Series, output_path: Path):
    """Plot correlation by regime."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    regime_names = ['Calm', 'Inflationary', 'Crisis']
    colors = [COLORS['calm'], COLORS['inflationary'], COLORS['crisis']]
    correlations = []
    
    common_idx = bond_returns.index.intersection(regimes.index)
    
    for regime in [0, 1, 2]:
        regime_mask = regimes.loc[common_idx] == regime
        if regime_mask.sum() > 50:
            corr = bond_returns.loc[common_idx][regime_mask].corr(
                sp500_returns.reindex(common_idx)[regime_mask]
            )
            correlations.append(corr)
        else:
            correlations.append(0)
    
    bars = ax.bar(regime_names, correlations, color=colors, edgecolor='white', linewidth=2)
    
    ax.axhline(0, color='black', linewidth=1)
    ax.set_ylabel('Stock-Bond Correlation', fontsize=12)
    ax.set_title('Stock-Bond Correlation by Regime', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for bar, corr in zip(bars, correlations):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
               f'{corr:.3f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path / 'correlation_by_regime.png', dpi=150, bbox_inches='tight')
    plt.close()


def _plot_diversification_ratio(returns_df: pd.DataFrame, regimes: pd.Series, output_path: Path):
    """Plot diversification ratio over time."""
    fig, ax = plt.subplots(figsize=(14, 5))
    
    # Calculate rolling diversification ratio
    window = 126  # ~6 months
    div_ratios = []
    dates = []
    
    for i in range(window, len(returns_df)):
        window_returns = returns_df.iloc[i-window:i]
        cov_matrix = window_returns.cov().values
        
        # Equal weight assumption
        n = len(window_returns.columns)
        weights = np.ones(n) / n
        
        individual_vols = np.sqrt(np.diag(cov_matrix))
        weighted_vol = weights @ individual_vols
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
        
        if portfolio_vol > 0:
            div_ratio = weighted_vol / portfolio_vol
            div_ratios.append(div_ratio)
            dates.append(returns_df.index[i])
    
    div_series = pd.Series(div_ratios, index=dates)
    
    ax.plot(div_series.index, div_series.values, color=COLORS['portfolio'], linewidth=1)
    ax.axhline(1, color='red', linestyle='--', alpha=0.7, label='No Diversification')
    
    ax.fill_between(div_series.index, 1, div_series.values, 
                   where=div_series > 1, alpha=0.3, color=COLORS['calm'])
    
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Diversification Ratio', fontsize=12)
    ax.set_title('Portfolio Diversification Ratio Over Time (Higher = Better)', 
                fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path / 'diversification_ratio.png', dpi=150, bbox_inches='tight')
    plt.close()


def generate_statistical_tests(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    output_dir: str
) -> Dict:
    """
    Generate statistical significance tests.
    
    Tests:
    1. Sharpe ratio significance (Jobson-Korkie)
    2. Maximum drawdown bootstrap
    3. Return distribution tests
    """
    output_path = Path(output_dir) / 'statistical_tests'
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    common_idx = portfolio_returns.index.intersection(benchmark_returns.index)
    port = portfolio_returns.loc[common_idx].dropna()
    bench = benchmark_returns.loc[common_idx].dropna()
    
    n = len(port)
    
    # Sharpe ratio test
    sr_port = port.mean() / (port.std() + 1e-10) * np.sqrt(252)
    sr_bench = bench.mean() / (bench.std() + 1e-10) * np.sqrt(252)
    
    # Jobson-Korkie test statistic
    se_diff = np.sqrt((2/n) * (1 - port.corr(bench)) + 
                     (1/(2*n)) * (sr_port**2 + sr_bench**2 - sr_port * sr_bench * (1 + port.corr(bench)**2)))
    z_stat = (sr_port - sr_bench) / (se_diff + 1e-10)
    p_val = 2 * (1 - norm.cdf(abs(z_stat)))
    
    results['sharpe_test'] = {
        'portfolio_sharpe': float(sr_port),
        'benchmark_sharpe': float(sr_bench),
        'sharpe_difference': float(sr_port - sr_bench),
        'z_statistic': float(z_stat),
        'p_value': float(p_val),
        'significant_at_5pct': p_val < 0.05
    }
    
    # Bootstrap MDD
    n_bootstrap = 1000
    mdd_port_dist = []
    mdd_bench_dist = []
    
    for _ in range(n_bootstrap):
        boot_idx = np.random.choice(len(port), size=len(port), replace=True)
        boot_port = port.iloc[boot_idx].values
        boot_bench = bench.iloc[boot_idx].values
        
        cum_port = np.cumprod(1 + boot_port)
        cum_bench = np.cumprod(1 + boot_bench)
        
        mdd_port_dist.append((cum_port / np.maximum.accumulate(cum_port) - 1).min())
        mdd_bench_dist.append((cum_bench / np.maximum.accumulate(cum_bench) - 1).min())
    
    results['mdd_test'] = {
        'portfolio_mdd_mean': float(np.mean(mdd_port_dist)),
        'portfolio_mdd_ci_lower': float(np.percentile(mdd_port_dist, 2.5)),
        'portfolio_mdd_ci_upper': float(np.percentile(mdd_port_dist, 97.5)),
        'benchmark_mdd_mean': float(np.mean(mdd_bench_dist)),
        'significantly_lower': np.mean(mdd_port_dist) > np.mean(mdd_bench_dist)
    }
    
    # Save results
    with open(output_path / 'statistical_tests.txt', 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("STATISTICAL SIGNIFICANCE TESTS\n")
        f.write("=" * 60 + "\n\n")
        
        f.write("1. SHARPE RATIO SIGNIFICANCE (Jobson-Korkie Test)\n")
        f.write("-" * 40 + "\n")
        f.write(f"   Portfolio Sharpe: {sr_port:.3f}\n")
        f.write(f"   Benchmark Sharpe: {sr_bench:.3f}\n")
        f.write(f"   Difference: {sr_port - sr_bench:+.3f}\n")
        f.write(f"   Z-statistic: {z_stat:.3f}\n")
        f.write(f"   P-value: {p_val:.4f}\n")
        f.write(f"   Significant at 5%: {'YES' if p_val < 0.05 else 'NO'}\n\n")
        
        f.write("2. MAXIMUM DRAWDOWN (Bootstrap 95% CI)\n")
        f.write("-" * 40 + "\n")
        f.write(f"   Portfolio MDD: {np.mean(mdd_port_dist)*100:.2f}%\n")
        f.write(f"   95% CI: [{np.percentile(mdd_port_dist, 2.5)*100:.2f}%, {np.percentile(mdd_port_dist, 97.5)*100:.2f}%]\n")
        f.write(f"   Benchmark MDD: {np.mean(mdd_bench_dist)*100:.2f}%\n\n")
    
    # Plot bootstrap distributions
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    axes[0].hist(np.array(mdd_port_dist) * 100, bins=30, alpha=0.7, color=COLORS['portfolio'], label='Portfolio')
    axes[0].hist(np.array(mdd_bench_dist) * 100, bins=30, alpha=0.5, color=COLORS['benchmark'], label='Benchmark')
    axes[0].axvline(np.mean(mdd_port_dist) * 100, color=COLORS['portfolio'], linestyle='--', linewidth=2)
    axes[0].axvline(np.mean(mdd_bench_dist) * 100, color=COLORS['benchmark'], linestyle='--', linewidth=2)
    axes[0].set_xlabel('Maximum Drawdown (%)')
    axes[0].set_ylabel('Frequency')
    axes[0].set_title('Bootstrap MDD Distribution', fontweight='bold')
    axes[0].legend()
    
    # Sharpe ratio distribution (assuming normal approximation)
    sr_se = np.sqrt(1/n + 0.5 * sr_port**2 / n)
    sr_dist = norm.rvs(loc=sr_port, scale=sr_se, size=1000)
    axes[1].hist(sr_dist, bins=30, alpha=0.7, color=COLORS['portfolio'])
    axes[1].axvline(sr_bench, color=COLORS['benchmark'], linewidth=2, linestyle='--', label=f'Benchmark ({sr_bench:.2f})')
    axes[1].axvline(sr_port, color=COLORS['portfolio'], linewidth=2, label=f'Portfolio ({sr_port:.2f})')
    axes[1].set_xlabel('Sharpe Ratio')
    axes[1].set_ylabel('Frequency')
    axes[1].set_title('Sharpe Ratio Distribution', fontweight='bold')
    axes[1].legend()
    
    plt.tight_layout()
    plt.savefig(output_path / 'bootstrap_distributions.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Statistical tests saved to {output_path}")
    return results

