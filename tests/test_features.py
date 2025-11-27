"""
Unit tests for features module.
"""

import pytest
import pandas as pd
import numpy as np

from src.core.features import engineer_features, compute_asset_features

EXPECTED_ASSET_FEATURE_COLUMNS = {
    'avg_return_hl5',
    'avg_return_hl10',
    'avg_return_hl21',
    'log_dd_hl5',
    'log_dd_hl21',
    'sortino_hl5',
    'sortino_hl10',
    'sortino_hl21',
}

EXPECTED_MACRO_FEATURE_COLUMNS = {
    'vix_logdiff_ewma_63d',
    'epu_logdiff_ewma_21d',
    'globalization_logdiff_ewma_21d',
    'economic_freedom_logdiff_ewma_21d',
    'broad_money_logdiff_ewma_63d',
    'debt_to_gdp_ratio',
    'daily_inflation_rate',
    'unemployment_rate',
    'gdp_growth_rate',
    'yield_2y_change',
    'yield_2y_change_ewma_21d',
    'yield_curve_slope_ewma_10d',
    'yield_curve_slope_change_ewma_21d',
    'stock_bond_corr_252d',
}


class TestEngineerFeatures:
    """Tests for main feature engineering function."""
    
    def test_engineer_features_basic(self, sample_data):
        """Test basic feature engineering."""
        asset_features, macro_features = engineer_features(sample_data)
        
        # Check we got outputs
        assert isinstance(asset_features, dict)
        assert isinstance(macro_features, pd.DataFrame)
        
        # Check macro features
        assert set(macro_features.columns) == EXPECTED_MACRO_FEATURE_COLUMNS
        assert macro_features.notna().any().all()
    
    def test_engineer_features_output_structure(self, sample_data):
        """Test output structure of engineered features."""
        asset_features, macro_features = engineer_features(sample_data)
        
        # Each asset should have features
        for asset, features in asset_features.items():
            assert isinstance(features, pd.DataFrame)
            assert len(features) > 0
            assert set(features.columns) == EXPECTED_ASSET_FEATURE_COLUMNS
    
    def test_engineer_features_index_alignment(self, sample_data):
        """Test that feature indices are aligned with input data."""
        asset_features, macro_features = engineer_features(sample_data)
        
        # Macro features index should be subset of input data index
        assert macro_features.index.isin(sample_data.index).all()
        
        # Each asset features index should be aligned
        for features in asset_features.values():
            assert features.index.isin(sample_data.index).all()


class TestComputeAssetFeatures:
    """Tests for asset feature computation."""
    
    def test_compute_asset_features_shape(self, sample_returns):
        """Test that asset features have expected shape."""
        for col in sample_returns.columns:
            returns = sample_returns[col]
            features = compute_asset_features(returns)
            
            assert isinstance(features, pd.DataFrame)
            assert set(features.columns) == EXPECTED_ASSET_FEATURE_COLUMNS
            assert len(features) == len(returns)
    
    def test_compute_asset_features_contains_expected_features(self, sample_returns):
        """Test that asset features include the expected set."""
        returns = sample_returns.iloc[:, 0]
        features = compute_asset_features(returns)
        
        assert set(features.columns) == EXPECTED_ASSET_FEATURE_COLUMNS
    
    def test_compute_asset_features_no_nans_in_main_features(self, sample_returns):
        """Test that main features don't have excessive NaNs."""
        returns = sample_returns.iloc[:, 0]
        features = compute_asset_features(returns)
        
        for col in features.columns:
            valid = features[col].dropna()
            if len(valid) == 0:
                continue
            nan_pct = features[col].isna().mean()
            assert nan_pct < 0.5, f"{col} has too many NaNs"
    
    def test_compute_asset_features_standardized(self, sample_returns):
        """Test that features are standardized (zero mean)."""
        returns = sample_returns.iloc[:, 0]
        features = compute_asset_features(returns)
        
        for col in features.columns:
            valid = features[col].dropna()
            if valid.empty:
                continue
            mean_val = valid.mean()
            assert abs(mean_val) < 1e-6, f"{col} not centered"


class TestFeatureEngineering:
    """Integration tests for feature engineering."""
    
    def test_features_with_minimal_data(self):
        """Test feature engineering with minimal data."""
        # Create minimal dataset
        dates = pd.date_range('2000-01-01', '2000-12-31', freq='D')
        data = pd.DataFrame({
            'asset_us_10y_gov_bond': np.random.randn(len(dates)).cumsum() + 100,
            'asset_us_risk_free_rate': np.random.randn(len(dates)).cumsum() + 50,
            'macro_vix_close': np.abs(np.random.randn(len(dates)) + 20),
            'macro_epu_index': np.abs(np.random.randn(len(dates)) + 30),
            'macro_globalization_index': np.abs(np.random.randn(len(dates)) + 40),
            'macro_economic_freedom_index': np.abs(np.random.randn(len(dates)) + 6),
            'macro_us_broad_money_series': np.abs(np.random.randn(len(dates)) + 500),
            'macro_us_debt_to_gdp_ratio': np.abs(np.random.randn(len(dates)) + 60),
            'macro_us_cpi_level': np.abs(np.random.randn(len(dates)) + 200),
            'macro_us_unemployment': np.abs(np.random.randn(len(dates)) + 4),
            'macro_us_gdp_growth': np.random.randn(len(dates)) * 0.1,
        }, index=dates)
        
        asset_features, macro_features = engineer_features(data)
        
        # Should still produce outputs
        assert len(asset_features) > 0
        assert len(macro_features) > 0
    
    def test_features_handle_missing_data(self):
        """Test that feature engineering handles missing data gracefully."""
        dates = pd.date_range('2000-01-01', '2010-12-31', freq='D')
        np.random.seed(42)
        
        data = pd.DataFrame({
            'asset_us_10y_gov_bond': np.random.randn(len(dates)).cumsum() + 100,
            'asset_us_risk_free_rate': np.random.randn(len(dates)).cumsum() + 50,
            'macro_vix_close': np.abs(np.random.randn(len(dates)) + 20),
            'macro_epu_index': np.abs(np.random.randn(len(dates)) + 30),
            'macro_globalization_index': np.abs(np.random.randn(len(dates)) + 40),
            'macro_economic_freedom_index': np.abs(np.random.randn(len(dates)) + 6),
            'macro_us_broad_money_series': np.abs(np.random.randn(len(dates)) + 500),
            'macro_us_debt_to_gdp_ratio': np.abs(np.random.randn(len(dates)) + 60),
            'macro_us_cpi_level': np.abs(np.random.randn(len(dates)) + 200),
            'macro_us_unemployment': np.abs(np.random.randn(len(dates)) + 4),
            'macro_us_gdp_growth': np.random.randn(len(dates)) * 0.1,
        }, index=dates)
        
        # Introduce some NaN values
        data.loc[data.index[10:20], 'macro_epu_index'] = np.nan
        
        asset_features, macro_features = engineer_features(data)
        
        # Should still work despite NaNs
        assert len(asset_features) > 0
        assert len(macro_features) > 0
