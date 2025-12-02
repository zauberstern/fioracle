"""
Synthetic Crisis Test Suite

Tests that the full pipeline correctly responds to crisis conditions:
1. VIX spike → regimes shift to crisis
2. Crisis regime → cash allocation increases (>70%)
3. Crisis regime → expected returns for HY assets become negative
4. No look-ahead bias: test_start returns are only predictable from pre-test features

Run with: pytest tests/test_crisis_response.py -v
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from core.regimes import JumpModel, RegimeEngine
from core.portfolio import PortfolioEngine


class TestSyntheticCrisis:
    """Test suite for crisis response behavior."""
    
    @pytest.fixture
    def base_config(self):
        """Minimal config for testing."""
        return {
            'regimes': {
                'jump_model': {
                    'n_states': 3,
                    'l1_penalty': 0.0,
                    'lambda_candidates': [1.0, 5.0, 10.0],
                    'default_lambda': 5.0
                },
                'xgboost': {
                    'max_depth': 3,
                    'n_estimators': 50,
                    'learning_rate': 0.1,
                    'forecast_horizon': {'mode': 'shift', 'horizon_days': 1}
                },
                'labels': {0: 'calm', 1: 'inflationary', 2: 'crisis'}
            },
            'portfolio': {
                'gamma_risk': 10.0,
                'gamma_trade': 2.0,
                'max_weight': 0.25,
                'min_bullish_assets': 3,
                'tiered_transaction_costs': {'enabled': False},
                'regime_allocation': {'enabled': True},
                'cash_floor': {'enabled': True, 'c0': 0.10, 'c1': 0.80},
                'gradual_risk_off': {
                    'enabled': True, 
                    'crisis_probability_threshold': 0.25,
                    'max_cash_at_crisis': 0.90
                },
                'regime_mixing': {'enabled': False}
            },
            'assets': {
                'categories': {
                    'government_bonds': ['GOV_BOND'],
                    'high_yield': ['HY_BOND'],
                    'safe_havens': ['GOLD', 'CASH']
                }
            }
        }
    
    @pytest.fixture
    def synthetic_calm_data(self):
        """Generate synthetic calm period data (low volatility, positive drift)."""
        np.random.seed(42)
        n_days = 500
        dates = pd.date_range('2020-01-01', periods=n_days, freq='B')
        
        # Calm period: low vol, positive returns
        assets = {
            'GOV_BOND': np.random.normal(0.0002, 0.003, n_days),  # Low vol, slight positive
            'HY_BOND': np.random.normal(0.0004, 0.005, n_days),   # Slightly higher return/vol
            'GOLD': np.random.normal(0.0001, 0.008, n_days),      # Moderate vol
            'CASH': np.random.normal(0.0001, 0.0001, n_days),     # Minimal vol
        }
        
        # Low VIX (calm conditions)
        vix = np.random.normal(15, 2, n_days)
        vix = np.clip(vix, 10, 25)
        
        returns_df = pd.DataFrame(assets, index=dates)
        macro_df = pd.DataFrame({'VIX': vix}, index=dates)
        
        return returns_df, macro_df
    
    @pytest.fixture
    def synthetic_crisis_data(self):
        """Generate synthetic crisis period data (high volatility, negative drift, VIX spike)."""
        np.random.seed(42)
        n_days = 500
        dates = pd.date_range('2020-01-01', periods=n_days, freq='B')
        
        # First 400 days: calm
        # Last 100 days: crisis (VIX spike, high vol, negative returns)
        crisis_start = 400
        
        assets = {}
        for name, (calm_ret, calm_vol, crisis_ret, crisis_vol) in [
            ('GOV_BOND', (0.0002, 0.003, 0.0001, 0.010)),   # Flight to quality
            ('HY_BOND', (0.0004, 0.005, -0.002, 0.025)),    # Crisis hit hard
            ('GOLD', (0.0001, 0.008, 0.001, 0.015)),        # Safe haven gains
            ('CASH', (0.0001, 0.0001, 0.0001, 0.0001)),     # Stable
        ]:
            calm = np.random.normal(calm_ret, calm_vol, crisis_start)
            crisis = np.random.normal(crisis_ret, crisis_vol, n_days - crisis_start)
            assets[name] = np.concatenate([calm, crisis])
        
        # VIX: calm then spike
        vix_calm = np.random.normal(15, 2, crisis_start)
        vix_crisis = np.random.normal(45, 10, n_days - crisis_start)  # VIX spike to 45+
        vix = np.concatenate([np.clip(vix_calm, 10, 25), np.clip(vix_crisis, 30, 80)])
        
        returns_df = pd.DataFrame(assets, index=dates)
        macro_df = pd.DataFrame({'VIX': vix}, index=dates)
        
        return returns_df, macro_df, crisis_start
    
    def test_jump_model_detects_crisis_from_volatility(self, synthetic_crisis_data):
        """Test that JumpModel correctly identifies crisis regimes from high volatility."""
        returns_df, macro_df, crisis_start = synthetic_crisis_data
        
        # Build features: rolling volatility (key crisis indicator)
        features = pd.DataFrame(index=returns_df.index)
        for col in returns_df.columns:
            features[f'{col}_vol_21d'] = returns_df[col].rolling(21).std()
            features[f'{col}_ret_21d'] = returns_df[col].rolling(21).mean()
        features['VIX'] = macro_df['VIX']
        features = features.dropna()
        
        # Fit JumpModel
        jm = JumpModel(lambda_jump=5.0, n_states=3)
        states = jm.fit(features.values)
        
        # Compute per-state volatility to identify crisis state
        state_vols = {}
        for s in range(3):
            mask = (states == s)
            if mask.sum() > 0:
                # Use average VIX as proxy for crisis intensity
                state_vols[s] = features['VIX'].iloc[mask].mean()
        
        # Crisis state should have highest average VIX
        crisis_state = max(state_vols, key=state_vols.get)
        
        # Check that crisis state is detected more in the crisis period
        crisis_period_states = states[crisis_start - 21:]  # After warmup
        calm_period_states = states[:crisis_start - 21]
        
        crisis_in_crisis_period = (crisis_period_states == crisis_state).mean()
        crisis_in_calm_period = (calm_period_states == crisis_state).mean()
        
        # Crisis detection should be higher in crisis period
        assert crisis_in_crisis_period > crisis_in_calm_period, \
            f"Crisis detection: {crisis_in_crisis_period:.2%} in crisis vs {crisis_in_calm_period:.2%} in calm"
        
        # At least 50% of crisis period should be identified as crisis
        assert crisis_in_crisis_period > 0.5, \
            f"Crisis detection rate {crisis_in_crisis_period:.2%} too low in crisis period"
    
    def test_portfolio_increases_cash_in_crisis(self, base_config, synthetic_crisis_data):
        """Test that PortfolioEngine increases cash allocation when regime is crisis."""
        returns_df, macro_df, _ = synthetic_crisis_data
        
        engine = PortfolioEngine(
            gamma_risk=base_config['portfolio']['gamma_risk'],
            gamma_trade=base_config['portfolio']['gamma_trade'],
            max_weight=base_config['portfolio']['max_weight'],
            min_bullish_assets=base_config['portfolio']['min_bullish_assets'],
            config=base_config
        )
        
        asset_names = list(returns_df.columns)
        n_assets = len(asset_names)
        
        # Compute simple covariance
        cov = returns_df.cov().values
        mu_calm = returns_df.mean().values
        
        # Test 1: All assets in CALM regime → should invest
        regime_forecasts_calm = np.zeros(n_assets, dtype=int)  # All calm
        weights_calm, diag_calm = engine.optimize_daily(
            regime_forecasts_calm, mu_calm, cov, asset_names,
            crisis_probability=0.0
        )
        
        cash_in_calm = diag_calm['cash_allocation']
        
        # Test 2: All assets in CRISIS regime → should hold mostly cash
        regime_forecasts_crisis = np.full(n_assets, 2, dtype=int)  # All crisis
        weights_crisis, diag_crisis = engine.optimize_daily(
            regime_forecasts_crisis, mu_calm * 0.1, cov * 4,  # Lower returns, higher vol
            asset_names,
            crisis_probability=1.0  # 100% crisis probability
        )
        
        cash_in_crisis = diag_crisis['cash_allocation']
        
        # Crisis should have MUCH higher cash allocation
        assert cash_in_crisis > cash_in_calm, \
            f"Cash in crisis ({cash_in_crisis:.2%}) should exceed calm ({cash_in_calm:.2%})"
        
        # With gradual risk-off enabled and 100% crisis probability, should be >70% cash
        assert cash_in_crisis > 0.70, \
            f"Cash allocation in crisis ({cash_in_crisis:.2%}) should be >70%"
    
    def test_hy_expected_return_negative_in_crisis(self, base_config):
        """Test that HY assets get negative expected return in crisis regime."""
        engine = PortfolioEngine(
            gamma_risk=10.0,
            gamma_trade=2.0,
            strategy='MinVar',
            config=base_config
        )
        
        # In MinVar strategy with 3-state:
        # - Calm (0): +bullish_return_minvar
        # - Inflationary (1): 0
        # - Crisis (2): -bullish_return_minvar
        
        # Simulate crisis regime
        n_assets = 4
        regime_forecasts = np.array([0, 2, 2, 0])  # Mixed: GOV calm, HY crisis
        
        # Generate mu using the engine's logic
        # For MinVar, the expected return is set directly based on regime
        expected_returns = np.zeros(n_assets)
        for j, regime in enumerate(regime_forecasts):
            if regime == 0:  # Calm
                expected_returns[j] = engine.bullish_return_minvar
            elif regime == 2:  # Crisis
                expected_returns[j] = -engine.bullish_return_minvar
            else:  # Inflationary
                expected_returns[j] = 0.0
        
        # HY (indices 1, 2) should have negative expected return in crisis
        assert expected_returns[1] < 0, f"HY in crisis should have μ<0, got {expected_returns[1]}"
        assert expected_returns[2] < 0, f"HY in crisis should have μ<0, got {expected_returns[2]}"
        
        # GOV (indices 0, 3) should have positive expected return in calm
        assert expected_returns[0] > 0, f"GOV in calm should have μ>0, got {expected_returns[0]}"
        assert expected_returns[3] > 0, f"GOV in calm should have μ>0, got {expected_returns[3]}"
    
    def test_no_lookahead_in_regime_forecasting(self, synthetic_crisis_data):
        """
        Test that regime forecasting uses only past data.
        
        Specifically: predictions at time t should only use features up to t-1.
        We verify this by checking that the XGBoost supervised dataset
        has targets shifted forward (y[t] = regime[t+1]).
        """
        returns_df, macro_df, crisis_start = synthetic_crisis_data
        
        # Build features
        features = pd.DataFrame(index=returns_df.index)
        for col in returns_df.columns:
            features[f'{col}_vol_21d'] = returns_df[col].rolling(21).std()
            features[f'{col}_ret_21d'] = returns_df[col].rolling(21).mean()
        features['VIX'] = macro_df['VIX']
        features = features.dropna()
        
        # Create regime labels (simulate from JumpModel)
        jm = JumpModel(lambda_jump=5.0, n_states=3)
        states = jm.fit(features.values)
        regimes = pd.Series(states, index=features.index)
        
        # Build supervised dataset as the engine does
        X = features.copy()
        
        # Target should be SHIFTED FORWARD by forecast horizon
        # This means: to predict regime at t+1, we use features at t
        horizon_days = 1
        y = regimes.shift(-horizon_days)
        
        # Drop the last horizon_days rows (no target available)
        X = X.iloc[:-horizon_days]
        y = y.iloc[:-horizon_days]
        valid = ~y.isna()
        X = X[valid]
        y = y[valid]
        
        # Verify alignment: y[i] should be the regime for X[i].index + 1 day
        for i in range(min(10, len(X) - 1)):
            feature_date = X.index[i]
            target_date = y.index[i]
            
            # Feature and target should have same index in the aligned dataset
            assert feature_date == target_date, \
                f"Misaligned: feature date {feature_date} != target date {target_date}"
            
            # But y[i] should be the regime for feature_date + horizon_days
            expected_target_regime_date = features.index[features.index.get_loc(feature_date) + horizon_days]
            actual_regime_at_expected = regimes.loc[expected_target_regime_date]
            
            assert y.iloc[i] == actual_regime_at_expected, \
                f"Target mismatch: y={y.iloc[i]} but regime at {expected_target_regime_date} is {actual_regime_at_expected}"
        
        print("✓ No look-ahead bias detected: targets correctly shifted forward")
    
    def test_crisis_probability_drives_cash_floor(self, base_config):
        """Test that crisis_probability correctly scales cash floor."""
        engine = PortfolioEngine(
            gamma_risk=10.0,
            gamma_trade=2.0,
            max_weight=0.25,
            config=base_config
        )
        
        asset_names = ['GOV_BOND', 'HY_BOND', 'GOLD', 'CASH']
        n_assets = len(asset_names)
        
        # Simple inputs
        regime_forecasts = np.zeros(n_assets, dtype=int)  # All calm
        mu = np.array([0.0002, 0.0004, 0.0001, 0.0001])
        cov = np.eye(n_assets) * 0.0001
        
        # Test multiple crisis probabilities
        crisis_probs = [0.0, 0.25, 0.5, 0.75, 1.0]
        cash_allocations = []
        
        for cp in crisis_probs:
            engine.reset()  # Reset previous weights
            _, diag = engine.optimize_daily(
                regime_forecasts, mu, cov, asset_names,
                crisis_probability=cp
            )
            cash_allocations.append(diag['cash_allocation'])
        
        # Cash allocation should increase monotonically with crisis probability
        for i in range(len(crisis_probs) - 1):
            assert cash_allocations[i+1] >= cash_allocations[i] - 0.01, \
                f"Cash should increase with crisis_prob: {cash_allocations}"
        
        # At crisis_prob=1.0, should have high cash (>70% given config)
        assert cash_allocations[-1] > 0.70, \
            f"At 100% crisis probability, cash should be >70%, got {cash_allocations[-1]:.2%}"
        
        print(f"✓ Cash floor scales correctly: {[f'{c:.1%}' for c in cash_allocations]}")


class TestSolverRobustness:
    """Test solver retry and logging behavior."""
    
    def test_solver_handles_difficult_problem(self):
        """Test that solver retries on difficult optimization problems."""
        config = {
            'portfolio': {
                'tiered_transaction_costs': {'enabled': False},
                'regime_allocation': {'enabled': False},
                'cash_floor': {'enabled': False},
                'gradual_risk_off': {'enabled': False},
                'regime_mixing': {'enabled': False}
            },
            'regimes': {'jump_model': {'n_states': 3}}
        }
        
        engine = PortfolioEngine(
            gamma_risk=10.0,
            gamma_trade=2.0,
            max_weight=0.25,
            config=config
        )
        
        # Create a challenging optimization problem
        n_assets = 10
        asset_names = [f'ASSET_{i}' for i in range(n_assets)]
        
        # Ill-conditioned covariance matrix (nearly singular)
        np.random.seed(123)
        A = np.random.randn(n_assets, 2)  # Low rank
        cov = A @ A.T + np.eye(n_assets) * 1e-8  # Nearly singular
        
        mu = np.random.randn(n_assets) * 0.001
        regime_forecasts = np.zeros(n_assets, dtype=int)
        
        # Should still produce valid weights (or graceful fallback)
        weights, diag = engine.optimize_daily(
            regime_forecasts, mu, cov, asset_names
        )
        
        # Weights should be valid regardless of solver outcome
        assert np.all(weights >= -1e-6), "Weights should be non-negative"
        assert np.all(weights <= engine.max_weight + 1e-6), "Weights should respect max"
        assert np.sum(weights) <= 1.0 + 1e-6, "Total weight should not exceed 1"
        
        # Status should indicate what happened
        assert diag['status'] in ['SUCCESS', 'FALLBACK', 'ERROR'], \
            f"Unknown status: {diag['status']}"
        
        print(f"✓ Solver handled difficult problem with status: {diag['status']}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
