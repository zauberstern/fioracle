"""
Performance metrics and visualization.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import seaborn as sns
from typing import Dict, Optional, List
import warnings
from pathlib import Path

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
    'light': '#e2e8f0',
    'bull': '#48bb78',
    'bear': '#f56565',
    'mdd_marker': '#ff6b6b',  # Bright red for max drawdown
}


def _format_date_axis(ax, dates):
    """Smart date axis formatting - avoids duplicate year labels."""
    date_range = (dates[-1] - dates[0]).days
    
    if date_range > 365 * 10:  # > 10 years
        ax.xaxis.set_major_locator(mdates.YearLocator(5))  # Every 5 years
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    elif date_range > 365 * 5:  # > 5 years
        ax.xaxis.set_major_locator(mdates.YearLocator(2))  # Every 2 years
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    elif date_range > 365 * 2:  # > 2 years
        ax.xaxis.set_major_locator(mdates.YearLocator(1))  # Every year
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    elif date_range > 365:  # > 1 year
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))  # Quarterly
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    else:  # < 1 year
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')


# =============================================================================
# 60/40 Gov/Credit Benchmark Builder
# =============================================================================
def build_60_40_benchmark(
    split_returns: pd.DataFrame,
    config: dict
) -> Optional[tuple]:
    """60/40 gov/credit benchmark from config."""
    bench_cfg = config.get('benchmark_60_40', {})
    if not bench_cfg.get('enabled', False):
        return None
    
    gov_assets = bench_cfg.get('gov_assets', [])
    credit_assets = bench_cfg.get('credit_assets', [])
    gov_weight = bench_cfg.get('gov_weight', 0.6)
    credit_weight = bench_cfg.get('credit_weight', 0.4)
    
    # Find matching columns (partial match on asset name)
    def find_matching_cols(asset_list, columns):
        matches = []
        for asset in asset_list:
            asset_upper = asset.upper()
            for col in columns:
                if asset_upper in col.upper():
                    matches.append(col)
                    break
        return matches
    
    gov_cols = find_matching_cols(gov_assets, split_returns.columns)
    credit_cols = find_matching_cols(credit_assets, split_returns.columns)
    
    if len(gov_cols) < 1 or len(credit_cols) < 1:
        return None
    
    # Compute equal-weighted returns within each group
    gov_returns = split_returns[gov_cols].mean(axis=1)
    credit_returns = split_returns[credit_cols].mean(axis=1)
    
    # Combine with 60/40 weights
    benchmark = gov_weight * gov_returns + credit_weight * credit_returns
    
    name = f"{int(gov_weight*100)}/{int(credit_weight*100)} Gov/Credit"
    
    return benchmark, name


def build_all_benchmarks(
    split_returns: pd.DataFrame,
    config: dict
) -> Dict[str, pd.Series]:
    """Build EW, 60/40, Barbell, and Diversified Core benchmarks."""
    benchmarks = {}
    
    # EW Buy-and-Hold (always available)
    available_assets = [c for c in split_returns.columns if not split_returns[c].isna().all()]
    if len(available_assets) >= 2:
        ew_returns = split_returns[available_assets].mean(axis=1)
        benchmarks[f"EW {len(available_assets)}-Asset B&H"] = ew_returns
    
    # Use enhanced benchmark engine for all other benchmarks
    try:
        from .benchmarks import BenchmarkEngine
        engine = BenchmarkEngine(config)
        
        # 60/40 Gov/Credit
        gov_credit_ret, _ = engine.compute_60_40_benchmark(split_returns)
        if len(gov_credit_ret) > 0:
            benchmarks["60/40 Gov/Credit"] = gov_credit_ret
        
        # Barbell Strategy
        barbell_ret, _ = engine.compute_barbell_benchmark(split_returns)
        if len(barbell_ret) > 0:
            benchmarks["Barbell (85/15)"] = barbell_ret
        
        # Diversified Core FI
        div_ret, _ = engine.compute_diversified_core_benchmark(split_returns)
        if len(div_ret) > 0:
            benchmarks["Diversified Core FI"] = div_ret
            
    except ImportError:
        # Fallback to basic 60/40 if benchmark module not available
        result = build_60_40_benchmark(split_returns, config)
        if result is not None:
            benchmarks[result[1]] = result[0]
    except Exception as e:
        print(f"  Warning: Enhanced benchmarks failed: {e}")
        result = build_60_40_benchmark(split_returns, config)
        if result is not None:
            benchmarks[result[1]] = result[0]
    
    return benchmarks

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica Neue', 'Arial', 'DejaVu Sans'],
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.titleweight': 'bold',
    'axes.labelsize': 10,
    'figure.titlesize': 14,
    'figure.titleweight': 'bold',
})


class Evaluator:
    """Compute Sharpe, drawdown, turnover, and generate charts."""
    
    def __init__(self, annualization_factor: int = 252, transaction_cost: float = 0.0005):
        self.annualization_factor = annualization_factor
        self.transaction_cost = transaction_cost
    
    def compute_portfolio_metrics(
        self,
        portfolio_returns: pd.Series,
        portfolio_weights: pd.DataFrame,
        benchmark_returns: Optional[pd.Series] = None,
        risk_free_rate: Optional[pd.Series] = None,
        returns_are_excess: bool = True
    ) -> Dict[str, float]:
        """Annualized Sharpe, drawdown, Calmar, turnover, total return."""
        if len(portfolio_returns) == 0 or portfolio_returns.isna().all():
            return self._empty_metrics()
        
        returns = portfolio_returns.dropna()
        n_days = len(returns)
        
        if n_days == 0:
            return self._empty_metrics()
        
        # Handle excess returns computation
        # BUG FIX: Backtest now returns excess returns, so don't subtract RF again
        if returns_are_excess:
            # Returns from backtest are already excess - use directly
            excess_rets = returns
            rf = pd.Series(0.0, index=returns.index)
        elif risk_free_rate is not None and risk_free_rate.notna().any():
            # Raw returns provided - subtract RF to get excess
            rf = risk_free_rate.reindex(returns.index)
            rf = rf.ffill(limit=5).fillna(0.0)
            excess_rets = returns - rf
        else:
            # No RF available - use raw returns
            excess_rets = returns
            rf = pd.Series(0.0, index=returns.index)
        
        # CORRECT ANNUALIZATION:
        # Daily mean -> annualized mean
        daily_mean = excess_rets.mean()
        daily_std = excess_rets.std()
        
        # Annualized figures
        ann_excess_return = daily_mean * self.annualization_factor
        ann_volatility = daily_std * np.sqrt(self.annualization_factor)
        
        # Sharpe ratio (annualized)
        if daily_std > 1e-10:
            sharpe_ratio = (daily_mean / daily_std) * np.sqrt(self.annualization_factor)
        else:
            sharpe_ratio = 0.0
        
        # Total cumulative return (for wealth curve)
        total_return = (1 + returns).prod() - 1
        
        # Maximum drawdown (on TOTAL returns, not excess)
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Calmar ratio (annualized return / |max drawdown|)
        n_years = n_days / self.annualization_factor
        ann_total_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0
        calmar_ratio = ann_total_return / abs(max_drawdown) if max_drawdown != 0 else 0.0
        
        # Turnover
        asset_cols = [c for c in portfolio_weights.columns if c != 'cash_allocation']
        if len(asset_cols) > 0 and len(portfolio_weights) > 1:
            turnover = portfolio_weights[asset_cols].diff().abs().sum(axis=1).mean()
        else:
            turnover = 0.0
        
        # Average leverage (sum of risky weights)
        if len(asset_cols) > 0:
            average_leverage = portfolio_weights[asset_cols].sum(axis=1).mean()
        else:
            average_leverage = 0.0
        
        return {
            'ann_excess_return': ann_excess_return,
            'ann_volatility': ann_volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar_ratio,
            'turnover': turnover,
            'average_leverage': average_leverage,
            'total_return': total_return,
            'n_days': n_days
        }
    
    def _empty_metrics(self) -> Dict[str, float]:
        return {
            'ann_excess_return': 0.0, 'ann_volatility': 0.0, 'sharpe_ratio': 0.0,
            'max_drawdown': 0.0, 'calmar_ratio': 0.0, 'turnover': 0.0,
            'average_leverage': 0.0, 'total_return': 0.0, 'n_days': 0
        }
    
    def compute_zero_one_strategy_sharpe(
        self,
        asset_returns: pd.Series,
        regime_forecasts: pd.Series,
        risk_free_rate: Optional[pd.Series] = None,
        apply_transaction_costs: bool = True
    ) -> float:
        """0/1 strategy: invest when bullish (0), cash when bearish (1)."""
        common_idx = asset_returns.index.intersection(regime_forecasts.index)
        if len(common_idx) == 0:
            return 0.0
        
        asset_rets = asset_returns.loc[common_idx]
        regimes = regime_forecasts.loc[common_idx]
        if risk_free_rate is not None and risk_free_rate.notna().any():
            rf_rets = risk_free_rate.reindex(common_idx).ffill(limit=5).fillna(0.0)
        else:
            rf_rets = pd.Series(0.0, index=common_idx)
        
        strategy_rets = asset_rets.copy()
        strategy_rets[regimes == 1] = rf_rets[regimes == 1]
        
        if apply_transaction_costs:
            switches = (regimes != regimes.shift(1)).astype(int)
            switches.iloc[0] = 1
            strategy_rets = strategy_rets - switches * self.transaction_cost
        
        excess_rets = strategy_rets - rf_rets
        
        if excess_rets.std() > 1e-10:
            return (excess_rets.mean() / excess_rets.std()) * np.sqrt(self.annualization_factor)
            return 0.0
    
    def tune_lambda_fast(
        self,
        asset_features: pd.DataFrame,
        asset_returns: pd.Series,
        lambda_candidates: List[float] = [0.1, 1.0, 5.0, 10.0],
        n_splits: int = 5
    ) -> tuple:
        """Time-series CV to pick the best lambda."""
        from sklearn.model_selection import TimeSeriesSplit
        from .regimes import JumpModel
        
        common_idx = asset_features.index.intersection(asset_returns.index)
        features = asset_features.loc[common_idx].dropna()
        returns = asset_returns.loc[common_idx]
        
        results = []
        tscv = TimeSeriesSplit(n_splits=n_splits)
        
        for lam in lambda_candidates:
            fold_sharpes = []
            
            for train_idx, test_idx in tscv.split(features):
                try:
                    train_features = features.iloc[train_idx]
                    test_features = features.iloc[test_idx]
                    test_returns = returns.iloc[test_idx]
                    
                    jm = JumpModel(lambda_jump=lam, n_states=2)
                    jm.fit(train_features.values)
                    states = jm.predict(test_features.values)
                    
                    regimes = pd.Series(states, index=test_features.index)
                    state_rets = {s: test_returns[regimes == s].sum() for s in [0, 1]}
                    bearish = min(state_rets, key=state_rets.get)
                    if bearish == 0:
                        regimes = 1 - regimes
                    
                    strategy_rets = test_returns.copy()
                    strategy_rets[regimes == 1] = 0.0
                    
                    if strategy_rets.std() > 1e-10:
                        sharpe = (strategy_rets.mean() / strategy_rets.std()) * np.sqrt(self.annualization_factor)
                    else:
                        sharpe = 0.0
                    fold_sharpes.append(sharpe)
                except:
                    fold_sharpes.append(0.0)
            
            results.append({'lambda': lam, 'avg_sharpe': np.mean(fold_sharpes), 'std_sharpe': np.std(fold_sharpes)})
        
        results_df = pd.DataFrame(results).sort_values('avg_sharpe', ascending=False)
        optimal_lambda = results_df.iloc[0]['lambda']
        return optimal_lambda, results_df
    
    def generate_all_plots(
        self,
        portfolio_returns: pd.Series,
        portfolio_weights: pd.DataFrame,
        benchmark_returns: Optional[pd.Series] = None,
        benchmark_name: str = "EW Benchmark",
        regime_labels: Optional[pd.Series] = None,
        strategy_name: str = "JM-XGB",
        save_dir: Optional[str] = None,
        all_benchmarks: Optional[Dict[str, pd.Series]] = None
    ):
        """Save cumulative, drawdown, allocation, Sharpe, heatmap, distribution, and pie charts."""
        if len(portfolio_returns) == 0:
            self._save_empty_placeholder(save_dir, strategy_name)
            return
        
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        metrics = self.compute_portfolio_metrics(portfolio_returns, portfolio_weights)
        
        # 1. Cumulative Returns Plot (with all benchmarks)
        self._plot_cumulative_returns(
            portfolio_returns, benchmark_returns, benchmark_name, 
            regime_labels, strategy_name, save_dir, all_benchmarks
        )
        
        # 2. Drawdown Plot
        self._plot_drawdown(
            portfolio_returns, benchmark_returns, benchmark_name, save_dir
        )
        
        # 3. Asset Allocation Timeline
        self._plot_allocation_timeline(portfolio_weights, save_dir)
        
        # 4. Rolling Sharpe Ratio (with all benchmarks)
        self._plot_rolling_sharpe(
            portfolio_returns, benchmark_returns, benchmark_name, save_dir, all_benchmarks
        )
        
        # 5. Monthly Returns Heatmap
        self._plot_monthly_heatmap(portfolio_returns, save_dir)
        
        # 6. Return Distribution
        self._plot_return_distribution(
            portfolio_returns, benchmark_returns, benchmark_name, save_dir
        )
        
        # 7. Allocation Summary Pie
        self._plot_allocation_pie(portfolio_weights, save_dir)
        
        print(f"  ✓ Generated 7 separate plots in {save_dir}")
    
    def _plot_cumulative_returns(self, returns, benchmark, bench_name, regimes, strategy, save_dir, all_benchmarks=None):
        """Plot cumulative wealth with regime shading and multiple benchmarks."""
        fig, ax = plt.subplots(figsize=(14, 7))
        
        cumulative = (1 + returns).cumprod()
        ax.plot(cumulative.index, cumulative.values, color=COLORS['primary'], 
               linewidth=2.5, label=strategy)
        
        # Plot all benchmarks if provided
        bench_colors = ['#718096', '#805AD5', '#D69E2E', '#319795']
        bench_styles = ['--', '-.', ':', (0, (3, 1, 1, 1))]
        
        if all_benchmarks:
            for i, (name, bench_ret) in enumerate(all_benchmarks.items()):
                common_idx = returns.index.intersection(bench_ret.index)
                if len(common_idx) > 0:
                    bench_aligned = bench_ret.loc[common_idx]
                    bench_cum = (1 + bench_aligned).cumprod()
                    ax.plot(bench_cum.index, bench_cum.values, 
                           color=bench_colors[i % len(bench_colors)],
                           linewidth=1.5, linestyle=bench_styles[i % len(bench_styles)], 
                           label=name, alpha=0.8)
        elif benchmark is not None:
            common_idx = returns.index.intersection(benchmark.index)
            if len(common_idx) > 0:
                bench_aligned = benchmark.loc[common_idx]
                bench_cum = (1 + bench_aligned).cumprod()
                ax.plot(bench_cum.index, bench_cum.values, color=COLORS['neutral'], 
                       linewidth=2, linestyle='--', label=bench_name, alpha=0.8)
        
        if regimes is not None:
            regime_aligned = regimes.reindex(returns.index)
            bear_mask = regime_aligned == 1
            if bear_mask.any():
                ax.fill_between(returns.index, 0, cumulative.max() * 1.1,
                               where=bear_mask, alpha=0.15, color=COLORS['bear'],
                               label='Bear Regime', step='mid')
        
        # Final value annotation
        final_val = cumulative.iloc[-1]
        ax.annotate(f'{final_val:.2f}x', xy=(cumulative.index[-1], final_val),
                   xytext=(10, 0), textcoords='offset points',
                   fontsize=12, fontweight='bold', color=COLORS['primary'])
        
        ax.set_title(f'Cumulative Wealth: {strategy}', fontsize=14, fontweight='bold')
        ax.set_ylabel('Portfolio Value (Initial = 1.0)')
        ax.legend(loc='upper left', frameon=True, fontsize=9, ncol=2)
        ax.grid(True, alpha=0.3)
        
        # FIX: Smart x-axis tick labels - no duplicate years
        _format_date_axis(ax, returns.index)
        
        plt.tight_layout()
        plt.savefig(f'{save_dir}/cumulative_returns.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_drawdown(self, returns, benchmark, bench_name, save_dir):
        """Plot drawdown analysis with improved styling."""
        fig, ax = plt.subplots(figsize=(14, 5))
        
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max * 100
        
        ax.fill_between(drawdown.index, drawdown.values, 0, color=COLORS['danger'], alpha=0.3)
        ax.plot(drawdown.index, drawdown.values, color=COLORS['danger'], 
               linewidth=1.5, label='Strategy')
        
        # Benchmark drawdown
        if benchmark is not None:
            common_idx = returns.index.intersection(benchmark.index)
            if len(common_idx) > 100:
                bench_aligned = benchmark.loc[common_idx]
                bench_cum = (1 + bench_aligned).cumprod()
                bench_running_max = bench_cum.cummax()
                bench_dd = (bench_cum - bench_running_max) / bench_running_max * 100
                ax.plot(bench_dd.index, bench_dd.values, color=COLORS['neutral'],
                       linewidth=1.5, linestyle='--', alpha=0.7, label=bench_name)
        
        # Max drawdown annotation - IMPROVED STYLING
        mdd_idx = drawdown.idxmin()
        mdd_val = drawdown.min()
        
        # Use bright marker color
        ax.scatter([mdd_idx], [mdd_val], color=COLORS['mdd_marker'], s=150, zorder=5, 
                  marker='v', edgecolor='white', linewidth=2)
        
        # Position annotation intelligently (above or below based on space)
        y_offset = 15 if mdd_val > drawdown.mean() else -25
        ax.annotate(
            f'Max DD: {mdd_val:.2f}%\n{mdd_idx.strftime("%Y-%m-%d")}', 
            xy=(mdd_idx, mdd_val),
            xytext=(30, y_offset), textcoords='offset points',
            fontsize=10, fontweight='bold', color=COLORS['mdd_marker'],
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=COLORS['mdd_marker'], alpha=0.9),
            arrowprops=dict(arrowstyle='->', color=COLORS['mdd_marker'], lw=2)
        )
        
        ax.set_title('Underwater Chart (Drawdown)', fontsize=13, fontweight='bold')
        ax.set_ylabel('Drawdown (%)')
        ax.legend(loc='lower left')
        ax.grid(True, alpha=0.3)
        
        # Smart date axis
        _format_date_axis(ax, returns.index)
        
        plt.tight_layout()
        plt.savefig(f'{save_dir}/drawdown.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_allocation_timeline(self, weights, save_dir):
        """Plot asset allocation over time as stacked area with display names."""
        fig, ax = plt.subplots(figsize=(14, 6))
        
        # Filter ONLY investable asset columns (exclude RF, ancillary, etc.)
        excluded_patterns = ['cash_allocation', 'date', 'risk_free', 'sp500', 'yield', 'ancillary']
        asset_cols = [c for c in weights.columns 
                     if not any(p in c.lower() for p in excluded_patterns)]
        
        if len(asset_cols) == 0:
            ax.text(0.5, 0.5, 'No allocation data', ha='center', va='center')
            plt.savefig(f'{save_dir}/allocation_timeline.png', dpi=150)
            plt.close()
            return
        
        # Resample to weekly for cleaner visualization
        weights_weekly = weights[asset_cols].resample('W').mean()
        
        # Add cash/risk-free allocation (difference from 1)
        total_risky = weights_weekly.sum(axis=1)
        cash_allocation = (1 - total_risky).clip(lower=0)
        if cash_allocation.mean() > 0.01:  # Only show if meaningful
            weights_weekly['Uninvested Cash'] = cash_allocation
        
        # Filter out columns with zero allocation
        weights_weekly = weights_weekly.loc[:, (weights_weekly > 0.001).any()]
        
        # Convert column names to display names
        display_labels = [self._get_display_name(c) if c != 'Uninvested Cash' else c 
                         for c in weights_weekly.columns]
        
        # Create stacked area
        colors = plt.cm.Set3(np.linspace(0, 1, len(weights_weekly.columns)))
        ax.stackplot(weights_weekly.index, weights_weekly.values.T, 
                    labels=display_labels, colors=colors, alpha=0.8)
        
        ax.set_title('Asset Allocation Over Time', fontsize=13, fontweight='bold')
        ax.set_ylabel('Weight')
        ax.set_ylim(0, 1.05)
        ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Smart date axis
        _format_date_axis(ax, weights.index)
        
        plt.tight_layout()
        plt.savefig(f'{save_dir}/allocation_timeline.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_rolling_sharpe(self, returns, benchmark, bench_name, save_dir, all_benchmarks=None):
        """Plot rolling Sharpe with smart date axis and multiple benchmarks."""
        fig, ax = plt.subplots(figsize=(14, 5))
        window = min(252, len(returns) // 3)
        
        if len(returns) < window:
            ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center')
            plt.savefig(f'{save_dir}/rolling_sharpe.png', dpi=150)
            plt.close()
            return
        
        rolling_mean = returns.rolling(window=window, min_periods=window//2).mean()
        rolling_std = returns.rolling(window=window, min_periods=window//2).std()
        rolling_sharpe = ((rolling_mean / rolling_std) * np.sqrt(252)).clip(-5, 5)
        
        ax.plot(rolling_sharpe.index, rolling_sharpe.values, color=COLORS['primary'], 
               linewidth=2, label='Strategy')
        
        # Plot all benchmarks if provided
        bench_colors = ['#718096', '#805AD5', '#D69E2E', '#319795']
        bench_styles = ['--', '-.', ':', (0, (3, 1, 1, 1))]
        
        if all_benchmarks:
            for i, (name, bench_ret) in enumerate(all_benchmarks.items()):
                common_idx = returns.index.intersection(bench_ret.index)
                if len(common_idx) > window:
                    bench_aligned = bench_ret.loc[common_idx]
                    bench_mean = bench_aligned.rolling(window, min_periods=window//2).mean()
                    bench_std = bench_aligned.rolling(window, min_periods=window//2).std()
                    bench_sharpe = ((bench_mean / bench_std) * np.sqrt(252)).clip(-5, 5)
                    ax.plot(bench_sharpe.index, bench_sharpe.values, 
                           color=bench_colors[i % len(bench_colors)],
                           linewidth=1.5, linestyle=bench_styles[i % len(bench_styles)], 
                           alpha=0.7, label=name)
        elif benchmark is not None:
            common_idx = returns.index.intersection(benchmark.index)
            if len(common_idx) > window:
                bench_aligned = benchmark.loc[common_idx]
                bench_mean = bench_aligned.rolling(window, min_periods=window//2).mean()
                bench_std = bench_aligned.rolling(window, min_periods=window//2).std()
                bench_sharpe = ((bench_mean / bench_std) * np.sqrt(252)).clip(-5, 5)
                ax.plot(bench_sharpe.index, bench_sharpe.values, color=COLORS['neutral'],
                       linewidth=1.5, linestyle='--', alpha=0.7, label=bench_name)
        
        ax.axhline(1.0, color=COLORS['success'], linestyle=':', alpha=0.7, label='Good (1.0)')
        ax.axhline(0, color=COLORS['neutral'], linestyle='-', alpha=0.3)
        
        ax.set_title(f'Rolling {window}-Day Sharpe Ratio', fontsize=13, fontweight='bold')
        ax.set_ylabel('Sharpe Ratio')
        ax.set_ylim(-5, 5)
        ax.legend(loc='upper left', fontsize=8, ncol=2)
        ax.grid(True, alpha=0.3)
        
        # Smart date axis
        _format_date_axis(ax, returns.index)
        
        plt.tight_layout()
        plt.savefig(f'{save_dir}/rolling_sharpe.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_monthly_heatmap(self, returns, save_dir):
        """Plot monthly returns heatmap."""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        monthly = returns.resample('M').apply(lambda x: (1 + x).prod() - 1) * 100
        monthly_df = pd.DataFrame({
            'year': monthly.index.year,
            'month': monthly.index.month,
            'return': monthly.values
        })
        
        pivot = monthly_df.pivot_table(index='year', columns='month', values='return')
        
        if len(pivot) == 0 or pivot.shape[1] < 3:
            ax.text(0.5, 0.5, 'Insufficient data for heatmap', ha='center', va='center')
            plt.savefig(f'{save_dir}/monthly_heatmap.png', dpi=150)
            plt.close()
            return
        
        cmap = sns.diverging_palette(10, 130, as_cmap=True)
        vmax = max(abs(pivot.min().min()), abs(pivot.max().max()), 5)
        
        sns.heatmap(pivot, annot=True, fmt='.1f', cmap=cmap, center=0,
                   vmin=-vmax, vmax=vmax, cbar_kws={'label': 'Return (%)'},
                   ax=ax, linewidths=0.5, annot_kws={'size': 8})
        
        ax.set_title('Monthly Returns (%)', fontsize=13, fontweight='bold')
        
        # Set month labels only if we have full year data
        month_labels = ['J','F','M','A','M','J','J','A','S','O','N','D']
        actual_months = pivot.columns.tolist()
        if len(actual_months) == 12:
            ax.set_xticklabels(month_labels)
        else:
            ax.set_xticklabels([month_labels[m-1] if m <= 12 else str(m) for m in actual_months])
        
        plt.tight_layout()
        plt.savefig(f'{save_dir}/monthly_heatmap.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_return_distribution(self, returns, benchmark, bench_name, save_dir):
        """Plot return distribution histogram."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.hist(returns.values * 100, bins=50, alpha=0.7, color=COLORS['primary'],
               label='Strategy', edgecolor='white', density=True)
        
        if benchmark is not None:
            common_idx = returns.index.intersection(benchmark.index)
            if len(common_idx) > 0:
                bench_aligned = benchmark.loc[common_idx]
                ax.hist(bench_aligned.values * 100, bins=50, alpha=0.5, 
                       color=COLORS['neutral'], label=bench_name, density=True)
        
        mean_ret = returns.mean() * 100
        ax.axvline(mean_ret, color=COLORS['accent'], linestyle='-', linewidth=2,
                  label=f'Mean: {mean_ret:.3f}%')
        ax.axvline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
        
        ax.set_title('Daily Return Distribution', fontsize=13, fontweight='bold')
        ax.set_xlabel('Daily Return (%)')
        ax.set_ylabel('Density')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f'{save_dir}/return_distribution.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def _get_display_name(self, asset_name: str) -> str:
        """Get human-readable display name for an asset from config or fallback."""
        import yaml
        from pathlib import Path
        
        # Try to load display names from config.yaml
        config_path = Path(__file__).parent.parent.parent / 'config' / 'config.yaml'
        config_display_names = {}
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    config_display_names = config.get('assets', {}).get('display_names', {})
            except:
                pass
        
        # Check config display names (try multiple case variations)
        upper_name = asset_name.upper()
        for key, value in config_display_names.items():
            if key.upper() == upper_name:
                return value
        
        # Comprehensive fallback display names
        fallback_names = {
            'US_CASH_RETURN': 'US T-Bills',
            'US_10Y_GOV_BOND_RETURN': 'US 10Y Treasury',
            'IBOXX_USD_TREASURY_TOTAL_RETURN': 'Treasury Index',
            'IBOXX_USD_SOVEREIGN_TOTAL_RETURN': 'Sovereign Index',
            'US_BOND_AGG_TOTAL_RETURN': 'US Agg Bond',
            'IBOXX_USD_CORPORATE_TOTAL_RETURN': 'Corporate IG',
            'US_AAA_CORP_BOND_TOTAL_RETURN': 'US AAA Corp',
            'US_BAA_CORP_BOND_TOTAL_RETURN': 'US BBB Corp',
            'IBOXX_USD_LIQ_HY_TOTAL_RETURN': 'USD HY Liq',
            'IBOXX_USD_LIQ_IG_TOTAL_RETURN': 'USD IG Liq',
            'CDX_HY_5Y_TOTAL_RETURN': 'CDX HY 5Y',
            'CDX_HY_3Y_TOTAL_RETURN': 'CDX HY 3Y',
            'CDX_IG_5Y_TOTAL_RETURN': 'CDX IG 5Y',
            'US_TIPS_0_5_TOTAL_RETURN': 'US TIPS 0-5Y',
            'US_INFLATION_SWAP_1Y_RETURN': 'IL Swap 1Y',
            'US_INFLATION_SWAP_2Y_RETURN': 'IL Swap 2Y',
            'US_INFLATION_SWAP_5Y_RETURN': 'IL Swap 5Y',
            'US_INFLATION_SWAP_10Y_RETURN': 'IL Swap 10Y',
            'IBOXX_UK_IL_GILT_TOTAL_RETURN': 'UK IL Gilts',
            'GLOBAL_ILB_0_5_TOTAL_RETURN': 'Global ILB',
            'IBOXX_GEMX_USD_EMEA_IL_HDG_TOTAL_RETURN': 'EM ILB',
            'GOLD_TOTAL_RETURN': 'Gold',
            'CHF_TOTAL_RETURN': 'Swiss Franc',
            'CH_SWISS_SAFE_TR': 'Swiss Safe',
            'USD_SWAPTION_6M_5Y_TOTAL_RETURN': 'Swaption 6M5Y',
            'USD_SWAPTION_1Y_5Y_TOTAL_RETURN': 'Swaption 1Y5Y',
            'USD_SWAPTION_1Y_10Y_TOTAL_RETURN': 'Swaption 1Y10Y',
            'WTI_TOTAL_RETURN': 'WTI Oil',
        }
        
        # Try exact match
        if upper_name in fallback_names:
            return fallback_names[upper_name]
        
        # Try partial match (for names that might differ slightly)
        for key, value in fallback_names.items():
            # Check if the key is contained in the name or vice versa
            if key in upper_name or upper_name in key:
                return value
        
        # Smart cleanup for names not in dictionary
        clean = asset_name.upper()
        
        # Remove common suffixes first
        for suffix in ['_TOTAL_RETURN', '_RETURN', '_TR', '_INDEX']:
            if clean.endswith(suffix):
                clean = clean[:-len(suffix)]
        
        # Remove common prefixes
        for prefix in ['IBOXX_USD_', 'IBOXX_', 'USD_', 'US_']:
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
                break  # Only remove one prefix
        
        # Replace underscores with spaces
        clean = clean.replace('_', ' ').strip()
        
        # Capitalize properly
        if len(clean) <= 5:
            return clean.upper()
        
        # Title case for longer names
        return clean.title()[:20]
    
    def _plot_allocation_pie(self, weights, save_dir):
        """Plot average allocation pie chart with human-readable labels."""
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Exclude ancillary assets and cash_allocation
        excluded_patterns = ['RF_WEIGHT', 'RISK_FREE', 'ANCILLARY', 'SP500', 'YIELD']
        asset_cols = [c for c in weights.columns 
                      if not any(pat in c.upper() for pat in excluded_patterns)]
        
        if len(asset_cols) == 0:
            ax.text(0.5, 0.5, 'No allocation data', ha='center', va='center')
            plt.savefig(f'{save_dir}/allocation_pie.png', dpi=150)
            plt.close()
            return
        
        avg_weights = weights[asset_cols].mean()
        
        # cash_allocation represents uninvested cash held at risk-free rate
        # This is implicit cash, label it appropriately
        avg_rf = weights['cash_allocation'].mean() if 'cash_allocation' in weights.columns else 0
        
        # Combine small allocations
        threshold = 0.02
        large = avg_weights[avg_weights >= threshold]
        small_sum = avg_weights[avg_weights < threshold].sum()
        
        if small_sum > 0:
            large['Other Assets'] = small_sum
        if avg_rf > threshold:
            large['Uninvested Cash'] = avg_rf
        
        # Convert to display names
        display_labels = [self._get_display_name(n) if n not in ['Other Assets', 'Uninvested Cash'] else n 
                         for n in large.index]
        
        colors = plt.cm.Set3(np.linspace(0, 1, len(large)))
        wedges, texts, autotexts = ax.pie(
            large.values, labels=None, autopct='%1.1f%%',
            colors=colors, startangle=90, pctdistance=0.75,
            wedgeprops=dict(width=0.5, edgecolor='white')
        )
        
        for autotext in autotexts:
            autotext.set_fontsize(9)
            autotext.set_fontweight('bold')
        
        ax.set_title('Average Portfolio Allocation', fontsize=13, fontweight='bold')
        ax.legend(wedges, display_labels, loc='center left', bbox_to_anchor=(1, 0.5))
        
        plt.tight_layout()
        plt.savefig(f'{save_dir}/allocation_pie.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def _save_empty_placeholder(self, save_dir, strategy_name):
        """Create placeholder for empty data."""
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, f'No data available for {strategy_name}',
               ha='center', va='center', fontsize=14, color=COLORS['neutral'])
        ax.axis('off')
        plt.savefig(f'{save_dir}/no_data.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    # Keep backward compatibility
    def plot_comprehensive_results(self, *args, **kwargs):
        """Backward compatibility wrapper."""
        return self.generate_all_plots(*args, **kwargs)
    
    def plot_essential(self, portfolio_returns, portfolio_weights, 
                      benchmark_returns=None, regime_labels=None, save_dir=None):
        """Generate essential visualization."""
        self.generate_all_plots(
            portfolio_returns, portfolio_weights, benchmark_returns, 
            "EW Benchmark", regime_labels, "Portfolio", save_dir
        )
    
    def evaluate(self, portfolio_returns, portfolio_weights, 
                benchmark_returns=None, regime_labels=None,
                risk_free_rate=None, plot=True, save_dir=None, verbose=True):
        """Complete evaluation: metrics + plots."""
        metrics = self.compute_portfolio_metrics(
            portfolio_returns, portfolio_weights, benchmark_returns, risk_free_rate
        )
        
        if verbose:
            print("="*60)
            print("Portfolio Performance Metrics (Annualized)")
            print("="*60)
            print(f"Ann Excess Return: {metrics['ann_excess_return']*100:>8.2f}%")
            print(f"Ann Volatility:    {metrics['ann_volatility']*100:>8.2f}%")
            print(f"Sharpe Ratio:      {metrics['sharpe_ratio']:>8.2f}")
            print(f"Max Drawdown:      {metrics['max_drawdown']*100:>8.2f}%")
            print(f"Calmar Ratio:      {metrics['calmar_ratio']:>8.2f}")
            print(f"Total Return:      {metrics['total_return']*100:>8.2f}%")
            print("="*60 + "\n")
        
        if plot and save_dir:
            self.generate_all_plots(
                portfolio_returns, portfolio_weights, benchmark_returns,
                "EW Benchmark", regime_labels, "JM-XGB", save_dir
            )
        
        return metrics
    

def compute_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    if len(returns) == 0 or returns.std() < 1e-10:
        return 0.0
    excess = returns - risk_free_rate
    return (excess.mean() / excess.std()) * np.sqrt(252)


def compute_all_metrics(portfolio_returns, benchmark_returns=None):
    evaluator = Evaluator()
    return evaluator.compute_portfolio_metrics(
        portfolio_returns, pd.DataFrame(index=portfolio_returns.index), benchmark_returns
    )


def generate_benchmark_comparison_report(
    portfolio_returns: pd.Series,
    portfolio_weights: pd.DataFrame,
    benchmarks: Dict[str, pd.Series],
    strategy_name: str,
    save_dir: str,
    risk_free_rate: Optional[pd.Series] = None
) -> pd.DataFrame:
    """Table of metrics for strategy vs. all benchmarks."""
    evaluator = Evaluator()
    
    results = []
    
    # Strategy metrics
    strategy_metrics = evaluator.compute_portfolio_metrics(
        portfolio_returns, portfolio_weights, None, risk_free_rate
    )
    strategy_metrics['name'] = strategy_name
    results.append(strategy_metrics)
    
    # Benchmark metrics
    dummy_weights = pd.DataFrame({'dummy': 1.0}, index=portfolio_returns.index)
    
    for bench_name, bench_returns in benchmarks.items():
        common_idx = portfolio_returns.index.intersection(bench_returns.index)
        if len(common_idx) < 50:
            continue
            
        bench_aligned = bench_returns.loc[common_idx]
        rf_aligned = risk_free_rate.loc[common_idx] if risk_free_rate is not None else None
        
        # Benchmarks use RAW returns, not excess - must subtract RF
        bench_metrics = evaluator.compute_portfolio_metrics(
            bench_aligned, dummy_weights.loc[common_idx], None, rf_aligned,
            returns_are_excess=False  # Benchmark returns are raw, need RF subtraction
        )
        bench_metrics['name'] = bench_name
        results.append(bench_metrics)
    
    # Create comparison DataFrame
    comparison_df = pd.DataFrame(results)
    comparison_df = comparison_df.set_index('name')
    
    # Reorder columns
    col_order = ['total_return', 'ann_excess_return', 'ann_volatility', 'sharpe_ratio',
                'max_drawdown', 'calmar_ratio', 'turnover', 'n_days']
    col_order = [c for c in col_order if c in comparison_df.columns]
    comparison_df = comparison_df[col_order]
    
    # Format for display
    comparison_df['total_return'] = comparison_df['total_return'].apply(lambda x: f"{x*100:.2f}%")
    comparison_df['ann_excess_return'] = comparison_df['ann_excess_return'].apply(lambda x: f"{x*100:.2f}%")
    comparison_df['ann_volatility'] = comparison_df['ann_volatility'].apply(lambda x: f"{x*100:.2f}%")
    comparison_df['sharpe_ratio'] = comparison_df['sharpe_ratio'].apply(lambda x: f"{x:.3f}")
    comparison_df['max_drawdown'] = comparison_df['max_drawdown'].apply(lambda x: f"{x*100:.2f}%")
    comparison_df['calmar_ratio'] = comparison_df['calmar_ratio'].apply(lambda x: f"{x:.3f}")
    
    # Save to CSV
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(save_path / 'benchmark_comparison.csv')
    
    # Also save as formatted text
    with open(save_path / 'benchmark_comparison.txt', 'w') as f:
        f.write("="*80 + "\n")
        f.write(f"BENCHMARK COMPARISON REPORT\n")
        f.write("="*80 + "\n\n")
        f.write(comparison_df.to_string())
        f.write("\n\n")
        f.write("-"*80 + "\n")
        f.write("Legend:\n")
        f.write("  - EW B&H: Equal-weight buy-and-hold across all assets\n")
        f.write("  - 60/40 Gov/Credit: 60% government bonds, 40% credit (quarterly rebalanced)\n")
        f.write("  - Barbell (85/15): 85% safe assets, 15% risky/hedging instruments\n")
        f.write("  - Diversified Core FI: Equal allocation across rates, credit, inflation, hedges\n")
        f.write("-"*80 + "\n")
    
    print(f"  ✓ Benchmark comparison saved to {save_path}")
    
    return comparison_df
