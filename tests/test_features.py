"""
Unit tests for features module.
"""

import pytest
import pandas as pd
import numpy as np

from src.core.features import engineer_features, compute_asset_features, compute_macro_features


class TestEngineerFeatures:
    """Tests for main feature engineering function."""
    
    def test_engineer_features_basic(self, sample_data):
        """Test basic feature engineering."""
        asset_features, macro_features = engineer_features(sample_data, complexity='basic')
        
        # Check we got outputs
        assert isinstance(asset_features, dict)
        assert isinstance(macro_features, pd.DataFrame)
        
        # Check macro features
        assert len(macro_features) > 0
        assert macro_features.shape[1] >= 3  # At least 3 macro features
    
    def test_engineer_features_output_structure(self, sample_data):
        """Test output structure of engineered features."""
        asset_features, macro_features = engineer_features(sample_data, complexity='basic')
        
        # Each asset should have features
        for asset, features in asset_features.items():
            assert isinstance(features, pd.DataFrame)
            assert len(features) > 0
            # Should have multiple features per asset
            assert features.shape[1] >= 10
    
    def test_engineer_features_index_alignment(self, sample_data):
        """Test that feature indices are aligned with input data."""
        asset_features, macro_features = engineer_features(sample_data, complexity='basic')
        
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
            features = compute_asset_features(returns, lookback=252)
            
            # Should have multiple features
            assert isinstance(features, pd.DataFrame)
            assert features.shape[1] > 0
            # Should have same or fewer rows (due to lookback)
            assert len(features) <= len(returns)
    
    def test_compute_asset_features_contains_return(self, sample_returns):
        """Test that asset features include return column."""
        returns = sample_returns.iloc[:, 0]
        features = compute_asset_features(returns)
        
        assert 'return' in features.columns
    
    def test_compute_asset_features_no_nans_in_main_features(self, sample_returns):
        """Test that main features don't have excessive NaNs."""
        returns = sample_returns.iloc[:, 0]
        features = compute_asset_features(returns, lookback=252)
        
        # After initial lookback period, should have valid features
        features_after_warmup = features.iloc[252:]
        
        # Most features should be non-NaN after warmup
        for col in features_after_warmup.columns:
            nan_pct = features_after_warmup[col].isna().sum() / len(features_after_warmup)
            assert nan_pct < 0.5, f"Feature {col} has {nan_pct*100:.1f}% NaN values"
    
    def test_compute_asset_features_volatility_positive(self, sample_returns):
        """Test that volatility features are positive."""
        returns = sample_returns.iloc[:, 0]
        features = compute_asset_features(returns)
        
        # Find volatility-related columns
        vol_cols = [c for c in features.columns if 'vol' in c.lower() or 'std' in c.lower()]
        
        for col in vol_cols:
            valid_values = features[col].dropna()
            assert (valid_values >= 0).all(), f"{col} has negative values"


class TestComputeMacroFeatures:
    """Tests for macro feature computation."""
    
    def test_compute_macro_features_basic(self, sample_data):
        """Test basic macro feature computation."""
        macro_features = compute_macro_features(sample_data, complexity='basic')
        
        assert isinstance(macro_features, pd.DataFrame)
        assert len(macro_features) > 0
        assert macro_features.shape[1] >= 3
    
    def test_compute_macro_features_index_alignment(self, sample_data):
        """Test that macro features are aligned with input."""
        macro_features = compute_macro_features(sample_data)
        
        # Index should be subset of input data
        assert macro_features.index.isin(sample_data.index).all()
    
    def test_compute_macro_features_no_infinite_values(self, sample_data):
        """Test that macro features don't contain infinite values."""
        macro_features = compute_macro_features(sample_data)
        
        for col in macro_features.columns:
            assert not np.isinf(macro_features[col]).any(), f"{col} contains infinite values"


class TestFeatureEngineering:
    """Integration tests for feature engineering."""
    
    def test_features_with_minimal_data(self):
        """Test feature engineering with minimal data."""
        # Create minimal dataset
        dates = pd.date_range('2000-01-01', '2000-12-31', freq='D')
        data = pd.DataFrame({
            'gpr_index': np.random.randn(len(dates)) + 100,
            'epu_index': np.random.randn(len(dates)) + 50,
            'bond_10y': np.random.randn(len(dates)) * 0.1 + 3.0,
        }, index=dates)
        
        asset_features, macro_features = engineer_features(data, complexity='basic')
        
        # Should still produce outputs
        assert len(asset_features) > 0
        assert len(macro_features) > 0
    
    def test_features_handle_missing_data(self):
        """Test that feature engineering handles missing data gracefully."""
        dates = pd.date_range('2000-01-01', '2010-12-31', freq='D')
        np.random.seed(42)
        
        data = pd.DataFrame({
            'gpr_index': np.random.randn(len(dates)) + 100,
            'epu_index': np.random.randn(len(dates)) + 50,
            'bond_10y': np.random.randn(len(dates)) * 0.1 + 3.0,
        }, index=dates)
        
        # Introduce some NaN values
        data.loc[data.index[10:20], 'gpr_index'] = np.nan
        
        asset_features, macro_features = engineer_features(data, complexity='basic')
        
        # Should still work despite NaNs
        assert len(asset_features) > 0
        assert len(macro_features) > 0
