"""
Portfolio optimization engine.

Combines:
1. RA-FIAP: Regime-conditioned expected returns and covariance
2. RA-FIPO: Constrained portfolio weight optimization

Features capital preservation, transaction costs, and daily rebalancing.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, Tuple, Optional


class PortfolioEngine:
    """
    Complete portfolio system: RA-FIAP + RA-FIPO.
    
    1. RA-FIAP: Generate regime-based μ and Σ
    2. RA-FIPO: Optimize weights with constraints
    """
    
    def __init__(
        self,
        gamma_risk: float = 10.0,
        gamma_trade: float = 1.0,
        transaction_cost: float = 0.0005,
        min_bullish_assets: int = 2,
        max_weight: float = 0.40,
        ewmc_decay: float = 0.94,
        lookback_years: int = 11
    ):
        """
        Initialize PortfolioEngine.
        
        Args:
            gamma_risk: Risk aversion parameter (higher = more conservative)
            gamma_trade: Trade aversion (controls turnover)
            transaction_cost: One-way transaction cost (decimal)
            min_bullish_assets: Min bullish assets to proceed (else 100% cash)
            max_weight: Maximum weight per asset
            ewmc_decay: Exponential decay for covariance
            lookback_years: Years of history for regime-conditional estimation
        """
        # RA-FIPO parameters
        self.gamma_risk = gamma_risk
        self.gamma_trade = gamma_trade
        self.transaction_cost = transaction_cost
        self.min_bullish_assets = min_bullish_assets
        self.max_weight = max_weight
        
        # RA-FIAP parameters
        self.ewmc_decay = ewmc_decay
        self.lookback_days = lookback_years * 252
        
        # State tracking
        self.w_prev = None  # Previous weights for turnover
    
    def generate_mu_sigma(
        self,
        date: pd.Timestamp,
        regime_forecasts: np.ndarray,
        returns_df: pd.DataFrame,
        regimes_df: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate regime-conditioned expected returns (μ) and covariance (Σ).
        
        RA-FIAP methodology: filters historical data by regime to build
        regime-specific return distributions.
        
        Returns: (expected_returns, covariance_matrix)
        """
        n_assets = len(regime_forecasts)
        date_idx = returns_df.index.get_loc(date)
        start_idx = max(0, date_idx - self.lookback_days)
        
        # Expected returns (μ)
        expected_returns = np.zeros(n_assets)
        assets = returns_df.columns
        
        for j, asset in enumerate(assets):
            regime = regime_forecasts[j]
            
            # Historical returns and regimes
            hist_returns = returns_df[asset].iloc[start_idx:date_idx].values
            hist_regimes = regimes_df[asset].iloc[start_idx:date_idx].values
            
            # Filter by predicted regime
            regime_mask = (hist_regimes == regime)
            
            if np.sum(regime_mask) >= 20:
                mu = np.mean(hist_returns[regime_mask])
            else:
                mu = np.mean(hist_returns)
            
            # Apply constraints
            if regime == 1:  # Bearish
                expected_returns[j] = min(mu, -0.001)  # Cap at -10 bps
            else:  # Bullish
                expected_returns[j] = max(mu, 0.0001)  # Min 1 bp
        
        # Covariance matrix (Σ)
        hist_returns_all = returns_df.iloc[start_idx:date_idx].values
        covariance_matrix = self._compute_ewmc(hist_returns_all)
        
        return expected_returns, covariance_matrix
    
    def _compute_ewmc(self, returns: np.ndarray) -> np.ndarray:
        """
        Exponentially Weighted Moving Covariance (more weight on recent data).
        
        Returns: Covariance matrix with regularization for stability
        """
        n_samples, n_assets = returns.shape
        
        # Exponential weights (more weight on recent data)
        indices = np.arange(n_samples)
        weights = self.ewmc_decay ** (n_samples - 1 - indices)
        weights = weights / weights.sum()
        
        # Weighted mean
        weighted_mean = np.sum(returns * weights[:, np.newaxis], axis=0)
        
        # Weighted covariance
        centered_returns = returns - weighted_mean
        cov_matrix = np.zeros((n_assets, n_assets))
        
        for i in range(n_samples):
            outer = np.outer(centered_returns[i], centered_returns[i])
            cov_matrix += weights[i] * outer
        
        # Regularization for numerical stability
        cov_matrix += np.eye(n_assets) * 1e-8
        
        return cov_matrix
    
    def optimize_daily(
        self,
        regime_forecasts: np.ndarray,
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        asset_names: Optional[list] = None
    ) -> Tuple[np.ndarray, Dict]:
        """
        Optimize portfolio weights for single day (RA-FIPO).
        
        Args:
            regime_forecasts: Binary forecasts (0=Bull, 1=Bear)
            expected_returns: Regime-conditioned μ
            covariance_matrix: Regime-conditioned Σ
            asset_names: Asset names (optional)
            
        Returns:
            Tuple of (optimal_weights, diagnostics)
        """
        n_assets = len(regime_forecasts)
        
        if asset_names is None:
            asset_names = [f"Asset_{i}" for i in range(n_assets)]
        
        if self.w_prev is None:
            self.w_prev = np.zeros(n_assets)
        
        # Count bullish assets
        bullish_mask = (regime_forecasts == 0)
        n_bullish = np.sum(bullish_mask)
        
        diagnostics = {
            'n_bullish': n_bullish,
            'n_bearish': n_assets - n_bullish,
            'bullish_assets': [asset_names[i] for i in range(n_assets) if bullish_mask[i]]
        }
        
        # Capital preservation rule
        if n_bullish < self.min_bullish_assets:
            weights = np.zeros(n_assets)
            diagnostics['status'] = 'CASH'
            diagnostics['reason'] = f'Only {n_bullish} bullish assets (< {self.min_bullish_assets})'
            diagnostics['rf_weight'] = 1.0
            diagnostics['turnover'] = np.sum(np.abs(weights - self.w_prev))
            
            self.w_prev = weights
            return weights, diagnostics
        
        # Adjust returns: bearish → 0, bullish → min 0.1 bps
        mu_adj = expected_returns.copy()
        mu_adj[~bullish_mask] = 0.0
        mu_adj[bullish_mask] = np.maximum(mu_adj[bullish_mask], 0.001)
        
        # Objective function
        def objective(w):
            ret = np.dot(w, mu_adj)
            var = np.dot(w, np.dot(covariance_matrix, w))
            turnover = self.gamma_trade * self.transaction_cost * np.sum(np.abs(w - self.w_prev))
            utility = ret - self.gamma_risk * var - turnover
            return -utility
        
        def gradient(w):
            grad_ret = mu_adj
            grad_var = 2 * self.gamma_risk * np.dot(covariance_matrix, w)
            grad_turn = self.gamma_trade * self.transaction_cost * np.sign(w - self.w_prev)
            return -(grad_ret - grad_var - grad_turn)
        
        # Constraints
        constraints = [
            {'type': 'ineq', 'fun': lambda w: 1.0 - np.sum(w)}  # sum(w) <= 1
        ]
        
        # Bounds: bullish [0, max_weight], bearish [0, 0]
        bounds = [(0.0, self.max_weight if bullish_mask[i] else 0.0) 
                  for i in range(n_assets)]
        
        # Initial guess: equal weight among bullish
        w0 = np.zeros(n_assets)
        if n_bullish > 0:
            w0[bullish_mask] = 1.0 / n_bullish
            w0[bullish_mask] = np.minimum(w0[bullish_mask], self.max_weight)
        
        # Optimize
        try:
            result = minimize(
                objective,
                w0,
                method='SLSQP',
                jac=gradient,
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000, 'ftol': 1e-9}
            )
            
            if result.success:
                weights = result.x
                diagnostics['status'] = 'SUCCESS'
            else:
                weights = w0
                diagnostics['status'] = 'FALLBACK'
                diagnostics['message'] = result.message
        
        except Exception as e:
            weights = w0
            diagnostics['status'] = 'ERROR'
            diagnostics['error'] = str(e)
        
        # Clean up numerical errors
        weights = np.maximum(weights, 0.0)
        if np.sum(weights) > 1.0:
            weights = weights / np.sum(weights)
        
        # Compute diagnostics
        rf_weight = 1.0 - np.sum(weights)
        portfolio_return = np.dot(weights, mu_adj)
        portfolio_vol = np.sqrt(np.dot(weights, np.dot(covariance_matrix, weights)))
        turnover = np.sum(np.abs(weights - self.w_prev))
        
        diagnostics['rf_weight'] = rf_weight
        diagnostics['expected_return'] = portfolio_return
        diagnostics['expected_volatility'] = portfolio_vol
        diagnostics['turnover'] = turnover
        diagnostics['transaction_cost'] = self.transaction_cost * turnover
        diagnostics['weights'] = {asset_names[i]: weights[i] for i in range(n_assets)}
        
        self.w_prev = weights.copy()
        
        return weights, diagnostics
    
    def backtest(
        self,
        returns_df: pd.DataFrame,
        regimes_df: pd.DataFrame,
        regime_forecasts_df: pd.DataFrame,
        start_date: Optional[pd.Timestamp] = None,
        end_date: Optional[pd.Timestamp] = None,
        verbose: bool = True
    ) -> Dict:
        """
        Run full backtest of RA-FIAP + RA-FIPO strategy.
        
        Args:
            returns_df: Historical returns
            regimes_df: Historical regimes
            regime_forecasts_df: Regime forecasts (from XGBoost)
            start_date: Start date (optional)
            end_date: End date (optional)
            verbose: Print progress
            
        Returns:
            Dict with:
                - portfolio_returns: Series of daily returns
                - portfolio_weights: DataFrame of weights over time
                - diagnostics: DataFrame of daily diagnostics
        """
        # Date range
        dates = returns_df.index
        if start_date:
            dates = dates[dates >= start_date]
        if end_date:
            dates = dates[dates <= end_date]
        
        # Filter to dates where we have enough history
        dates = dates[self.lookback_days:]
        
        assets = returns_df.columns
        n_assets = len(assets)
        
        # Storage
        weights_history = []
        returns_history = []
        diagnostics_history = []
        
        if verbose:
            print("="*60)
            print("Running Backtest (RA-FIAP + RA-FIPO)")
            print("="*60)
            total = len(dates)
        
        for i, date in enumerate(dates):
            if verbose and i % 252 == 0:
                print(f"  {date.strftime('%Y-%m-%d')}: {i+1}/{total} ({(i+1)/total*100:.1f}%)")
            
            # Get regime forecasts for this date
            if date not in regime_forecasts_df.index:
                continue
            
            regime_forecasts = regime_forecasts_df.loc[date].values
            
            # Generate μ and Σ
            mu, sigma = self.generate_mu_sigma(
                date, regime_forecasts, returns_df, regimes_df
            )
            
            # Optimize weights
            weights, diag = self.optimize_daily(
                regime_forecasts, mu, sigma, asset_names=assets.tolist()
            )
            
            # Record weights
            weights_history.append({
                'date': date,
                **{asset: weights[j] for j, asset in enumerate(assets)},
                'rf_weight': diag['rf_weight']
            })
            
            # Compute realized return (next day)
            next_date_idx = returns_df.index.get_loc(date) + 1
            if next_date_idx < len(returns_df):
                next_returns = returns_df.iloc[next_date_idx].values
                portfolio_return = np.dot(weights, next_returns)
                returns_history.append({
                    'date': returns_df.index[next_date_idx],
                    'return': portfolio_return
                })
            
            # Record diagnostics
            diagnostics_history.append({
                'date': date,
                **{k: v for k, v in diag.items() if k != 'weights'}
            })
        
        if verbose:
            print("="*60 + "\n")
        
        # Convert to DataFrames
        weights_df = pd.DataFrame(weights_history).set_index('date')
        returns_series = pd.DataFrame(returns_history).set_index('date')['return']
        diagnostics_df = pd.DataFrame(diagnostics_history).set_index('date')
        
        return {
            'portfolio_returns': returns_series,
            'portfolio_weights': weights_df,
            'diagnostics': diagnostics_df
        }
    
    def reset(self):
        """Reset optimizer state."""
        self.w_prev = None


# Backward compatibility functions
def optimize_portfolio_ra_fipo(
    regime_forecasts: np.ndarray,
    expected_returns: np.ndarray,
    covariance_matrix: np.ndarray,
    gamma_risk: float = 10.0,
    gamma_trade: float = 1.0,
    min_bullish_assets: int = 2,
    max_weight: float = 0.40
) -> Tuple[np.ndarray, Dict]:
    """
    Optimize portfolio using RA-FIPO (backward compatible).
    
    Args:
        regime_forecasts: Binary forecasts (0=Bull, 1=Bear)
        expected_returns: Expected returns
        covariance_matrix: Covariance matrix
        gamma_risk: Risk aversion
        gamma_trade: Trade aversion
        min_bullish_assets: Min bullish to proceed
        max_weight: Max weight per asset
        
    Returns:
        Tuple of (weights, diagnostics)
    """
    engine = PortfolioEngine(
        gamma_risk=gamma_risk,
        gamma_trade=gamma_trade,
        min_bullish_assets=min_bullish_assets,
        max_weight=max_weight
    )
    
    return engine.optimize_daily(
        regime_forecasts,
        expected_returns,
        covariance_matrix
    )
