"""
Regime-aware portfolio optimization with MVO, MinVar, and EW strategies.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, Tuple, Optional, List
import warnings
import logging

logger = logging.getLogger(__name__)


class PortfolioEngine:
    """Combines regime forecasts with MVO/MinVar/EW optimization."""
    
    def __init__(
        self,
        gamma_risk: float = 10.0,
        gamma_trade: float = 2.0,
        transaction_cost: float = 0.0005,
        min_bullish_assets: int = 3,
        max_weight: float = 0.35,
        covariance_halflife: int = 252,
        lookback_years: int = 7,
        bearish_return_cap: float = -0.001,
        bullish_return_minvar: float = 0.001,
        strategy: str = 'MV',
        enforce_nonzero_drawdown: bool = True,
        min_drawdown_threshold: float = 0.0001,
        config: Optional[Dict] = None
    ):
        """Setup optimization parameters and config-driven features."""
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
        
        # =========================================================================
        # TIERED TRANSACTION COSTS - Asset-class specific costs
        # =========================================================================
        tiered_cfg = portfolio_cfg.get('tiered_transaction_costs', {})
        self.tiered_costs_enabled = tiered_cfg.get('enabled', False)
        self.tiered_costs_by_asset = tiered_cfg.get('costs_by_asset', {})
        self.tiered_default_cost = tiered_cfg.get('default_cost', 0.0005)
        
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
        
        # Tail hedges
        self.tail_hedges_cfg = portfolio_cfg.get('tail_hedges', {})
        self.tail_hedges_enabled = self.tail_hedges_cfg.get('enabled', False)
        
        # Rebalancing frequency (daily, weekly, monthly)
        eval_cfg = self.config.get('evaluation', {})
        self.rebalance_frequency = eval_cfg.get('rebalance_frequency', 'daily')
        
        # Asset categories from config
        asset_cfg = self.config.get('assets', {})
        self.asset_categories = asset_cfg.get('categories', {})
        self.asset_display_names = asset_cfg.get('display_names', {})
        
        # Number of regime states (2=bull/bear, 3=calm/inflationary/crisis)
        # Controls whether 3-state specific logic (inflationary dampening, crisis caps) is applied
        regimes_cfg = self.config.get('regimes', {})
        self.n_states = regimes_cfg.get('jump_model', {}).get('n_states', 3)
        
        self.w_prev = None
        
        # For regime mixing: store reference to regime engine and features
        self._regime_engine = None
        self._asset_features_dict = None
    
    def set_regime_engine(self, regime_engine, asset_features_dict: Dict[str, pd.DataFrame] = None):
        """Attach a RegimeEngine for probability-based allocation."""
        self._regime_engine = regime_engine
        self._asset_features_dict = asset_features_dict
    
    def _should_rebalance(self, current_date: pd.Timestamp, last_rebalance_date: Optional[pd.Timestamp]) -> bool:
        """Check if rebalancing is due based on frequency setting."""
        # Always rebalance on first day
        if last_rebalance_date is None:
            return True
        
        freq = self.rebalance_frequency.lower()
        
        if freq == 'daily':
            return True
        
        elif freq == 'weekly':
            # Rebalance on Mondays, or if >7 days since last rebalance
            days_since = (current_date - last_rebalance_date).days
            is_monday = current_date.dayofweek == 0
            return is_monday or days_since >= 7
        
        elif freq == 'monthly':
            # Rebalance on first trading day of month, or if >31 days since last rebalance
            days_since = (current_date - last_rebalance_date).days
            is_new_month = current_date.month != last_rebalance_date.month
            return is_new_month or days_since >= 31
        
        else:
            # Unknown frequency, default to daily
            return True
    
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
    
    def _get_transaction_cost(self, asset_name: str) -> float:
        """Look up transaction cost for an asset (tiered if enabled)."""
        if not self.tiered_costs_enabled:
            return self.transaction_cost
        
        asset_upper = asset_name.upper()
        
        # Find best matching pattern (longest match wins)
        best_match = None
        best_match_len = 0
        
        for pattern, cost in self.tiered_costs_by_asset.items():
            pattern_upper = pattern.upper()
            if pattern_upper in asset_upper:
                if len(pattern_upper) > best_match_len:
                    best_match = cost
                    best_match_len = len(pattern_upper)
        
        if best_match is not None:
            return best_match
        
        return self.tiered_default_cost
    
    def _get_transaction_costs_array(self, asset_names: List[str]) -> np.ndarray:
        """Return array of transaction costs for all assets."""
        return np.array([self._get_transaction_cost(name) for name in asset_names])
    
    def generate_mu_sigma(
        self,
        date: pd.Timestamp,
        regime_forecasts: np.ndarray,
        returns_df: pd.DataFrame,
        regimes_df: pd.DataFrame,
        available_assets: List[str],
        macro_features: Optional[pd.DataFrame] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Build expected return vector and covariance matrix for optimization."""
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
            # MinVar: μ_j based on regime state
            # 3-state: +10bp calm, 0 inflationary, -10bp crisis
            # 2-state: +10bp bullish (0), -10bp bearish (1)
            for j in range(n_assets):
                if j < len(regime_forecasts):
                    regime = regime_forecasts[j]
                    if self.n_states == 3:
                        # 3-state: calm(0)=bullish, inflationary(1)=neutral, crisis(2)=bearish
                        if regime == 0:  # Calm/Bullish
                            expected_returns[j] = self.bullish_return_minvar  # +10 bps
                        elif regime == 2:  # Crisis/Bearish
                            expected_returns[j] = -self.bullish_return_minvar  # -10 bps (PENALIZE)
                        else:  # Inflationary/Cautious (regime == 1)
                            expected_returns[j] = 0.0  # Neutral
                    else:
                        # 2-state: bullish(0)=invest, bearish(1)=avoid
                        if regime == 0:  # Bullish
                            expected_returns[j] = self.bullish_return_minvar
                        else:  # Bearish
                            expected_returns[j] = -self.bullish_return_minvar
        
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
                    # Include current date's return since it's available at close of day
                    hist_dates = returns_df.index[start_idx:date_idx + 1]
                    
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
                    
                    # Apply regime-specific adjustments based on n_states
                    if self.n_states == 3:
                        # 3-state: calm=full, inflationary=dampened, crisis=capped
                        if regime == 0:  # Calm: full expected return
                            expected_returns[j] = mu
                        elif regime == 1:  # Inflationary: dampened return (50%)
                            expected_returns[j] = max(mu * 0.5, self.bearish_return_cap)
                        else:  # Crisis (regime 2): capped return
                            expected_returns[j] = self.bearish_return_cap
                    else:
                        # 2-state: bullish=full, bearish=capped
                        if regime == 0:  # Bullish: full expected return
                            expected_returns[j] = mu
                        else:  # Bearish: capped return
                            expected_returns[j] = self.bearish_return_cap
        
        # Covariance matrix (EWM with 252-day halflife)
        # Include current date's return since it's available at close of day
        # slice [start_idx:date_idx+1] includes dates from start_idx up to AND including date_idx
        hist_dates = returns_df.index[start_idx:date_idx + 1]
        hist_returns_all = returns_df.loc[hist_dates, available_assets]
        
        # Handle NaNs before computing covariance
        hist_returns_all = hist_returns_all.dropna(how='all')
        
        if len(hist_returns_all) == 0:
            covariance_matrix = np.eye(n_assets) * 0.01
        else:
            covariance_matrix = self._compute_ewmc(hist_returns_all.values)
        
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
        """Compute mu as a linear function of regime and macro features."""
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
        
        # Include current date's return since it's available at close of day
        hist_dates = returns_df.index[start_idx:date_idx + 1]
        
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
            
            # Apply regime-specific adjustments for 3-state model
            if regime == 0:  # Calm: full expected return
                expected_returns[j] = mu
            elif regime == 1:  # Inflationary: dampened return (50%)
                expected_returns[j] = max(mu * 0.5, self.bearish_return_cap)
            else:  # Crisis (regime 2): capped return
                expected_returns[j] = self.bearish_return_cap
        
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
        """Fallback: simple regime-conditional average returns."""
        n_assets = len(available_assets)
        expected_returns = np.zeros(n_assets)
        
        # Include current date's return since it's available at close of day
        hist_dates = returns_df.index[start_idx:date_idx + 1]
        
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
            
            # Apply regime-specific adjustments for 3-state model
            if regime == 0:  # Calm: full expected return
                expected_returns[j] = mu
            elif regime == 1:  # Inflationary: dampened return (50%)
                expected_returns[j] = max(mu * 0.5, self.bearish_return_cap)
            else:  # Crisis (regime 2): capped return
                expected_returns[j] = self.bearish_return_cap
        
        return expected_returns
    
    def _compute_ewmc(self, returns: np.ndarray) -> np.ndarray:
        """Exponentially weighted covariance with regularization."""
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
        crisis_probability: Optional[float] = None,
        regime_probabilities: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, Dict]:
        """Run one-day MVO optimization. Returns weights and diagnostics dict."""
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
        
        # Get per-asset transaction costs (tiered if enabled)
        transaction_costs = self._get_transaction_costs_array(asset_names)
        
        # =========================================================================
        # REGIME MIXING: Use probability-weighted investability scores
        # =========================================================================
        if self.regime_mixing_enabled and regime_probabilities is not None:
            # Regime mixing: compute soft investability scores from probabilities
            # P(calm) * 1.0 + P(inflationary) * 0.5 + P(crisis) * 0.0
            # Score of 1.0 = fully investable, 0.0 = not investable
            
            # Ensure probabilities have correct shape (n_assets, 3)
            if regime_probabilities.shape == (n_assets, 3):
                investability_scores = (
                    regime_probabilities[:, 0] * 1.0 +   # Calm: fully investable
                    regime_probabilities[:, 1] * 0.5 +   # Inflationary: half
                    regime_probabilities[:, 2] * 0.0     # Crisis: not investable
                )
            elif regime_probabilities.shape[0] == n_assets and regime_probabilities.shape[1] == 2:
                # Only 2 classes present (e.g., calm and crisis)
                # Assume column 0 = calm, column 1 = crisis
                investability_scores = regime_probabilities[:, 0] * 1.0
            else:
                # Fallback to discrete
                investability_scores = np.where(regime_forecasts == 0, 1.0,
                                               np.where(regime_forecasts == 1, 0.5, 0.0))
            
            # Soft masks based on probability thresholds
            bullish_mask = investability_scores >= 0.7   # High confidence calm
            cautious_mask = (investability_scores >= 0.3) & (investability_scores < 0.7)
            bearish_mask = investability_scores < 0.3    # High confidence crisis
            investable_mask = investability_scores >= 0.3  # Include if score >= 0.3
            
        else:
            # Original discrete logic (no regime mixing)
            # 3-state regime logic:
            # - Calm (0): Fully investable (bullish)
            # - Inflationary (1): Cautiously investable (neutral)
            # - Crisis (2): Not investable (bearish)
            bullish_mask = (regime_forecasts == 0)      # Calm = bullish
            cautious_mask = (regime_forecasts == 1)    # Inflationary = cautious
            bearish_mask = (regime_forecasts == 2)     # Crisis = bearish
            investable_mask = (regime_forecasts <= 1)  # Calm or Inflationary
            investability_scores = np.where(bullish_mask, 1.0, 
                                           np.where(cautious_mask, 0.5, 0.0))
        
        n_investable = np.sum(investable_mask)
        n_bullish = np.sum(bullish_mask)
        n_cautious = np.sum(cautious_mask)
        n_bearish = np.sum(bearish_mask)
        
        # Determine if we're actually using smooth transitions (probabilities) vs discrete
        using_smooth_transitions = (
            self.regime_mixing_enabled and 
            regime_probabilities is not None and 
            regime_probabilities.shape[0] == n_assets
        )
        
        diagnostics = {
            'n_bullish': int(n_bullish),
            'n_cautious': int(n_cautious),
            'n_bearish': int(n_bearish),
            'n_investable': int(n_investable),
            'bullish_assets': [asset_names[i] for i in range(n_assets) if bullish_mask[i]],
            'cautious_assets': [asset_names[i] for i in range(n_assets) if cautious_mask[i]],
            'tiered_costs_enabled': self.tiered_costs_enabled,
            'regime_mixing_enabled': self.regime_mixing_enabled,
            'using_smooth_transitions': using_smooth_transitions,  # True only if probabilities available
            'avg_investability_score': float(np.mean(investability_scores)) if n_assets > 0 else 0.0,
            'min_investability_score': float(np.min(investability_scores)) if n_assets > 0 else 0.0,
            'max_investability_score': float(np.max(investability_scores)) if n_assets > 0 else 0.0
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
        
        # Crisis override: if dominant regime is crisis, enforce configurable minimum cash
        # Configurable via cash_floor.crisis_override_min (default 30%, was hardcoded 50%)
        crisis_override_min = self.cash_floor_cfg.get('crisis_override_min', 0.30)
        if dominant_regime == 2:  # Crisis
            min_cash = max(min_cash, crisis_override_min)
            diagnostics['crisis_override'] = True
            diagnostics['crisis_override_min'] = crisis_override_min
        
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
        
        # Risk concentration: if few investable assets, go to cash (unless smooth floor enabled)
        # Use investable count (bullish + cautious) instead of just bullish
        if not self.cash_floor_enabled and n_investable <= self.min_bullish_assets:
            weights = np.zeros(n_assets)
            diagnostics['status'] = 'CASH'
            diagnostics['reason'] = f'Only {n_investable} investable assets (≤{self.min_bullish_assets})'
            diagnostics['cash_allocation'] = 1.0
            diagnostics['turnover'] = np.sum(np.abs(weights - self.w_prev))
            
            self.w_prev = weights
            return weights, diagnostics
        
        # EW Strategy: Equal weights among investable assets
        # Bullish get full weight, Cautious get 50% weight
        if self.strategy == 'EW':
            weights = np.zeros(n_assets)
            if n_investable > 0:
                if self.regime_mixing_enabled:
                    # Regime mixing: use continuous investability scores as weights
                    # This creates smooth transitions instead of discrete jumps
                    raw_weights = investability_scores.copy()
                    raw_weights[raw_weights < 0.1] = 0.0  # Zero out very low scores
                else:
                    # Discrete: bullish=1.0, cautious=0.5, bearish=0.0
                    raw_weights = np.where(bullish_mask, 1.0, np.where(cautious_mask, 0.5, 0.0))
                
                total_raw = raw_weights.sum()
                if total_raw > 0:
                    # Normalize to sum to max_risky_allocation (respects cash floor)
                    max_risky_allocation = 1.0 - min_cash
                    weights = (raw_weights / total_raw) * max_risky_allocation
            weights = np.minimum(weights, self.max_weight)
            
            # Ensure we don't exceed risky allocation budget
            max_risky_allocation = 1.0 - min_cash
            if np.sum(weights) > max_risky_allocation:
                weights = weights * (max_risky_allocation / np.sum(weights))
            
            cash_allocation = 1.0 - np.sum(weights)
            turnover = np.sum(np.abs(weights - self.w_prev))
            
            # Compute weighted transaction cost (tiered by asset)
            weight_changes = np.abs(weights - self.w_prev)
            total_transaction_cost = np.sum(weight_changes * transaction_costs)
            
            diagnostics['status'] = 'EW'
            diagnostics['cash_allocation'] = cash_allocation
            diagnostics['turnover'] = turnover
            diagnostics['transaction_cost'] = total_transaction_cost
            
            self.w_prev = weights.copy()
            return weights, diagnostics
        
        # MinVar and MV: Optimize over INVESTABLE assets (bullish + cautious)
        investable_indices = np.where(investable_mask)[0]
        n_investable_assets = len(investable_indices)
        
        # Handle edge case: no investable assets -> 100% cash
        if n_investable_assets == 0:
            weights = np.zeros(n_assets)
            diagnostics['status'] = 'CASH'
            diagnostics['reason'] = 'No investable assets'
            diagnostics['cash_allocation'] = 1.0
            diagnostics['turnover'] = np.sum(np.abs(weights - self.w_prev))
            self.w_prev = weights.copy()
            return weights, diagnostics
        
        # Subset matrices for investable assets
        sigma_investable = covariance_matrix[np.ix_(investable_indices, investable_indices)]
        mu_investable = expected_returns[investable_indices]
        w_prev_investable = self.w_prev[investable_indices]
        costs_investable = transaction_costs[investable_indices]  # Per-asset costs
        
        # Get regime status and investability scores for each investable asset
        regimes_investable = regime_forecasts[investable_indices]
        scores_investable = investability_scores[investable_indices]
        
        # MinVar adjustment with 3-state logic
        if self.strategy == 'MinVar':
            if self.regime_mixing_enabled:
                # Regime mixing: use continuous investability scores to modulate returns
                # Score of 1.0 (calm) → +10bp, Score of 0.5 (inflationary) → 0bp
                # Linear interpolation: mu = score * 2 * bullish_return - bullish_return
                # When score=1.0: mu = +10bp, score=0.5: mu = 0bp, score=0.3: mu = -4bp
                mu_investable = (scores_investable * 2 - 1) * self.bullish_return_minvar
            else:
                # Discrete: Bullish (calm): +10bp, Cautious (inflationary): 0bp
                mu_investable = np.where(
                    regimes_investable == 0,  # Calm/Bullish
                    self.bullish_return_minvar,  # +10 bps
                    0.0  # Cautious/Inflationary: neutral
                )
        
        # Objective function (Equation 2) with asset-specific transaction costs
        # maximize w^T μ - γ_risk w^T Σ w - γ_trade × Σ_j a_j |w_j - w_pre_j|
        def objective(w):
            ret = np.dot(w, mu_investable)
            var = np.dot(w, np.dot(sigma_investable, w))
            # Asset-specific turnover costs
            turnover_cost = self.gamma_trade * np.sum(costs_investable * np.abs(w - w_prev_investable))
            return -(ret - self.gamma_risk * var - turnover_cost)
        
        def gradient(w):
            grad_ret = mu_investable
            grad_var = 2 * self.gamma_risk * np.dot(sigma_investable, w)
            # Asset-specific gradient for turnover
            grad_turn = self.gamma_trade * costs_investable * np.sign(w - w_prev_investable)
            return -(grad_ret - grad_var - grad_turn)
        
        # Constraints (apply cash floor if enabled)
        max_risky_allocation = 1.0 - min_cash
        constraints = [{'type': 'ineq', 'fun': lambda w: max_risky_allocation - np.sum(w)}]
        
        # Enforce regime-specific category caps (if enabled)
        # IMPORTANT: Scale category caps by max_risky_allocation to avoid infeasibility
        if self.regime_allocation_enabled:
            try:
                # Determine dominant regime (already computed above)
                category_caps = self._get_regime_category_weights(dominant_regime) or {}
                # Build mapping from category -> indices in investable set
                cat_to_indices = {}
                for local_idx, global_idx in enumerate(investable_indices):
                    asset = asset_names[global_idx]
                    cat = self._get_asset_category(asset)
                    if cat is None:
                        continue
                    cat_to_indices.setdefault(cat, []).append(local_idx)
                # Add linear inequality constraints: sum_{j in cat} w_j <= cap * max_risky_allocation
                # This ensures caps are proportional to available allocation budget
                for cat, idx_list in cat_to_indices.items():
                    cap = float(category_caps.get(cat, 1.0))  # default no cap if not specified
                    # Scale cap by risky allocation budget to maintain feasibility
                    cap_effective = cap * max_risky_allocation
                    if len(idx_list) == 0 or cap_effective >= max_risky_allocation:
                        continue
                    A = np.zeros(n_investable_assets)
                    A[idx_list] = 1.0
                    constraints.append({'type': 'ineq', 'fun': lambda w, A=A, cap=cap_effective: cap - np.dot(A, w)})
                diagnostics['category_caps_applied'] = True
                diagnostics['category_caps'] = category_caps
                diagnostics['category_caps_scaled_by'] = max_risky_allocation
            except Exception:
                diagnostics['category_caps_applied'] = False
        
        # Tail-hedge minimum allocation when crisis probability is elevated
        tail_cfg = getattr(self, 'tail_hedges_cfg', {}) if hasattr(self, 'tail_hedges_cfg') else {}
        if getattr(self, 'tail_hedges_enabled', False) and tail_cfg:
            try:
                # Union of hedge assets
                hedge_sets = []
                for key in ['chf_assets', 'gold_assets', 'gov_safe_assets', 'volatility_hedges']:
                    hedge_sets.extend([a.upper() for a in tail_cfg.get(key, [])])
                hedge_assets = set(hedge_sets)
                # Map to local investable indices
                hedge_local_indices = []
                for local_idx, global_idx in enumerate(investable_indices):
                    asset = asset_names[global_idx].upper().replace('.CSV', '')
                    # loose matching to handle suffix differences
                    if any(h in asset for h in hedge_assets):
                        hedge_local_indices.append(local_idx)
                if len(hedge_local_indices) > 0:
                    # Crisis-probability-driven floor: start at 0 for p<=0.2, up to 40% at p>=1.0
                    cp = float(crisis_probability) if crisis_probability is not None else 0.0
                    hedge_min_total = max(0.0, (cp - 0.2) * 0.5)  # linear scale, cap at 0.4
                    hedge_min_total = min(0.4, hedge_min_total)
                    # Apply to risky budget
                    required_min = hedge_min_total * max_risky_allocation
                    if required_min > 0:
                        A = np.zeros(n_investable_assets)
                        A[hedge_local_indices] = 1.0
                        constraints.append({'type': 'ineq', 'fun': lambda w, A=A, req=required_min: np.dot(A, w) - req})
                        diagnostics['tail_hedge_min_required'] = required_min
                        diagnostics['tail_hedge_indices'] = hedge_local_indices
                else:
                    diagnostics['tail_hedge_min_required'] = 0.0
            except Exception:
                # Ignore if anything goes wrong; keep problem feasible
                pass
        
        # Bounds
        bounds = [(0.0, self.max_weight) for _ in range(n_investable_assets)]
        
        # =========================================================================
        # SMART INITIAL GUESS - Feasibility-aware starting point
        # =========================================================================
        # Compute a feasible initial guess that respects all known constraints
        initial_weight = min(max_risky_allocation / max(n_investable_assets, 1), self.max_weight)
        w0 = np.full(n_investable_assets, max(0.0, initial_weight * 0.8))  # Start at 80% of max
        
        # If tail hedge is required, bias initial guess toward hedge assets
        if diagnostics.get('tail_hedge_min_required', 0) > 0:
            hedge_indices = diagnostics.get('tail_hedge_indices', [])
            if len(hedge_indices) > 0:
                hedge_min = diagnostics['tail_hedge_min_required']
                per_hedge = min(hedge_min / len(hedge_indices), self.max_weight)
                for idx in hedge_indices:
                    w0[idx] = max(w0[idx], per_hedge)
        
        # Normalize to respect max_risky_allocation
        if np.sum(w0) > max_risky_allocation:
            w0 = w0 * (max_risky_allocation / np.sum(w0))
        
        # =========================================================================
        # ROBUST MULTI-SOLVER OPTIMIZATION
        # =========================================================================
        # Strategy: Try SLSQP first (fastest), then trust-constr (most robust),
        # then COBYLA (derivative-free, handles numerical issues well)
        
        def try_slsqp(constraint_set, tol=1e-8, w_init=None):
            """Try SLSQP optimization"""
            try:
                res = minimize(
                    objective, w_init if w_init is not None else w0,
                    method='SLSQP',
                    jac=gradient,
                    bounds=bounds,
                    constraints=constraint_set,
                    options={'maxiter': 1000, 'ftol': tol}
                )
                return res.success and res.fun < 1e10, res
            except Exception:
                return False, None
        
        def try_cobyla(constraint_set, w_init=None):
            """Try COBYLA optimization (derivative-free, more robust)"""
            try:
                # Convert inequality constraints for COBYLA (must be >= 0)
                cobyla_constraints = []
                for c in constraint_set:
                    if c['type'] == 'ineq':
                        cobyla_constraints.append({'type': 'ineq', 'fun': c['fun']})
                # Add bounds as constraints for COBYLA
                for i in range(n_investable_assets):
                    cobyla_constraints.append({'type': 'ineq', 'fun': lambda w, i=i: w[i]})  # w[i] >= 0
                    cobyla_constraints.append({'type': 'ineq', 'fun': lambda w, i=i: self.max_weight - w[i]})  # w[i] <= max
                
                res = minimize(
                    objective, w_init if w_init is not None else w0,
                    method='COBYLA',
                    constraints=cobyla_constraints,
                    options={'maxiter': 2000, 'rhobeg': 0.1}
                )
                # Check if result is within bounds
                if res.x is not None and np.all(res.x >= -1e-6) and np.all(res.x <= self.max_weight + 1e-6):
                    return res.success, res
                return False, res
            except Exception:
                return False, None
        
        # Build constraint levels from most restrictive to least
        constraints_full = constraints.copy()
        
        # Count constraints before tail hedge
        n_base_constraints = 1  # Cash floor constraint
        if diagnostics.get('category_caps_applied', False):
            n_base_constraints += len([c for c in constraints[1:] if diagnostics.get('tail_hedge_min_required', 0) == 0 or c != constraints[-1]])
        
        # Level 2: Drop tail hedge minimum
        has_tail_hedge = diagnostics.get('tail_hedge_min_required', 0) > 0
        constraints_no_tail = constraints[:-1] if has_tail_hedge and len(constraints) > 1 else constraints.copy()
        
        # Level 3: Cash floor only
        constraints_cash_only = [constraints[0]] if constraints else []
        
        # Level 4: Relaxed sum constraint (no strict cash floor)
        constraints_relaxed = [{'type': 'ineq', 'fun': lambda w: 0.98 - np.sum(w)}]  # Allow 98% allocation
        
        # Try optimization with progressive relaxation and multiple solvers
        result = None
        final_constraint_level = 'full'
        solver_used = 'SLSQP'
        
        constraint_levels = [
            ('full', constraints_full),
            ('no_tail_hedge', constraints_no_tail),
            ('cash_only', constraints_cash_only),
            ('relaxed', constraints_relaxed),
        ]
        
        # Try each constraint level with SLSQP first
        for constraint_name, constraint_set in constraint_levels:
            for tol in [1e-9, 1e-8, 1e-7, 1e-6, 1e-5]:
                success, res = try_slsqp(constraint_set, tol)
                if success:
                    result = res
                    final_constraint_level = constraint_name
                    solver_used = 'SLSQP'
                    break
            if result is not None and result.success:
                break
        
        # If SLSQP failed, try COBYLA with relaxed constraints
        if result is None or not result.success:
            for constraint_name, constraint_set in constraint_levels[1:]:  # Skip 'full'
                success, res = try_cobyla(constraint_set)
                if success:
                    result = res
                    final_constraint_level = constraint_name
                    solver_used = 'COBYLA'
                    break
        
        # Final fallback: simple equal weight
        if result is None or not result.success:
            w_opt = np.full(n_investable_assets, max_risky_allocation / max(n_investable_assets, 1))
            w_opt = np.minimum(w_opt, self.max_weight)
            diagnostics['status'] = 'EQUAL_WEIGHT_FALLBACK'
            diagnostics['solver_used'] = 'none'
            final_constraint_level = 'fallback'
        else:
            w_opt = result.x
        
        # Log constraint relaxation (only warn if significant)
        diagnostics['constraint_level'] = final_constraint_level
        diagnostics['solver_used'] = solver_used
        if final_constraint_level not in ('full', 'no_tail_hedge'):
            if final_constraint_level != 'fallback':
                logger.debug(f"Solver ({solver_used}) used constraint level: {final_constraint_level}")
            diagnostics['constraint_relaxation'] = final_constraint_level
        
        # Extract result
        if result is not None and result.success:
            w_opt = result.x
            diagnostics['status'] = 'SUCCESS'
            diagnostics['solver_iterations'] = result.nit if hasattr(result, 'nit') else None
        elif result is not None and diagnostics.get('status') != 'EQUAL_WEIGHT_FALLBACK':
            # Use last result even if not fully converged
            w_opt = np.clip(result.x, 0.0, self.max_weight)
            # Ensure sum doesn't exceed max_risky_allocation
            if np.sum(w_opt) > max_risky_allocation:
                w_opt = w_opt * (max_risky_allocation / np.sum(w_opt))
            diagnostics['status'] = 'PARTIAL_CONVERGENCE'
            diagnostics['solver_message'] = result.message if result else 'No result'
        elif diagnostics.get('status') != 'EQUAL_WEIGHT_FALLBACK':
            # Complete failure - use equal weight among investable assets
            w_opt = np.full(n_investable_assets, max_risky_allocation / max(n_investable_assets, 1))
            w_opt = np.minimum(w_opt, self.max_weight)
            diagnostics['status'] = 'EQUAL_WEIGHT_FALLBACK'
            logger.warning(f"Optimizer completely failed, using equal weight fallback")
        
        # Map back to full space
        weights = np.zeros(n_assets)
        weights[investable_indices] = w_opt
        
        # Enforce constraints (safety net)
        weights = np.maximum(weights, 0.0)
        weights = np.minimum(weights, self.max_weight)
        if np.sum(weights) > 1.0:
            weights = weights / np.sum(weights)
        
        # =========================================================================
        # FEASIBILITY CHECKS - Verify optimizer output satisfies constraints
        # =========================================================================
        cash_allocation = 1.0 - np.sum(weights)
        
        # Check 1: All weights non-negative and within bounds
        if np.any(weights < -1e-6):
            diagnostics['feasibility_warning'] = 'negative_weights'
        if np.any(weights > self.max_weight + 1e-6):
            diagnostics['feasibility_warning'] = 'weight_exceeds_max'
        
        # Check 2: Total allocation sums to 1 (within tolerance)
        total_allocation = np.sum(weights) + cash_allocation
        if abs(total_allocation - 1.0) > 1e-4:
            diagnostics['feasibility_warning'] = f'allocation_sum={total_allocation:.6f}'
        
        # Check 3: Track solver convergence
        diagnostics['solver_converged'] = (diagnostics.get('status') == 'SUCCESS')
        
        turnover = np.sum(np.abs(weights - self.w_prev))
        
        # Compute weighted transaction cost (tiered by asset)
        weight_changes = np.abs(weights - self.w_prev)
        total_transaction_cost = np.sum(weight_changes * transaction_costs)
        
        diagnostics['cash_allocation'] = cash_allocation
        diagnostics['expected_return'] = np.dot(weights, expected_returns)
        diagnostics['expected_volatility'] = np.sqrt(np.dot(weights, np.dot(covariance_matrix, weights)))
        diagnostics['turnover'] = turnover
        diagnostics['transaction_cost'] = total_transaction_cost
        diagnostics['avg_transaction_cost_bps'] = (total_transaction_cost / max(turnover, 1e-10)) * 10000
        
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
        macro_features: Optional[pd.DataFrame] = None,
        risk_free_rate: Optional[pd.Series] = None
    ) -> Dict:
        """Full historical backtest with daily or lower-frequency rebalancing."""
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
        
        # Rebalancing state
        last_rebalance_date = None
        previous_weights = None
        previous_diag = None
        
        if verbose:
            print("="*60)
            print(f"Running Backtest ({self.strategy} JM-XGB, rebalance={self.rebalance_frequency})")
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
                
                # Determine if we should rebalance today
                should_rebalance = self._should_rebalance(date, last_rebalance_date)
                
                if should_rebalance:
                    # Generate μ and Σ
                    available_returns_df = returns_df[available_assets]
                    available_regimes_df = regimes_df[[c for c in available_assets if c in regimes_df.columns]]
                    
                    mu, sigma = self.generate_mu_sigma(
                        date, regime_forecasts, available_returns_df, available_regimes_df, available_assets,
                        macro_features=macro_features
                    )
                    
                    # Compute crisis probability from regime forecasts
                    # Crisis probability = proportion of assets in crisis regime (state 2)
                    crisis_prob = (regime_forecasts == 2).mean()
                    
                    # Get regime probabilities for regime mixing (if enabled and regime_engine available)
                    regime_probs = None
                    if self.regime_mixing_enabled and hasattr(self, '_regime_engine') and self._regime_engine is not None:
                        try:
                            # Get asset features dict from the engine
                            asset_features_dict = getattr(self, '_asset_features_dict', None)
                            if asset_features_dict is not None and macro_features is not None:
                                regime_probs = self._regime_engine.get_regime_probabilities(
                                    asset_features_dict, macro_features, date, available_assets
                                )
                        except Exception:
                            regime_probs = None  # Fall back to discrete if probabilities unavailable
                    
                    # Optimize with crisis probability and regime probabilities
                    weights_subset, diag = self.optimize_daily(
                        regime_forecasts, mu, sigma, available_assets,
                        crisis_probability=crisis_prob,
                        regime_probabilities=regime_probs
                    )
                    diag['rebalanced'] = True
                    
                    # Update rebalancing state
                    last_rebalance_date = date
                    previous_weights = weights_subset.copy()
                    previous_diag = diag.copy()
                else:
                    # Use previous weights (hold position)
                    if previous_weights is not None and len(previous_weights) == n_available:
                        weights_subset = previous_weights
                        diag = previous_diag.copy()
                        diag['rebalanced'] = False
                        diag['turnover'] = 0.0
                        diag['transaction_cost'] = 0.0
                    else:
                        # First day or asset availability changed - must rebalance
                        available_returns_df = returns_df[available_assets]
                        available_regimes_df = regimes_df[[c for c in available_assets if c in regimes_df.columns]]
                        
                        mu, sigma = self.generate_mu_sigma(
                            date, regime_forecasts, available_returns_df, available_regimes_df, available_assets,
                            macro_features=macro_features
                        )
                        crisis_prob = (regime_forecasts == 2).mean()
                        
                        weights_subset, diag = self.optimize_daily(
                            regime_forecasts, mu, sigma, available_assets,
                            crisis_probability=crisis_prob,
                            regime_probabilities=None
                        )
                        diag['rebalanced'] = True
                        
                        last_rebalance_date = date
                        previous_weights = weights_subset.copy()
                        previous_diag = diag.copy()
                
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
                    
                    # Step 1: Risky asset return (weighted sum)
                    risky_return = np.nansum(weights * next_returns)
                    
                    # Step 2: Add cash return (cash earns risk-free rate)
                    cash_weight = diag.get('cash_allocation', 0.0)
                    rf_daily = 0.0
                    if risk_free_rate is not None and next_date in risk_free_rate.index:
                        rf_val = risk_free_rate.loc[next_date]
                        if pd.notna(rf_val) and np.isfinite(rf_val):
                            rf_daily = rf_val
                    
                    cash_return = cash_weight * rf_daily
                    total_return = risky_return + cash_return
                    
                    # Step 3: Compute EXCESS return (subtract benchmark = 100% RF)
                    # Excess return = what we earned - what we'd earn holding 100% cash
                    excess_return = total_return - rf_daily
                    
                    # Step 4: Deduct transaction costs (these are real costs)
                    transaction_cost = diag.get('transaction_cost', 0.0)
                    net_excess_return = excess_return - transaction_cost
                    
                    returns_history.append({
                        'date': next_date,
                        'return': net_excess_return if np.isfinite(net_excess_return) else 0.0,
                        'total_return': total_return if np.isfinite(total_return) else 0.0,
                        'transaction_cost': transaction_cost,
                        'rf_daily': rf_daily
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
        
        # =========================================================================
        # SOLVER HEALTH SUMMARY - Log optimization failures for methodology audit
        # =========================================================================
        if len(diagnostics_df) > 0 and 'solver_converged' in diagnostics_df.columns:
            n_days = len(diagnostics_df)
            n_converged = diagnostics_df['solver_converged'].sum()
            n_failed = n_days - n_converged
            failure_rate = n_failed / n_days * 100 if n_days > 0 else 0
            
            if verbose and n_failed > 0:
                print(f"  SOLVER HEALTH: {n_converged}/{n_days} converged ({failure_rate:.1f}% fallback)")
                if failure_rate > 5.0:
                    print(f"  ⚠ WARNING: High solver failure rate may affect methodology validity")
        
        if len(diagnostics_df) > 0 and 'feasibility_warning' in diagnostics_df.columns:
            warnings = diagnostics_df['feasibility_warning'].dropna()
            if len(warnings) > 0 and verbose:
                print(f"  FEASIBILITY: {len(warnings)} days with constraint warnings")
        
        # =========================================================================
        # REBALANCING SUMMARY
        # =========================================================================
        if len(diagnostics_df) > 0 and 'rebalanced' in diagnostics_df.columns and verbose:
            n_days = len(diagnostics_df)
            n_rebalanced = diagnostics_df['rebalanced'].sum()
            print(f"  REBALANCING: {n_rebalanced}/{n_days} days ({self.rebalance_frequency})")
        
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
    """Backward-compatible wrapper for single-day optimization."""
    engine = PortfolioEngine(
        gamma_risk=gamma_risk,
        gamma_trade=gamma_trade,
        min_bullish_assets=min_bullish_assets,
        max_weight=max_weight,
        strategy=strategy
    )
    
    asset_names = [f"Asset_{i}" for i in range(len(regime_forecasts))]
    return engine.optimize_daily(regime_forecasts, expected_returns, covariance_matrix, asset_names)
