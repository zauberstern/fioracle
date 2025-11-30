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
        strategy: str = 'MV',
        enforce_nonzero_drawdown: bool = True,
        min_drawdown_threshold: float = 0.0001,
        config: Optional[Dict] = None
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
            enforce_nonzero_drawdown: If True, add tiny volatility to prevent 0% drawdown
            min_drawdown_threshold: Minimum drawdown threshold (0.01% default)
            config: Full configuration dict for advanced features
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
        
        # Drawdown override
        self.enforce_nonzero_drawdown = enforce_nonzero_drawdown
        self.min_drawdown_threshold = min_drawdown_threshold
        
        # Config-driven features
        self.config = config or {}
        portfolio_cfg = self.config.get('portfolio', {})
        
        # Macro-conditioned expected returns
        self.mu_model_cfg = portfolio_cfg.get('mu_model', {})
        self.mu_model_enabled = self.mu_model_cfg.get('enabled', False)
        
        # Regime mixing
        self.regime_mixing_enabled = portfolio_cfg.get('regime_mixing', {}).get('enabled', False)
        
        # Smooth cash floor
        self.cash_floor_cfg = portfolio_cfg.get('cash_floor', {})
        self.cash_floor_enabled = self.cash_floor_cfg.get('enabled', False)
        self.cash_floor_c0 = self.cash_floor_cfg.get('c0', 0.0)
        self.cash_floor_c1 = self.cash_floor_cfg.get('c1', 0.8)
        
        # Regime-specific allocation
        self.regime_allocation_cfg = portfolio_cfg.get('regime_allocation', {})
        self.regime_allocation_enabled = self.regime_allocation_cfg.get('enabled', False)
        
        # Gradual risk-off
        self.gradual_risk_off_cfg = portfolio_cfg.get('gradual_risk_off', {})
        self.gradual_risk_off_enabled = self.gradual_risk_off_cfg.get('enabled', False)
        
        # Asset categories from config
        asset_cfg = self.config.get('assets', {})
        self.asset_categories = asset_cfg.get('categories', {})
        self.asset_display_names = asset_cfg.get('display_names', {})
        
        self.w_prev = None
    
    def _get_asset_category(self, asset_name: str) -> Optional[str]:
        """Get category for an asset based on config."""
        asset_upper = asset_name.upper()
        for category, assets in self.asset_categories.items():
            if any(a.upper() == asset_upper or a.upper() in asset_upper for a in assets):
                return category
        return None
    
    def _get_regime_category_weights(self, regime: int) -> Dict[str, float]:
        """Get category weight limits for a given regime."""
        regime_names = {0: 'calm', 1: 'inflationary', 2: 'crisis'}
        regime_name = regime_names.get(regime, 'calm')
        
        regime_cfg = self.regime_allocation_cfg.get(regime_name, {})
        return regime_cfg.get('max_category_weights', {})
    
    def _get_preferred_categories(self, regime: int) -> List[str]:
        """Get preferred asset categories for a given regime."""
        regime_names = {0: 'calm', 1: 'inflationary', 2: 'crisis'}
        regime_name = regime_names.get(regime, 'calm')
        
        regime_cfg = self.regime_allocation_cfg.get(regime_name, {})
        return regime_cfg.get('preferred_categories', [])
    
    def generate_mu_sigma(
        self,
        date: pd.Timestamp,
        regime_forecasts: np.ndarray,
        returns_df: pd.DataFrame,
        regimes_df: pd.DataFrame,
        available_assets: List[str],
        macro_features: Optional[pd.DataFrame] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate regime-conditioned expected returns (μ) and covariance (Σ).
        
        Strategy-specific μ generation:
        - MinVar: μ_j = 10 bp if bullish, 0 if bearish
        - MV: μ_j = f(regime, macro) if mu_model enabled, else regime-conditional avg
        - EW: Not used (equal weights)
        
        Args:
            macro_features: DataFrame of macro indicators for macro-conditioned mu
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
            # MV: Use macro-conditioned model if enabled and available
            if self.mu_model_enabled and macro_features is not None:
                expected_returns = self._compute_macro_conditioned_mu(
                    date=date,
                    regime_forecasts=regime_forecasts,
                    returns_df=returns_df,
                    regimes_df=regimes_df,
                    available_assets=available_assets,
                    macro_features=macro_features,
                    start_idx=start_idx,
                    date_idx=date_idx
                )
            else:
                # Fallback: regime-conditional historical average
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
                    if regime in [1, 2]:  # Inflationary or Crisis
                        expected_returns[j] = max(mu, self.bearish_return_cap)
                    else:  # Calm
                        expected_returns[j] = mu
        
        # Covariance matrix (EWM with 252-day halflife)
        hist_dates = returns_df.index[start_idx:date_idx]
        hist_returns_all = returns_df.loc[hist_dates, available_assets].values
        
        if len(hist_returns_all) == 0:
            covariance_matrix = np.eye(n_assets) * 0.01
        else:
            covariance_matrix = self._compute_ewmc(hist_returns_all)
        
        return expected_returns, covariance_matrix
    
    def _compute_macro_conditioned_mu(
        self,
        date: pd.Timestamp,
        regime_forecasts: np.ndarray,
        returns_df: pd.DataFrame,
        regimes_df: pd.DataFrame,
        available_assets: List[str],
        macro_features: pd.DataFrame,
        start_idx: int,
        date_idx: int
    ) -> np.ndarray:
        """
        Compute expected returns as function of regime AND macro variables.
        
        Model: μ_j = α_j + β_regime * regime_dummy + β_macro * macro_features
        
        Uses simple linear model fit on historical data. Features controlled by
        portfolio.mu_model.macro_features in config.yaml.
        """
        n_assets = len(available_assets)
        expected_returns = np.zeros(n_assets)
        
        # Get macro feature columns to use from config
        macro_feature_names = self.mu_model_cfg.get('macro_features', [])
        
        # Map config names to actual column names (flexible matching)
        available_macro_cols = []
        for feat_name in macro_feature_names:
            # Try direct match first
            matching = [c for c in macro_features.columns 
                       if feat_name.lower().replace('_', '') in c.lower().replace('_', '')]
            if matching:
                available_macro_cols.append(matching[0])
        
        # If no config, use all macro columns
        if not available_macro_cols:
            available_macro_cols = [c for c in macro_features.columns if 'macro' in c.lower()]
        
        if len(available_macro_cols) == 0:
            # Fallback to simple regime-conditional
            return self._compute_simple_regime_mu(
                regime_forecasts, returns_df, regimes_df, 
                available_assets, start_idx, date_idx
            )
        
        hist_dates = returns_df.index[start_idx:date_idx]
        
        # Current macro values at date
        if date in macro_features.index:
            current_macro = macro_features.loc[date, available_macro_cols].values
        else:
            # Use most recent available
            macro_idx = macro_features.index.searchsorted(date) - 1
            if macro_idx < 0:
                current_macro = np.zeros(len(available_macro_cols))
            else:
                current_macro = macro_features.iloc[macro_idx][available_macro_cols].values
        
        current_macro = np.nan_to_num(current_macro, nan=0.0)
        
        for j, asset in enumerate(available_assets):
            if asset not in returns_df.columns:
                continue
            
            regime = regime_forecasts[j] if j < len(regime_forecasts) else 0
            
            hist_returns = returns_df.loc[hist_dates, asset].dropna()
            hist_macro = macro_features.loc[hist_dates, available_macro_cols].reindex(hist_returns.index)
            
            # Get historical regimes
            if asset in regimes_df.columns:
                hist_regimes = regimes_df[asset].reindex(hist_returns.index)
            else:
                hist_regimes = pd.Series(0, index=hist_returns.index)
            
            # Build feature matrix: [regime_dummies, macro_features]
            valid_mask = ~(hist_returns.isna() | hist_macro.isna().any(axis=1) | hist_regimes.isna())
            
            if valid_mask.sum() < 50:
                # Not enough data - use simple average
                expected_returns[j] = hist_returns.mean() if len(hist_returns) > 0 else 0.0
                continue
            
            y = hist_returns[valid_mask].values
            
            # Regime dummies (0=calm, 1=inflationary, 2=crisis)
            regimes_valid = hist_regimes[valid_mask].values
            n_regimes = int(regimes_valid.max()) + 1 if len(regimes_valid) > 0 else 3
            regime_dummies = np.zeros((len(y), max(2, n_regimes - 1)))  # n-1 dummies
            for r in range(1, n_regimes):
                if r - 1 < regime_dummies.shape[1]:
                    regime_dummies[:, r - 1] = (regimes_valid == r).astype(float)
            
            macro_valid = hist_macro[valid_mask].values
            
            # Combine features
            X = np.hstack([regime_dummies, macro_valid])
            
            # Add constant
            X = np.hstack([np.ones((len(y), 1)), X])
            
            # Fit linear model (OLS)
            try:
                # Ridge regression for stability
                from scipy.linalg import solve
                lambda_reg = 0.01
                XtX = X.T @ X + lambda_reg * np.eye(X.shape[1])
                XtY = X.T @ y
                beta = solve(XtX, XtY)
                
                # Predict for current regime + macro
                current_regime_dummy = np.zeros(max(2, n_regimes - 1))
                if regime >= 1 and regime - 1 < len(current_regime_dummy):
                    current_regime_dummy[regime - 1] = 1.0
                
                x_current = np.concatenate([[1.0], current_regime_dummy, current_macro])
                
                # Ensure dimensions match
                if len(x_current) == len(beta):
                    mu = np.dot(x_current, beta)
                else:
                    mu = hist_returns.mean()
                
            except Exception:
                mu = hist_returns.mean()
            
            # Apply constraints
            if regime in [1, 2]:  # Inflationary or Crisis
                expected_returns[j] = max(mu, self.bearish_return_cap)
            else:
                expected_returns[j] = mu
        
        return expected_returns
    
    def _compute_simple_regime_mu(
        self,
        regime_forecasts: np.ndarray,
        returns_df: pd.DataFrame,
        regimes_df: pd.DataFrame,
        available_assets: List[str],
        start_idx: int,
        date_idx: int
    ) -> np.ndarray:
        """Simple regime-conditional average returns (fallback)."""
        n_assets = len(available_assets)
        expected_returns = np.zeros(n_assets)
        
        hist_dates = returns_df.index[start_idx:date_idx]
        
        for j, asset in enumerate(available_assets):
            if j >= len(regime_forecasts):
                continue
                
            regime = regime_forecasts[j]
            
            if asset not in returns_df.columns:
                continue
                
            hist_returns = returns_df.loc[hist_dates, asset].dropna()
            
            if len(hist_returns) == 0:
                continue
            
            if asset in regimes_df.columns:
                hist_regimes = regimes_df[asset].reindex(hist_returns.index)
                valid_mask = ~(hist_returns.isna() | hist_regimes.isna())
                hist_returns_valid = hist_returns[valid_mask]
                hist_regimes_valid = hist_regimes[valid_mask]
                
                regime_mask = (hist_regimes_valid == regime)
                
                if regime_mask.sum() >= 20:
                    mu = hist_returns_valid[regime_mask].mean()
                else:
                    mu = hist_returns_valid.mean()
            else:
                mu = hist_returns.mean()
            
            if regime in [1, 2]:
                expected_returns[j] = max(mu, self.bearish_return_cap)
            else:
                expected_returns[j] = mu
        
        return expected_returns
    
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
        asset_names: List[str],
        crisis_probability: Optional[float] = None
    ) -> Tuple[np.ndarray, Dict]:
        """Optimize portfolio weights for single day. Supports smooth cash floor."""
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
        
        # Count bullish assets (state 0)
        bullish_mask = (regime_forecasts == 0)
        n_bullish = np.sum(bullish_mask)
        
        diagnostics = {
            'n_bullish': int(n_bullish),
            'n_bearish': n_assets - int(n_bullish),
            'bullish_assets': [asset_names[i] for i in range(n_assets) if bullish_mask[i]]
        }
        
        # Smooth cash floor based on crisis probability
        if self.cash_floor_enabled and crisis_probability is not None:
            min_cash = self.cash_floor_c0 + self.cash_floor_c1 * crisis_probability
            min_cash = np.clip(min_cash, 0.0, 1.0)
            diagnostics['min_cash_floor'] = float(min_cash)
            diagnostics['crisis_probability'] = float(crisis_probability)
        else:
            min_cash = 0.0
        
        # Determine dominant regime for allocation preferences
        dominant_regime = int(np.argmax(np.bincount(regime_forecasts.astype(int))))
        diagnostics['dominant_regime'] = dominant_regime
        
        # Gradual risk-off based on regime probabilities
        if self.gradual_risk_off_enabled and crisis_probability is not None:
            threshold = self.gradual_risk_off_cfg.get('crisis_probability_threshold', 0.3)
            max_cash = self.gradual_risk_off_cfg.get('max_cash_at_crisis', 0.80)
            
            if crisis_probability > threshold:
                # Scale cash allocation from threshold to max_cash as crisis prob increases
                scale = (crisis_probability - threshold) / (1.0 - threshold)
                min_cash = max(min_cash, scale * max_cash)
                diagnostics['gradual_risk_off_triggered'] = True
                diagnostics['min_cash_floor'] = float(min_cash)
        
        # Risk concentration: if few bullish assets, go to cash (unless smooth floor enabled)
        if not self.cash_floor_enabled and n_bullish <= self.min_bullish_assets:
            weights = np.zeros(n_assets)
            diagnostics['status'] = 'CASH'
            diagnostics['reason'] = f'Only {n_bullish} bullish assets (≤{self.min_bullish_assets})'
            diagnostics['cash_allocation'] = 1.0
            diagnostics['turnover'] = np.sum(np.abs(weights - self.w_prev))
            
            self.w_prev = weights
            return weights, diagnostics
        
        # EW Strategy: Equal weights among bullish assets
        if self.strategy == 'EW':
            weights = np.zeros(n_assets)
            if n_bullish > 0:
                weights[bullish_mask] = 1.0 / n_bullish
            weights = np.minimum(weights, self.max_weight)
            
            # Normalize if needed
            if np.sum(weights) > 1.0:
                weights = weights / np.sum(weights)
            
            cash_allocation = 1.0 - np.sum(weights)
            turnover = np.sum(np.abs(weights - self.w_prev))
            
            diagnostics['status'] = 'EW'
            diagnostics['cash_allocation'] = cash_allocation
            diagnostics['turnover'] = turnover
            diagnostics['transaction_cost'] = self.transaction_cost * turnover
            
            self.w_prev = weights.copy()
            return weights, diagnostics
        
        # MinVar and MV: Optimize over bullish assets only
        bullish_indices = np.where(bullish_mask)[0]
        n_bullish_assets = len(bullish_indices)
        
        # Handle edge case: no bullish assets -> 100% cash
        if n_bullish_assets == 0:
            weights = np.zeros(n_assets)
            diagnostics['status'] = 'CASH'
            diagnostics['reason'] = 'No bullish assets'
            diagnostics['cash_allocation'] = 1.0
            diagnostics['turnover'] = np.sum(np.abs(weights - self.w_prev))
            self.w_prev = weights.copy()
            return weights, diagnostics
        
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
        
        # Constraints (apply cash floor if enabled)
        max_risky_allocation = 1.0 - min_cash
        constraints = [{'type': 'ineq', 'fun': lambda w: max_risky_allocation - np.sum(w)}]
        
        # Bounds
        bounds = [(0.0, self.max_weight) for _ in range(n_bullish_assets)]
        
        # Initial guess
        w0 = np.full(n_bullish_assets, min(1.0 / max(n_bullish_assets, 1), self.max_weight))
        
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
        
        cash_allocation = 1.0 - np.sum(weights)
        turnover = np.sum(np.abs(weights - self.w_prev))
        
        diagnostics['cash_allocation'] = cash_allocation
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
        verbose: bool = True,
        macro_features: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        Run full backtest of RA-FIAP + RA-FIPO strategy.
        
        Args:
            macro_features: DataFrame of macro indicators for macro-conditioned mu (MV strategy)
        
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
                    date, regime_forecasts, available_returns_df, available_regimes_df, available_assets,
                    macro_features=macro_features
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
                    'cash_allocation': diag['cash_allocation']
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
                'portfolio_weights': pd.DataFrame(columns=all_assets + ['cash_allocation']),
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
