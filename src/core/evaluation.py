"""
Performance evaluation and professional visualizations.

Key Fixes Applied:
- Separate plot files instead of combined comprehensive analysis
- Correct benchmark labeling (shows actual benchmark type)
- Fixed return annualization and scaling consistency
- Fixed benchmark drawdown truncation bug
- Fixed rolling Sharpe calculation issues
- Added asset allocation timeline chart
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
}

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
    """Performance evaluation with proper return calculations."""
    
    def __init__(self, annualization_factor: int = 252, transaction_cost: float = 0.0005):
        self.annualization_factor = annualization_factor
        self.transaction_cost = transaction_cost
    
    def compute_portfolio_metrics(
        self,
        portfolio_returns: pd.Series,
        portfolio_weights: pd.DataFrame,
        benchmark_returns: Optional[pd.Series] = None,
        risk_free_rate: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """Compute annualized portfolio performance metrics."""
        if len(portfolio_returns) == 0 or portfolio_returns.isna().all():
            return self._empty_metrics()
        
        returns = portfolio_returns.dropna()
        n_days = len(returns)
        
        if n_days == 0:
            return self._empty_metrics()
        
        # Risk-free rate alignment
        if risk_free_rate is not None:
            rf = risk_free_rate.reindex(returns.index).fillna(0.0)
            excess_rets = returns - rf
        else:
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
        asset_cols = [c for c in portfolio_weights.columns if c != 'rf_weight']
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
        """Compute Sharpe Ratio of 0/1 Strategy."""
        common_idx = asset_returns.index.intersection(regime_forecasts.index)
        if len(common_idx) == 0:
            return 0.0
        
        asset_rets = asset_returns.loc[common_idx]
        regimes = regime_forecasts.loc[common_idx]
        rf_rets = risk_free_rate.reindex(common_idx).fillna(0.0) if risk_free_rate is not None else pd.Series(0.0, index=common_idx)
        
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
        """Optimize lambda using time-series cross-validation."""
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
        save_dir: Optional[str] = None
    ):
        """Generate all plots as SEPARATE files."""
        if len(portfolio_returns) == 0:
            self._save_empty_placeholder(save_dir, strategy_name)
            return
        
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        metrics = self.compute_portfolio_metrics(portfolio_returns, portfolio_weights)
        
        # 1. Cumulative Returns Plot
        self._plot_cumulative_returns(
            portfolio_returns, benchmark_returns, benchmark_name, 
            regime_labels, strategy_name, save_dir
        )
        
        # 2. Drawdown Plot
        self._plot_drawdown(
            portfolio_returns, benchmark_returns, benchmark_name, save_dir
        )
        
        # 3. Asset Allocation Timeline
        self._plot_allocation_timeline(portfolio_weights, save_dir)
        
        # 4. Rolling Sharpe Ratio
        self._plot_rolling_sharpe(
            portfolio_returns, benchmark_returns, benchmark_name, save_dir
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
    
    def _plot_cumulative_returns(self, returns, benchmark, bench_name, regimes, strategy, save_dir):
        """Plot cumulative wealth with regime shading."""
        fig, ax = plt.subplots(figsize=(14, 7))
        
        cumulative = (1 + returns).cumprod()
        ax.plot(cumulative.index, cumulative.values, color=COLORS['primary'], 
               linewidth=2.5, label=strategy)
        
        if benchmark is not None:
            # FIXED: Properly align and handle missing data
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
        ax.legend(loc='upper left', frameon=True)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        
        plt.tight_layout()
        plt.savefig(f'{save_dir}/cumulative_returns.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_drawdown(self, returns, benchmark, bench_name, save_dir):
        """Plot drawdown analysis - FIXED for benchmark alignment."""
        fig, ax = plt.subplots(figsize=(14, 5))
        
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max * 100
        
        ax.fill_between(drawdown.index, drawdown.values, 0, color=COLORS['danger'], alpha=0.4)
        ax.plot(drawdown.index, drawdown.values, color=COLORS['danger'], 
               linewidth=1.5, label='Strategy')
        
        # FIXED: Benchmark drawdown with proper alignment
        if benchmark is not None:
            common_idx = returns.index.intersection(benchmark.index)
            if len(common_idx) > 100:  # Need sufficient overlap
                bench_aligned = benchmark.loc[common_idx]
                bench_cum = (1 + bench_aligned).cumprod()
                bench_running_max = bench_cum.cummax()
                bench_dd = (bench_cum - bench_running_max) / bench_running_max * 100
                ax.plot(bench_dd.index, bench_dd.values, color=COLORS['neutral'],
                       linewidth=1.5, linestyle='--', alpha=0.7, label=bench_name)
        
        mdd_idx = drawdown.idxmin()
        mdd_val = drawdown.min()
        ax.scatter([mdd_idx], [mdd_val], color=COLORS['danger'], s=100, zorder=5, marker='v')
        ax.annotate(f'Max DD: {mdd_val:.1f}%', xy=(mdd_idx, mdd_val),
                   xytext=(20, -20), textcoords='offset points', fontsize=9)
        
        ax.set_title('Drawdown Analysis', fontsize=13, fontweight='bold')
        ax.set_ylabel('Drawdown (%)')
        ax.legend(loc='lower left')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(f'{save_dir}/drawdown.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_allocation_timeline(self, weights, save_dir):
        """Plot asset allocation over time as stacked area."""
        fig, ax = plt.subplots(figsize=(14, 6))
        
        asset_cols = [c for c in weights.columns if c not in ['rf_weight', 'date']]
        if len(asset_cols) == 0:
            ax.text(0.5, 0.5, 'No allocation data', ha='center', va='center')
            plt.savefig(f'{save_dir}/allocation_timeline.png', dpi=150)
            plt.close()
            return
        
        # Resample to weekly for cleaner visualization
        weights_weekly = weights[asset_cols].resample('W').mean()
        
        # Add risk-free
        if 'rf_weight' in weights.columns:
            rf_weekly = weights['rf_weight'].resample('W').mean()
            weights_weekly['Risk-Free'] = rf_weekly
        
        # Create stacked area
        colors = plt.cm.Set3(np.linspace(0, 1, len(weights_weekly.columns)))
        ax.stackplot(weights_weekly.index, weights_weekly.values.T, 
                    labels=weights_weekly.columns, colors=colors, alpha=0.8)
        
        ax.set_title('Asset Allocation Over Time', fontsize=13, fontweight='bold')
        ax.set_ylabel('Weight')
        ax.set_ylim(0, 1.1)
        ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        
        plt.tight_layout()
        plt.savefig(f'{save_dir}/allocation_timeline.png', dpi=150, bbox_inches='tight')
        plt.close()
    
    def _plot_rolling_sharpe(self, returns, benchmark, bench_name, save_dir):
        """Plot rolling Sharpe - FIXED for reasonable values."""
        fig, ax = plt.subplots(figsize=(14, 5))
        window = min(252, len(returns) // 3)
        
        if len(returns) < window:
            ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center')
            plt.savefig(f'{save_dir}/rolling_sharpe.png', dpi=150)
            plt.close()
            return
        
        rolling_mean = returns.rolling(window=window, min_periods=window//2).mean()
        rolling_std = returns.rolling(window=window, min_periods=window//2).std()
        # FIXED: Clip extreme values
        rolling_sharpe = ((rolling_mean / rolling_std) * np.sqrt(252)).clip(-5, 5)
        
        ax.plot(rolling_sharpe.index, rolling_sharpe.values, color=COLORS['primary'], 
               linewidth=2, label='Strategy')
        
        if benchmark is not None:
            common_idx = returns.index.intersection(benchmark.index)
            if len(common_idx) > window:
                bench_aligned = benchmark.loc[common_idx]
                bench_mean = bench_aligned.rolling(window, min_periods=window//2).mean()
                bench_std = bench_aligned.rolling(window, min_periods=window//2).std()
                # FIXED: Clip extreme values
                bench_sharpe = ((bench_mean / bench_std) * np.sqrt(252)).clip(-5, 5)
                ax.plot(bench_sharpe.index, bench_sharpe.values, color=COLORS['neutral'],
                       linewidth=1.5, linestyle='--', alpha=0.7, label=bench_name)
        
        ax.axhline(1.0, color=COLORS['success'], linestyle=':', alpha=0.7, label='Good (1.0)')
        ax.axhline(0, color=COLORS['neutral'], linestyle='-', alpha=0.3)
        
        ax.set_title(f'Rolling {window}-Day Sharpe Ratio', fontsize=13, fontweight='bold')
        ax.set_ylabel('Sharpe Ratio')
        ax.set_ylim(-5, 5)  # Reasonable range
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        
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
        
        if len(pivot) == 0:
            ax.text(0.5, 0.5, 'Insufficient data', ha='center', va='center')
            plt.savefig(f'{save_dir}/monthly_heatmap.png', dpi=150)
            plt.close()
            return
        
        cmap = sns.diverging_palette(10, 130, as_cmap=True)
        vmax = max(abs(pivot.min().min()), abs(pivot.max().max()), 5)
        
        sns.heatmap(pivot, annot=True, fmt='.1f', cmap=cmap, center=0,
                   vmin=-vmax, vmax=vmax, cbar_kws={'label': 'Return (%)'},
                   ax=ax, linewidths=0.5, annot_kws={'size': 8})
        
        ax.set_title('Monthly Returns (%)', fontsize=13, fontweight='bold')
        ax.set_xticklabels(['J','F','M','A','M','J','J','A','S','O','N','D'])
        
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
    
    def _plot_allocation_pie(self, weights, save_dir):
        """Plot average allocation pie chart."""
        fig, ax = plt.subplots(figsize=(10, 8))
        
        asset_cols = [c for c in weights.columns if c != 'rf_weight']
        if len(asset_cols) == 0:
            ax.text(0.5, 0.5, 'No allocation data', ha='center', va='center')
            plt.savefig(f'{save_dir}/allocation_pie.png', dpi=150)
            plt.close()
            return
        
        avg_weights = weights[asset_cols].mean()
        avg_rf = weights['rf_weight'].mean() if 'rf_weight' in weights.columns else 0
        
        # Combine small allocations
        threshold = 0.02
        large = avg_weights[avg_weights >= threshold]
        small_sum = avg_weights[avg_weights < threshold].sum()
        
        if small_sum > 0:
            large['Other'] = small_sum
        if avg_rf > threshold:
            large['Risk-Free'] = avg_rf
        
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
        ax.legend(wedges, large.index, loc='center left', bbox_to_anchor=(1, 0.5))
        
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
