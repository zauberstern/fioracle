"""
Performance evaluation and visualization.

Provides:
- Performance metrics (Sharpe, Sortino, Max DD, Calmar, etc.)
- Hyperparameter tuning via cross-validation
- Essential visualizations (4 clean charts)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Tuple, Optional, List
import warnings

warnings.filterwarnings('ignore')


class Evaluator:
    """
    Complete evaluation suite for regime-based strategies.
    
    - Performance metrics (Sharpe, Sortino, drawdowns, etc.)
    - Lambda tuning with cross-validation
    - Clean visualizations
    """
    
    def __init__(self, annualization_factor: int = 252):
        """
        Initialize Evaluator.
        
        Args:
            annualization_factor: 252 for daily, 12 for monthly
        """
        self.annualization_factor = annualization_factor
    
    def compute_metrics(
        self,
        returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        risk_free_rate: float = 0.0
    ) -> Dict[str, float]:
        """
        Compute all performance metrics.
        
        Returns dict with: total_return, sharpe, sortino, max_drawdown,
        calmar, win_rate, skewness, kurtosis, and benchmark comparisons.
        """
        metrics = {}
        
        # Basic statistics
        metrics['total_return'] = (1 + returns).prod() - 1
        metrics['annualized_return'] = (1 + metrics['total_return']) ** (self.annualization_factor / len(returns)) - 1
        metrics['volatility'] = returns.std() * np.sqrt(self.annualization_factor)
        
        # Sharpe ratio
        excess = returns - risk_free_rate
        metrics['sharpe'] = (excess.mean() / excess.std() * np.sqrt(self.annualization_factor)) if excess.std() > 0 else 0.0
        
        # Sortino ratio
        downside = excess[excess < 0]
        downside_std = downside.std() if len(downside) > 0 else 0.0
        metrics['sortino'] = (excess.mean() / downside_std * np.sqrt(self.annualization_factor)) if downside_std > 0 else 0.0
        
        # Max drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        metrics['max_drawdown'] = drawdown.min()
        
        # Calmar ratio
        metrics['calmar'] = metrics['annualized_return'] / abs(metrics['max_drawdown']) if metrics['max_drawdown'] != 0 else 0.0
        
        # Win rate
        metrics['win_rate'] = (returns > 0).sum() / len(returns)
        
        # Skewness and kurtosis
        metrics['skewness'] = returns.skew()
        metrics['kurtosis'] = returns.kurtosis()
        
        # Benchmark comparison
        if benchmark_returns is not None:
            aligned_bench = benchmark_returns.reindex(returns.index)
            bench_cumulative = (1 + aligned_bench).prod() - 1
            metrics['excess_return'] = metrics['total_return'] - bench_cumulative
            
            # Tracking error
            tracking_diff = returns - aligned_bench
            metrics['tracking_error'] = tracking_diff.std() * np.sqrt(self.annualization_factor)
            
            # Information ratio
            metrics['information_ratio'] = (tracking_diff.mean() / tracking_diff.std() * np.sqrt(self.annualization_factor)) if tracking_diff.std() > 0 else 0.0
        
        return metrics
    
    def tune_lambda_fast(
        self,
        asset_features: pd.DataFrame,
        asset_returns: pd.Series,
        lambda_candidates: List[float] = [0.1, 1.0, 3.0, 5.0, 7.0, 10.0, 15.0],
        n_splits: int = 5
    ) -> Tuple[float, pd.DataFrame]:
        """
        Optimize lambda using time-series cross-validation.
        
        Tests each lambda value, selects the one with best average Sharpe.
        
        Returns: (optimal_lambda, results_dataframe)
        """
        from hmmlearn import hmm
        from sklearn.model_selection import TimeSeriesSplit
        
        # Align data
        common_idx = asset_features.index.intersection(asset_returns.index)
        features = asset_features.loc[common_idx]
        returns = asset_returns.loc[common_idx]
        
        results = []
        tscv = TimeSeriesSplit(n_splits=n_splits)
        
        for lambda_val in lambda_candidates:
            fold_sharpes = []
            
            for train_idx, test_idx in tscv.split(features):
                # Train
                train_features = features.iloc[train_idx]
                train_returns = returns.iloc[train_idx]
                
                # Fit HMM
                self_prob = 0.5 + 0.49 * (lambda_val / 100.0)
                other_prob = 1.0 - self_prob
                
                model = hmm.GaussianHMM(
                    n_components=2,
                    covariance_type='diag',
                    n_iter=100,
                    random_state=42,
                    init_params='mc',
                    params='stmc'
                )
                
                model.transmat_ = np.array([[self_prob, other_prob], [other_prob, self_prob]])
                model.startprob_ = np.array([0.5, 0.5])
                
                X_norm = (train_features.values - train_features.values.mean(axis=0)) / (train_features.values.std(axis=0) + 1e-8)
                
                try:
                    model.fit(X_norm)
                    
                    # Test
                    test_features = features.iloc[test_idx]
                    test_returns = returns.iloc[test_idx]
                    
                    X_test_norm = (test_features.values - train_features.values.mean(axis=0)) / (train_features.values.std(axis=0) + 1e-8)
                    states = model.predict(X_test_norm)
                    
                    # Assign bull/bear labels
                    state_returns = {}
                    for s in [0, 1]:
                        mask = (states == s)
                        state_returns[s] = test_returns.values[mask].sum()
                    
                    bearish_state = min(state_returns, key=state_returns.get)
                    regimes = pd.Series(states, index=test_features.index)
                    if bearish_state == 0:
                        regimes = 1 - regimes
                    
                    # Strategy returns: 100% asset when bull, 0% when bear
                    strategy_rets = test_returns.copy()
                    strategy_rets[regimes == 1] = 0.0
                    
                    # Sharpe
                    sharpe = (strategy_rets.mean() / strategy_rets.std() * np.sqrt(self.annualization_factor)) if strategy_rets.std() > 0 else 0.0
                    fold_sharpes.append(sharpe)
                
                except:
                    fold_sharpes.append(0.0)
            
            avg_sharpe = np.mean(fold_sharpes)
            results.append({
                'lambda': lambda_val,
                'avg_sharpe': avg_sharpe,
                'std_sharpe': np.std(fold_sharpes)
            })
        
        results_df = pd.DataFrame(results).sort_values('avg_sharpe', ascending=False)
        optimal_lambda = results_df.iloc[0]['lambda']
        
        return optimal_lambda, results_df
    
    def plot_essential(
        self,
        portfolio_returns: pd.Series,
        portfolio_weights: pd.DataFrame,
        benchmark_returns: Optional[pd.Series] = None,
        regime_labels: Optional[pd.Series] = None,
        save_dir: Optional[str] = None
    ):
        """
        Generate 4 essential charts:
        
        1. Cumulative returns vs benchmark
        2. Drawdown timeline
        3. Weight allocation over time
        4. Monthly returns heatmap (gradient-only, clean)
        """
        sns.set_style('whitegrid')
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. Cumulative Returns
        ax = axes[0, 0]
        cumulative = (1 + portfolio_returns).cumprod()
        ax.plot(cumulative.index, cumulative.values, label='Strategy', linewidth=2, color='#2E86AB')
        
        if benchmark_returns is not None:
            bench_aligned = benchmark_returns.reindex(portfolio_returns.index)
            bench_cumulative = (1 + bench_aligned).cumprod()
            ax.plot(bench_cumulative.index, bench_cumulative.values, label='Benchmark', linewidth=2, color='#A23B72', alpha=0.7)
        
        # Shade recession/regime periods
        if regime_labels is not None:
            regime_aligned = regime_labels.reindex(portfolio_returns.index)
            bear_periods = regime_aligned == 1
            if bear_periods.any():
                ax.fill_between(portfolio_returns.index, 0, cumulative.max()*1.1, 
                               where=bear_periods, alpha=0.1, color='red', label='Bear Regime')
        
        ax.set_title('Cumulative Returns', fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Return')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # 2. Drawdown
        ax = axes[0, 1]
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max * 100
        ax.fill_between(drawdown.index, drawdown.values, 0, color='#E63946', alpha=0.6)
        ax.plot(drawdown.index, drawdown.values, color='#C1121F', linewidth=1.5)
        ax.set_title('Drawdown', fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Drawdown (%)')
        ax.grid(True, alpha=0.3)
        
        # 3. Weight Allocation
        ax = axes[1, 0]
        asset_cols = [c for c in portfolio_weights.columns if c != 'rf_weight']
        if asset_cols:
            portfolio_weights[asset_cols].plot(ax=ax, kind='area', stacked=True, alpha=0.7)
            ax.set_title('Portfolio Weights Over Time', fontsize=14, fontweight='bold')
            ax.set_xlabel('Date')
            ax.set_ylabel('Weight')
            ax.set_ylim(0, 1.05)
            ax.legend(loc='upper left', bbox_to_anchor=(1.0, 1.0), frameon=True)
            ax.grid(True, alpha=0.3)
        
        # 4. Monthly Returns Heatmap (gradient-only, no annotations for clarity)
        ax = axes[1, 1]
        monthly_returns = portfolio_returns.resample('M').apply(lambda x: (1 + x).prod() - 1) * 100
        monthly_pivot = monthly_returns.groupby([monthly_returns.index.year, monthly_returns.index.month]).first().unstack()
        
        if len(monthly_pivot) > 0:
            # Use gradient without annotations for cleaner visualization
            sns.heatmap(monthly_pivot, annot=False, cmap='RdYlGn', center=0, 
                       cbar_kws={'label': 'Return (%)'}, ax=ax, linewidths=0.1,
                       vmin=-10, vmax=10)  # Cap range for better color contrast
            ax.set_title('Monthly Returns Heatmap', fontsize=14, fontweight='bold')
            ax.set_xlabel('Month')
            ax.set_ylabel('Year')
            ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
        
        plt.tight_layout()
        
        if save_dir:
            import os
            os.makedirs(save_dir, exist_ok=True)
            plt.savefig(f'{save_dir}/essential_plots.png', dpi=150, bbox_inches='tight')
            print(f"✓ Saved plots to {save_dir}/essential_plots.png")
        
        plt.show()
    
    def evaluate(
        self,
        portfolio_returns: pd.Series,
        portfolio_weights: pd.DataFrame,
        benchmark_returns: Optional[pd.Series] = None,
        regime_labels: Optional[pd.Series] = None,
        plot: bool = True,
        save_dir: Optional[str] = None,
        verbose: bool = True
    ) -> Dict:
        """
        Complete evaluation: metrics + plots.
        
        Args:
            portfolio_returns: Strategy returns
            portfolio_weights: Weights DataFrame
            benchmark_returns: Benchmark returns (optional)
            regime_labels: Regime labels (optional)
            plot: Whether to generate plots
            save_dir: Directory to save plots
            verbose: Print metrics
            
        Returns:
            Dict of metrics
        """
        # Compute metrics
        metrics = self.compute_metrics(portfolio_returns, benchmark_returns)
        
        # Add turnover metrics
        asset_cols = [c for c in portfolio_weights.columns if c != 'rf_weight']
        if asset_cols and len(portfolio_weights) > 1:
            weight_changes = portfolio_weights[asset_cols].diff().abs().sum(axis=1)
            metrics['avg_turnover'] = weight_changes.mean()
            metrics['total_turnover'] = weight_changes.sum()
        
        if verbose:
            print("="*60)
            print("Performance Metrics")
            print("="*60)
            print(f"Total Return:      {metrics['total_return']*100:>8.2f}%")
            print(f"Annual Return:     {metrics['annualized_return']*100:>8.2f}%")
            print(f"Volatility:        {metrics['volatility']*100:>8.2f}%")
            print(f"Sharpe Ratio:      {metrics['sharpe']:>8.2f}")
            print(f"Sortino Ratio:     {metrics['sortino']:>8.2f}")
            print(f"Max Drawdown:      {metrics['max_drawdown']*100:>8.2f}%")
            print(f"Calmar Ratio:      {metrics['calmar']:>8.2f}")
            print(f"Win Rate:          {metrics['win_rate']*100:>8.2f}%")
            
            if 'excess_return' in metrics:
                print(f"\nBenchmark Comparison:")
                print(f"Excess Return:     {metrics['excess_return']*100:>8.2f}%")
                print(f"Information Ratio: {metrics['information_ratio']:>8.2f}")
            
            if 'avg_turnover' in metrics:
                print(f"\nTrading Activity:")
                print(f"Avg Turnover:      {metrics['avg_turnover']*100:>8.2f}%")
            
            print("="*60 + "\n")
        
        # Generate plots
        if plot:
            self.plot_essential(
                portfolio_returns,
                portfolio_weights,
                benchmark_returns,
                regime_labels,
                save_dir
            )
        
        return metrics


# Backward compatibility
def compute_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Compute Sharpe ratio (backward compatible)."""
    evaluator = Evaluator()
    metrics = evaluator.compute_metrics(returns, risk_free_rate=risk_free_rate)
    return metrics['sharpe']


def compute_all_metrics(
    portfolio_returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None
) -> Dict[str, float]:
    """Compute all metrics (backward compatible)."""
    evaluator = Evaluator()
    return evaluator.compute_metrics(portfolio_returns, benchmark_returns)


def evaluate_strategy_performance(
    portfolio_returns: pd.Series,
    portfolio_weights: pd.DataFrame,
    benchmark_returns: Optional[pd.Series] = None
) -> Dict:
    """Evaluate strategy performance (backward compatible)."""
    evaluator = Evaluator()
    return evaluator.evaluate(
        portfolio_returns,
        portfolio_weights,
        benchmark_returns,
        plot=False,
        verbose=True
    )
