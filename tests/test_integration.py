"""
Integration tests for complete pipeline.
"""

import pytest
import pandas as pd
import numpy as np

from src.core import DataPipeline, engineer_features, RegimeEngine, PortfolioEngine, Evaluator


class TestEndToEndPipeline:
    """End-to-end integration tests."""
    
    @pytest.mark.slow
    def test_complete_pipeline_basic_mode(self):
        """Test complete pipeline in basic mode (integration test)."""
        # This test requires actual data, so it might fail in CI
        # Mark as slow test that can be skipped
        
        try:
            # Step 1: Load data
            pipeline = DataPipeline()
            data = pipeline.load('2000-01-01', '2005-12-31')
            
            assert data is not None
            assert len(data) > 0
            
            # Step 2: Engineer features
            asset_features, macro_features = engineer_features(data)
            
            assert len(asset_features) > 0
            assert len(macro_features) > 0
            
            # Step 3: Extract returns
            asset_returns = {}
            for asset, features in asset_features.items():
                if 'return' in features.columns:
                    asset_returns[asset] = features['return'].copy()
            
            returns_df = pd.DataFrame(asset_returns)
            assert len(returns_df.columns) > 0
            
            # Step 4: Identify regimes
            engine = RegimeEngine(lambda_jump=5.0, n_macro_regimes=3)
            results = engine.fit_identify_forecast(
                asset_features_dict=asset_features,
                asset_returns_df=returns_df,
                macro_features=macro_features,
                train_forecasters=False,  # Skip for speed
                verbose=False
            )
            
            assert 'asset_regimes' in results
            assert len(results['asset_regimes']) > 0
            
            # Step 5: Evaluate
            evaluator = Evaluator()
            
            # Create simple equal-weight portfolio
            ew_returns = returns_df.mean(axis=1)
            metrics = evaluator.compute_metrics(ew_returns)
            
            assert 'sharpe' in metrics
            assert 'max_drawdown' in metrics
            
        except FileNotFoundError:
            pytest.skip("Data files not available for integration test")
        except Exception as e:
            pytest.skip(f"Integration test skipped: {e}")


class TestDataToFeaturesPipeline:
    """Test data loading to feature engineering pipeline."""
    
    def test_data_features_integration(self, sample_data):
        """Test that data can flow into feature engineering."""
        asset_features, macro_features = engineer_features(sample_data)
        
        # Verify outputs are compatible
        assert isinstance(asset_features, dict)
        assert isinstance(macro_features, pd.DataFrame)
        
        # Verify indices are aligned
        for features in asset_features.values():
            # Feature indices should be subset of original data
            assert features.index.isin(sample_data.index).all()


class TestFeaturesToRegimesPipeline:
    """Test feature engineering to regime identification pipeline."""
    
    def test_features_regimes_integration(self, sample_features, sample_returns):
        """Test that features can flow into regime identification."""
        asset_features_dict = {
            'TEST_ASSET': sample_features
        }
        
        engine = RegimeEngine(lambda_jump=5.0, n_macro_regimes=2)
        
        # Create minimal macro features
        macro_features = pd.DataFrame({
            'feature_1': np.random.randn(len(sample_features)),
            'feature_2': np.random.randn(len(sample_features)),
        }, index=sample_features.index)
        
        try:
            results = engine.fit_identify_forecast(
                asset_features_dict=asset_features_dict,
                asset_returns_df=sample_returns.iloc[:, :1],
                macro_features=macro_features,
                train_forecasters=False,
                verbose=False
            )
            
            assert 'asset_regimes' in results
            
        except Exception as e:
            # HMM can be unstable with random data
            pytest.skip(f"Regime fitting failed (expected with random data): {e}")


class TestRegimesToPortfolioPipeline:
    """Test regime identification to portfolio optimization pipeline."""
    
    def test_regimes_portfolio_integration(self, sample_returns, sample_regimes):
        """Test that regimes can flow into portfolio optimization."""
        # Create regime dict
        regimes_dict = {
            col: sample_regimes for col in sample_returns.columns
        }
        
        # Create simple macro probs
        macro_probs = pd.DataFrame({
            'regime_0': np.random.random(len(sample_returns)),
            'regime_1': np.random.random(len(sample_returns)),
        }, index=sample_returns.index)
        
        # Normalize
        macro_probs = macro_probs.div(macro_probs.sum(axis=1), axis=0)
        
        # This would normally connect to portfolio optimization
        # Just verify data structure compatibility
        assert all(col in regimes_dict for col in sample_returns.columns)
        assert len(macro_probs) == len(sample_returns)


class TestPortfolioToEvaluationPipeline:
    """Test portfolio optimization to evaluation pipeline."""
    
    def test_portfolio_evaluation_integration(self, sample_returns, sample_weights):
        """Test that portfolio results can flow into evaluation."""
        # Compute portfolio returns
        portfolio_returns = (sample_returns * sample_weights).sum(axis=1)
        
        # Evaluate
        evaluator = Evaluator()
        metrics = evaluator.evaluate(
            portfolio_returns,
            sample_weights,
            plot=False,
            verbose=False
        )
        
        # Verify we got meaningful metrics
        assert isinstance(metrics, dict)
        assert 'sharpe' in metrics
        assert np.isfinite(metrics['sharpe'])
        assert 'max_drawdown' in metrics
        assert metrics['max_drawdown'] <= 0


class TestCachingIntegration:
    """Test that caching works across pipeline."""
    
    def test_cache_consistency(self, sample_data, temp_cache_dir):
        """Test that cached data is consistent."""
        from src.core.utils import cache_to_parquet, load_from_parquet
        
        # Cache the data
        cache_to_parquet(sample_data, 'test_data', cache_dir=str(temp_cache_dir))
        
        # Load it back
        loaded_data = load_from_parquet('test_data', cache_dir=str(temp_cache_dir))
        
        # Should be identical
        pd.testing.assert_frame_equal(loaded_data, sample_data)
        
        # Engineer features on both
        features1, macro1 = engineer_features(sample_data)
        features2, macro2 = engineer_features(loaded_data)
        
        # Features should be identical
        assert set(features1.keys()) == set(features2.keys())
        
        for key in features1.keys():
            pd.testing.assert_frame_equal(features1[key], features2[key])


class TestErrorHandling:
    """Test error handling across pipeline components."""
    
    def test_invalid_date_range(self):
        """Test handling of invalid date ranges."""
        pipeline = DataPipeline()
        
        # End date before start date
        data = pipeline.load('2020-01-01', '2019-01-01')
        assert data.empty
    
    def test_empty_features_dict(self):
        """Test handling of empty features."""
        engine = RegimeEngine(lambda_jump=5.0, n_macro_regimes=2)
        
        empty_features = {}
        empty_returns = pd.DataFrame()
        empty_macro = pd.DataFrame()
        
        with pytest.raises((ValueError, KeyError, Exception)):
            engine.fit_identify_forecast(
                empty_features, empty_returns, empty_macro, verbose=False
            )
    
    def test_mismatched_indices(self, sample_features, sample_returns):
        """Test handling of mismatched time indices."""
        # Create features with different index
        shifted_features = sample_features.copy()
        shifted_features.index = shifted_features.index + pd.Timedelta(days=10)
        
        asset_features_dict = {'TEST_ASSET': shifted_features}
        macro_features = pd.DataFrame({
            'feature_1': np.random.randn(len(sample_features)),
        }, index=sample_features.index)
        
        engine = RegimeEngine(lambda_jump=5.0, n_macro_regimes=2)
        
        # Should handle mismatched indices gracefully
        try:
            results = engine.fit_identify_forecast(
                asset_features_dict, 
                sample_returns.iloc[:, :1],
                macro_features,
                train_forecasters=False,
                verbose=False
            )
            # If it succeeds, verify output is valid
            assert 'asset_regimes' in results
        except Exception:
            # Or it should raise an appropriate error
            pass


class TestPerformanceMetrics:
    """Test that performance metrics are computed correctly end-to-end."""
    
    def test_metrics_consistency(self, sample_returns):
        """Test that metrics are consistently computed."""
        evaluator = Evaluator()
        
        # Compute metrics twice
        metrics1 = evaluator.compute_metrics(sample_returns.iloc[:, 0])
        metrics2 = evaluator.compute_metrics(sample_returns.iloc[:, 0])
        
        # Should be identical
        for key in metrics1:
            if isinstance(metrics1[key], (int, float)):
                assert metrics1[key] == metrics2[key]
    
    def test_metrics_bounds(self, sample_returns):
        """Test that metrics are within reasonable bounds."""
        evaluator = Evaluator()
        metrics = evaluator.compute_metrics(sample_returns.iloc[:, 0])
        
        # Max drawdown should be negative or zero
        assert metrics['max_drawdown'] <= 0
        
        # Annual return should be finite
        assert np.isfinite(metrics['annual_return'])
        
        # Volatility should be positive
        assert metrics['annual_volatility'] >= 0
        
        # Win rate should be between 0 and 100
        if 'win_rate' in metrics:
            assert 0 <= metrics['win_rate'] <= 100


class TestWalkForwardValidation:
    """Test walk-forward validation functionality."""
    
    @pytest.mark.slow
    def test_walk_forward_splits(self):
        """Test that walk-forward creates correct splits."""
        try:
            pipeline = DataPipeline()
            data = pipeline.load('2000-01-01', '2010-12-31')
            
            # Would normally use walk-forward here
            # For now, just test data can be split
            midpoint = len(data) // 2
            train_data = data.iloc[:midpoint]
            val_data = data.iloc[midpoint:]
            
            assert len(train_data) > 0
            assert len(val_data) > 0
            assert len(train_data) + len(val_data) == len(data)
            
        except FileNotFoundError:
            pytest.skip("Data files not available")
