"""
Robustness grid over gamma parameters.

Evaluates portfolio performance across a grid of risk/trade aversion values.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, Optional
import json
from itertools import product


def evaluate_gamma_grid(
    config: dict,
    returns_df: pd.DataFrame,
    regime_forecasts_df: pd.DataFrame,
    macro_features: pd.DataFrame,
    regimes_df: pd.DataFrame,
    split_name: str,
    output_dir: Path,
    risk_free_rate: pd.Series
) -> pd.DataFrame:
    """
    Evaluate portfolio performance over grid of (gamma_risk, gamma_trade).
    
    Returns DataFrame indexed by (gamma_risk, gamma_trade) with key metrics.
    """
    from core.portfolio import PortfolioEngine
    from core.evaluation import Evaluator
    
    grid_cfg = config.get('portfolio', {}).get('robustness_grid', {})
    if not grid_cfg.get('enabled', False):
        return pd.DataFrame()
    
    gamma_risk_values = grid_cfg.get('gamma_risk_values', [7.5, 10.0, 12.5, 15.0])
    gamma_trade_values = grid_cfg.get('gamma_trade_values', [0.5, 1.0, 2.0])
    
    output_path = output_dir / 'robustness_grid' / split_name
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    total = len(gamma_risk_values) * len(gamma_trade_values)
    print(f"Running robustness grid: {total} combinations...")
    
    for i, (g_risk, g_trade) in enumerate(product(gamma_risk_values, gamma_trade_values)):
        print(f"  [{i+1}/{total}] γ_risk={g_risk}, γ_trade={g_trade}")
        
        try:
            # Create portfolio engine with these parameters
            engine = PortfolioEngine(
                gamma_risk=g_risk,
                gamma_trade=g_trade,
                transaction_cost=config['portfolio']['transaction_cost'],
                min_bullish_assets=config['portfolio']['min_bullish_assets'],
                max_weight=config['portfolio']['max_weight'],
                covariance_halflife=config['portfolio']['covariance_halflife'],
                lookback_years=11,
                bearish_return_cap=config['portfolio']['bearish_return_cap'],
                bullish_return_minvar=config['portfolio']['bullish_return_minvar'],
                strategy='MV',  # Use MV for robustness testing
                config=config
            )
            
            # Run backtest (simplified)
            backtest_results = _run_simplified_backtest(
                engine,
                returns_df,
                regimes_df,
                regime_forecasts_df,
                risk_free_rate
            )
            
            if backtest_results is None:
                continue
            
            portfolio_returns = backtest_results['portfolio_returns']
            
            # Compute metrics
            if len(portfolio_returns) < 50:
                continue
            
            ann_return = portfolio_returns.mean() * 252
            ann_vol = portfolio_returns.std() * np.sqrt(252)
            sharpe = ann_return / (ann_vol + 1e-10)
            
            cumulative = (1 + portfolio_returns).cumprod()
            running_max = cumulative.cummax()
            drawdown = (cumulative - running_max) / running_max
            max_dd = drawdown.min()
            
            calmar = ann_return / (-max_dd + 1e-10) if max_dd < 0 else 0
            
            results.append({
                'gamma_risk': g_risk,
                'gamma_trade': g_trade,
                'sharpe': sharpe,
                'max_drawdown': max_dd,
                'calmar': calmar,
                'ann_return': ann_return,
                'ann_vol': ann_vol,
                'n_days': len(portfolio_returns)
            })
            
        except Exception as e:
            print(f"    Error: {e}")
            continue
    
    if len(results) == 0:
        return pd.DataFrame()
    
    results_df = pd.DataFrame(results)
    
    # Save results
    results_df.to_csv(output_path / 'gamma_grid_results.csv', index=False)
    
    # Plot heatmaps
    _plot_gamma_heatmaps(results_df, output_path)
    
    return results_df


def _run_simplified_backtest(
    engine,
    returns_df: pd.DataFrame,
    regimes_df: pd.DataFrame,
    regime_forecasts_df: pd.DataFrame,
    risk_free_rate: pd.Series
) -> Optional[Dict]:
    """Run simplified backtest for robustness grid."""
    
    # Use regime forecasts if available, otherwise regimes
    if regime_forecasts_df is not None and not regime_forecasts_df.empty:
        forecast_df = regime_forecasts_df
    else:
        forecast_df = regimes_df
    
    common_idx = returns_df.index.intersection(forecast_df.index)
    if len(common_idx) < 100:
        return None
    
    portfolio_returns = []
    
    # Sample every 5th day for speed
    sample_dates = common_idx[::5]
    
    for date in sample_dates:
        try:
            available_assets = [c for c in returns_df.columns 
                              if c in forecast_df.columns 
                              and not returns_df.loc[:date, c].isna().all()]
            
            if len(available_assets) < 3:
                continue
            
            # Get regime forecasts
            forecasts = forecast_df.loc[date, available_assets].values
            forecasts = np.nan_to_num(forecasts, nan=0)
            
            # Generate mu and sigma
            mu, sigma = engine.generate_mu_sigma(
                date=date,
                regime_forecasts=forecasts,
                returns_df=returns_df.loc[:date],
                regimes_df=regimes_df.loc[:date] if regimes_df is not None else pd.DataFrame(),
                available_assets=available_assets
            )
            
            # Optimize
            weights, _ = engine.optimize_daily(
                regime_forecasts=forecasts,
                expected_returns=mu,
                covariance_matrix=sigma,
                asset_names=available_assets
            )
            
            # Compute return
            if date in returns_df.index:
                asset_rets = returns_df.loc[date, available_assets].values
                rf = risk_free_rate.loc[date] if date in risk_free_rate.index else 0.0
                
                portfolio_ret = np.dot(weights, np.nan_to_num(asset_rets, nan=0)) + (1 - weights.sum()) * rf
                portfolio_returns.append({'date': date, 'return': portfolio_ret})
                
        except Exception:
            continue
    
    if len(portfolio_returns) < 50:
        return None
    
    returns_series = pd.DataFrame(portfolio_returns).set_index('date')['return']
    
    return {
        'portfolio_returns': returns_series,
        'portfolio_weights': pd.DataFrame()  # Not tracked for speed
    }


def _plot_gamma_heatmaps(results_df: pd.DataFrame, output_path: Path):
    """Plot heatmaps for Sharpe, MDD, Calmar."""
    metrics = [
        ('sharpe', 'Sharpe Ratio', 'RdYlGn'),
        ('max_drawdown', 'Max Drawdown', 'RdYlGn_r'),
        ('calmar', 'Calmar Ratio', 'RdYlGn')
    ]
    
    for metric, title, cmap in metrics:
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Pivot for heatmap
        pivot = results_df.pivot(
            index='gamma_risk', 
            columns='gamma_trade', 
            values=metric
        )
        
        if metric == 'max_drawdown':
            pivot = pivot * 100  # Convert to %
            fmt = '.1f'
            label = 'Max Drawdown (%)'
        else:
            fmt = '.2f'
            label = title
        
        sns.heatmap(
            pivot, 
            annot=True, 
            fmt=fmt, 
            cmap=cmap,
            ax=ax,
            cbar_kws={'label': label}
        )
        
        ax.set_title(f'{title} by γ Parameters', fontsize=13, fontweight='bold')
        ax.set_xlabel('γ_trade', fontsize=11)
        ax.set_ylabel('γ_risk', fontsize=11)
        
        plt.tight_layout()
        plt.savefig(output_path / f'gamma_grid_{metric}.png', dpi=150, bbox_inches='tight')
        plt.close()

