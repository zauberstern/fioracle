"""
Portfolio optimization engine implementing enhanced Markowitz MVO.

Core Optimization (Equation 2):
maximize w^T μ - γ_risk w^T Σ w - γ_trade × a ||w - w_pre||_1

Constraints:
- Long-only: 0 ≤ w ≤ 0.40 (40% max per asset)
- Leverage: 1^T w ≤ 1 (no short risk-free)
- Risk-free: w_rf = 1 - 1^T w

Risk Concentration Constraint:
- If ≤3 assets are bullish → 100% to risk-free asset

Strategies:
- MinVar (JM-XGB): μ_j = 10bp if bullish, 0 if bearish
- MV (JM-XGB): Regime-conditional μ from 11-year historical window
- EW (JM-XGB): Equal weights among bullish assets (daily rebalanced)

Parameters:
- γ_risk = 10.0, γ_trade = 1.0
- Transaction cost a = 0.0005 (5 bps)
- Covariance: EWM with 252-day halflife
- Bearish return cap: -10 bps
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, Tuple, Optional, List
import warnings


class PortfolioEngine:
    """
    Complete portfolio system implementing RA-FIAP + RA-FIPO.
    
    1. RA-FIAP: Generate regime-based μ and Σ
    2. RA-FIPO: Optimize weights with constraints
    """
    
    def __init__(
        self,
        gamma_risk: float = 10.0,
        gamma_trade: float = 1.0,
        transaction_cost: float = 0.0005,
        min_bullish_assets: int = 3,
        max_weight: float = 0.40,
        covariance_halflife: int = 252,
        lookback_years: int = 11,
        bearish_return_cap: float = -0.001,
        bullish_return_minvar: float = 0.001,
        strategy: str = 'MV'
    ):
        """
        Initialize PortfolioEngine.
        
        Args:
            gamma_risk: Risk aversion parameter (10.0 for all enhanced models)
            gamma_trade: Trade aversion (1.0 to reduce turnover)
            transaction_cost: One-way transaction cost (0.0005 = 5 bps)
            min_bullish_assets: Min bullish assets to proceed (≤3 → 100% cash)
            max_weight: Maximum weight per asset (40%)
            covariance_halflife: EWM covariance halflife in days (252)
            lookback_years: Years of history for regime-conditional estimation (11)
            bearish_return_cap: Cap on bearish return forecasts (-10 bps)
            bullish_return_minvar: Return for bullish assets in MinVar (10 bps)
            strategy: 'MinVar', 'MV', or 'EW'
        """
        self.gamma_risk = gamma_risk
        self.gamma_trade = gamma_trade
        self.transaction_cost = transaction_cost
        self.min_bullish_assets = min_bullish_assets
        self.max_weight = max_weight
        self.strategy = strategy
        
        self.covariance_halflife = covariance_halflife
        self.lookback_days = lookback_years * 252
        self.bearish_return_cap = bearish_return_cap
        self.bullish_return_minvar = bullish_return_minvar
        
        self.w_prev = None
    
    def generate_mu_sigma(
        self,
        date: pd.Timestamp,
        regime_forecasts: np.ndarray,
        returns_df: pd.DataFrame,
        regimes_df: pd.DataFrame,
        available_assets: List[str]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate regime-conditioned expected returns (μ) and covariance (Σ).
        
        Strategy-specific μ generation:
        - MinVar: μ_j = 10 bp if bullish, 0 if bearish
        - MV: μ_j = average return from historical periods with same regime
        - EW: Not used (equal weights)
        """
        n_assets = len(available_assets)
        
        # Get date index
        try:
            date_idx = returns_df.index.get_loc(date)
        except KeyError:
            if date < returns_df.index[0]:
                raise ValueError(f"Date {date} before data start")
            date_idx = returns_df.index.searchsorted(date) - 1
            if date_idx < 0:
                raise ValueError(f"Date {date} before data start")
        
        start_idx = max(0, date_idx - self.lookback_days)
        
        # Expected returns
        expected_returns = np.zeros(n_assets)
        
        if self.strategy == 'MinVar':
            # MinVar: μ_j = 10 bp if bullish, 0 if bearish
            for j in range(n_assets):
                if j < len(regime_forecasts):
                    regime = regime_forecasts[j]
                    expected_returns[j] = self.bullish_return_minvar if regime == 0 else 0.0
        
        elif self.strategy == 'MV':
            # MV: Regime-conditional historical average
            for j, asset in enumerate(available_assets):
                if j >= len(regime_forecasts):
                    continue
                    
                regime = regime_forecasts[j]
                hist_dates = returns_df.index[start_idx:date_idx]
                
                if asset not in returns_df.columns:
                    continue
                    
                hist_returns = returns_df.loc[hist_dates, asset].dropna()
                
                if len(hist_returns) == 0:
                    continue
                
                # Get regime-conditional returns
                if asset in regimes_df.columns:
                    hist_regimes = regimes_df[asset].reindex(hist_returns.index)
                    valid_mask = ~(hist_returns.isna() | hist_regimes.isna())
                    hist_returns_valid = hist_returns[valid_mask]
                    hist_regimes_valid = hist_regimes[valid_mask]
                    
                    # Filter by predicted regime
                    regime_mask = (hist_regimes_valid == regime)
                    
                    if regime_mask.sum() >= 20:
                        mu = hist_returns_valid[regime_mask].mean()
                    else:
                        mu = hist_returns_valid.mean()
                else:
                    mu = hist_returns.mean()
                
                # Apply constraints
                if regime == 1:  # Bearish
                    expected_returns[j] = max(mu, self.bearish_return_cap)
                else:  # Bullish
                    expected_returns[j] = mu
        
        # Covariance matrix (EWM with 252-day halflife)
        hist_dates = returns_df.index[start_idx:date_idx]
        hist_returns_all = returns_df.loc[hist_dates, available_assets].values
        
        if len(hist_returns_all) == 0:
            covariance_matrix = np.eye(n_assets) * 0.01
        else:
            covariance_matrix = self._compute_ewmc(hist_returns_all)
        
        return expected_returns, covariance_matrix
    
    def _compute_ewmc(self, returns: np.ndarray) -> np.ndarray:
        """Exponentially Weighted Moving Covariance with regularization."""
        # Handle NaN values
        returns = np.nan_to_num(returns, nan=0.0)
        
        n_samples, n_assets = returns.shape
        
        if n_samples == 0:
            return np.eye(n_assets) * 0.01
        
        # Exponential weights
        indices = np.arange(n_samples)
        weights = np.exp(-np.log(2) / self.covariance_halflife * (n_samples - 1 - indices))
        weights = weights / weights.sum()
        
        # Weighted mean
        weighted_mean = np.sum(returns * weights[:, np.newaxis], axis=0)
        
        # Weighted covariance
        centered = returns - weighted_mean
        cov_matrix = np.zeros((n_assets, n_assets))
        
        for i in range(n_samples):
            outer = np.outer(centered[i], centered[i])
            cov_matrix += weights[i] * outer
        
        # Regularization
        cov_matrix += np.eye(n_assets) * 1e-6
        
        return cov_matrix
    
    def optimize_daily(
        self,
        regime_forecasts: np.ndarray,
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        asset_names: List[str]
    ) -> Tuple[np.ndarray, Dict]:
        """
        Optimize portfolio weights for single day (RA-FIPO).
        
        Implements Equation 2 with constraints 3 & 4.
        """
        n_assets = len(asset_names)
        
        # Validate dimensions
        if len(regime_forecasts) != n_assets:
            regime_forecasts = np.zeros(n_assets)  # Default to bullish
        if len(expected_returns) != n_assets:
            expected_returns = np.zeros(n_assets)
        if covariance_matrix.shape != (n_assets, n_assets):
            covariance_matrix = np.eye(n_assets) * 0.01
        
        # Initialize previous weights
        if self.w_prev is None or len(self.w_prev) != n_assets:
            self.w_prev = np.zeros(n_assets)
        
        # Count bullish assets
        bullish_mask = (regime_forecasts == 0)
        n_bullish = np.sum(bullish_mask)
        
        diagnostics = {
            'n_bullish': int(n_bullish),
            'n_bearish': n_assets - int(n_bullish),
            'bullish_assets': [asset_names[i] for i in range(n_assets) if bullish_mask[i]]
        }
        
        # Risk Concentration Constraint: if ≤3 bullish → 100% to risk-free
        if n_bullish <= self.min_bullish_assets:
            weights = np.zeros(n_assets)
            diagnostics['status'] = 'CASH'
            diagnostics['reason'] = f'Only {n_bullish} bullish assets (≤{self.min_bullish_assets})'
            diagnostics['rf_weight'] = 1.0
            diagnostics['turnover'] = np.sum(np.abs(weights - self.w_prev))
            
            self.w_prev = weights
            return weights, diagnostics
        
        # EW Strategy: Equal weights among bullish assets
        if self.strategy == 'EW':
            weights = np.zeros(n_assets)
            weights[bullish_mask] = 1.0 / n_bullish
            weights = np.minimum(weights, self.max_weight)
            
            # Normalize if needed
            if np.sum(weights) > 1.0:
                weights = weights / np.sum(weights)
            
            rf_weight = 1.0 - np.sum(weights)
            turnover = np.sum(np.abs(weights - self.w_prev))
            
            diagnostics['status'] = 'EW'
            diagnostics['rf_weight'] = rf_weight
            diagnostics['turnover'] = turnover
            diagnostics['transaction_cost'] = self.transaction_cost * turnover
            
            self.w_prev = weights.copy()
            return weights, diagnostics
        
        # MinVar and MV: Optimize over bullish assets only
        bullish_indices = np.where(bullish_mask)[0]
        n_bullish_assets = len(bullish_indices)
        
        # Subset matrices
        sigma_bullish = covariance_matrix[np.ix_(bullish_indices, bullish_indices)]
        mu_bullish = expected_returns[bullish_indices]
        w_prev_bullish = self.w_prev[bullish_indices]
        
        # MinVar adjustment
        if self.strategy == 'MinVar':
            mu_bullish = np.full(n_bullish_assets, self.bullish_return_minvar)
        
        # Objective function (Equation 2)
        def objective(w):
            ret = np.dot(w, mu_bullish)
            var = np.dot(w, np.dot(sigma_bullish, w))
            turnover_l1 = np.sum(np.abs(w - w_prev_bullish))
            turnover_cost = self.gamma_trade * self.transaction_cost * turnover_l1
            return -(ret - self.gamma_risk * var - turnover_cost)
        
        def gradient(w):
            grad_ret = mu_bullish
            grad_var = 2 * self.gamma_risk * np.dot(sigma_bullish, w)
            grad_turn = self.gamma_trade * self.transaction_cost * np.sign(w - w_prev_bullish)
            return -(grad_ret - grad_var - grad_turn)
        
        # Constraints
        constraints = [{'type': 'ineq', 'fun': lambda w: 1.0 - np.sum(w)}]
        
        # Bounds
        bounds = [(0.0, self.max_weight) for _ in range(n_bullish_assets)]
        
        # Initial guess
        w0 = np.full(n_bullish_assets, min(1.0 / n_bullish_assets, self.max_weight))
        
        # Optimize
        try:
            result = minimize(
                objective, w0,
                method='SLSQP',
                jac=gradient,
                bounds=bounds,
                constraints=constraints,
                options={'maxiter': 1000, 'ftol': 1e-9}
            )
            
            w_opt = result.x if result.success else w0
            diagnostics['status'] = 'SUCCESS' if result.success else 'FALLBACK'
        except Exception as e:
            w_opt = w0
            diagnostics['status'] = 'ERROR'
            diagnostics['error'] = str(e)
        
        # Map back to full space
        weights = np.zeros(n_assets)
        weights[bullish_indices] = w_opt
        
        # Enforce constraints
        weights = np.maximum(weights, 0.0)
        weights = np.minimum(weights, self.max_weight)
        if np.sum(weights) > 1.0:
            weights = weights / np.sum(weights)
        
        rf_weight = 1.0 - np.sum(weights)
        turnover = np.sum(np.abs(weights - self.w_prev))
        
        diagnostics['rf_weight'] = rf_weight
        diagnostics['expected_return'] = np.dot(weights, expected_returns)
        diagnostics['expected_volatility'] = np.sqrt(np.dot(weights, np.dot(covariance_matrix, weights)))
        diagnostics['turnover'] = turnover
        diagnostics['transaction_cost'] = self.transaction_cost * turnover
        
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
        
        Handles dynamic asset availability (assets become investable when data available).
        """
        # Date range
        dates = returns_df.index
        if start_date:
            dates = dates[dates >= start_date]
        if end_date:
            dates = dates[dates <= end_date]
        
        # Need lookback for covariance - but use minimum of lookback or available data
        min_lookback = min(self.lookback_days, len(dates) - 100)  # At least 100 days to process
        if min_lookback < 0:
            min_lookback = 0
        dates = dates[min_lookback:]
        
        all_assets = returns_df.columns.tolist()
        n_assets = len(all_assets)
        
        # Determine asset availability
        asset_availability = {}
        for asset in all_assets:
            first_valid = returns_df[asset].dropna().index
            if len(first_valid) > 0:
                asset_availability[asset] = first_valid[0]
            else:
                asset_availability[asset] = pd.Timestamp.max
        
        # Storage
        weights_history = []
        returns_history = []
        diagnostics_history = []
        
        if verbose:
            print("="*60)
            print(f"Running Backtest ({self.strategy} JM-XGB)")
            print("="*60)
            total = len(dates)
        
        for i, date in enumerate(dates):
            if verbose and i % 250 == 0:
                print(f"  {date.strftime('%Y-%m-%d')}: {i+1}/{total} ({(i+1)/total*100:.1f}%)")
            
            if date not in regime_forecasts_df.index:
                continue
            
            try:
                # Get available assets at this date
                available_assets = []
                for asset in all_assets:
                    if date >= asset_availability.get(asset, pd.Timestamp.max):
                        ret_val = returns_df.loc[date, asset]
                        if pd.notna(ret_val) and np.isfinite(ret_val):
                            available_assets.append(asset)
                
                if len(available_assets) == 0:
                    continue
                
                # Get regime forecasts for available assets
                n_available = len(available_assets)
                regime_forecasts = np.zeros(n_available, dtype=int)  # Default bullish
                
                if date in regime_forecasts_df.index:
                    raw = regime_forecasts_df.loc[date]
                    if isinstance(raw, pd.Series):
                        for idx, asset in enumerate(available_assets):
                            if asset in raw.index:
                                val = raw[asset]
                                regime_forecasts[idx] = int(val) if pd.notna(val) else 0
                
                # Generate μ and Σ
                available_returns_df = returns_df[available_assets]
                available_regimes_df = regimes_df[[c for c in available_assets if c in regimes_df.columns]]
                
                mu, sigma = self.generate_mu_sigma(
                    date, regime_forecasts, available_returns_df, available_regimes_df, available_assets
                )
                
                # Optimize
                weights_subset, diag = self.optimize_daily(
                    regime_forecasts, mu, sigma, available_assets
                )
                
                # Map to full asset space
                weights = np.zeros(n_assets)
                asset_idx_map = {asset: idx for idx, asset in enumerate(all_assets)}
                for j, asset in enumerate(available_assets):
                    weights[asset_idx_map[asset]] = weights_subset[j]
                
                weights_history.append({
                    'date': date,
                    **{asset: weights[j] for j, asset in enumerate(all_assets)},
                    'rf_weight': diag['rf_weight']
                })
                
                # Compute realized return
                date_idx = returns_df.index.get_loc(date)
                if date_idx + 1 < len(returns_df):
                    next_date = returns_df.index[date_idx + 1]
                    next_returns = returns_df.loc[next_date, all_assets].values
                    
                    # Portfolio return (excess)
                    portfolio_return = np.nansum(weights * next_returns)
                    
                    returns_history.append({
                        'date': next_date,
                        'return': portfolio_return if np.isfinite(portfolio_return) else 0.0
                    })
                
                diagnostics_history.append({
                    'date': date,
                    **{k: v for k, v in diag.items() if k not in ['weights']}
                })
                
            except Exception as e:
                if verbose and i < 5:
                    print(f"  ⚠ Error on {date}: {e}")
                continue
        
        if verbose:
            print("="*60 + "\n")
        
        # Convert to DataFrames
        if len(weights_history) == 0:
            return {
                'portfolio_returns': pd.Series(dtype=float),
                'portfolio_weights': pd.DataFrame(columns=all_assets + ['rf_weight']),
                'diagnostics': pd.DataFrame()
            }
        
        weights_df = pd.DataFrame(weights_history).set_index('date')
        returns_series = pd.DataFrame(returns_history).set_index('date')['return'] if returns_history else pd.Series(dtype=float)
        diagnostics_df = pd.DataFrame(diagnostics_history).set_index('date') if diagnostics_history else pd.DataFrame()
        
        return {
            'portfolio_returns': returns_series,
            'portfolio_weights': weights_df,
            'diagnostics': diagnostics_df
        }
    
    def reset(self):
        """Reset optimizer state."""
        self.w_prev = None


def optimize_portfolio_ra_fipo(
    regime_forecasts: np.ndarray,
    expected_returns: np.ndarray,
    covariance_matrix: np.ndarray,
    gamma_risk: float = 10.0,
    gamma_trade: float = 1.0,
    min_bullish_assets: int = 3,
    max_weight: float = 0.40,
    strategy: str = 'MV'
) -> Tuple[np.ndarray, Dict]:
    """Backward compatible wrapper."""
    engine = PortfolioEngine(
        gamma_risk=gamma_risk,
        gamma_trade=gamma_trade,
        min_bullish_assets=min_bullish_assets,
        max_weight=max_weight,
        strategy=strategy
    )
    
    asset_names = [f"Asset_{i}" for i in range(len(regime_forecasts))]
    return engine.optimize_daily(regime_forecasts, expected_returns, covariance_matrix, asset_names)
