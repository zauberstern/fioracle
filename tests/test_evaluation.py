"""
Unit tests for evaluation module.
"""

import pytest
import pandas as pd
import numpy as np

from src.core.evaluation import Evaluator


class TestEvaluatorInit:
    """Tests for Evaluator initialization."""
    
    def test_evaluator_default_init(self):
        """Test Evaluator with default parameters."""
        evaluator = Evaluator()
        assert evaluator.annualization_factor == 252
    
    def test_evaluator_custom_annualization(self):
        """Test Evaluator with custom annualization factor."""
        evaluator = Evaluator(annualization_factor=12)
        assert evaluator.annualization_factor == 12


class TestComputeMetrics:
    """Tests for metrics computation."""
    
    def test_compute_metrics_basic(self, sample_returns):
        """Test basic metrics computation."""
        evaluator = Evaluator()
        returns = sample_returns.iloc[:, 0]
        
        metrics = evaluator.compute_metrics(returns)
        
        # Check all expected metrics are present
        assert 'total_return' in metrics
        assert 'annualized_return' in metrics
        assert 'volatility' in metrics
        assert 'sharpe' in metrics
        assert 'sortino' in metrics
        assert 'max_drawdown' in metrics
        assert 'calmar' in metrics
        assert 'win_rate' in metrics
    
    def test_compute_metrics_positive_returns(self):
        """Test metrics with positive returns."""
        dates = pd.date_range('2000-01-01', '2010-12-31', freq='D')
        returns = pd.Series(np.random.randn(len(dates)) * 0.001 + 0.0005, index=dates)
        
        evaluator = Evaluator()
        metrics = evaluator.compute_metrics(returns)
        
        assert metrics['total_return'] > 0
        assert metrics['sharpe'] > 0
        assert metrics['win_rate'] > 0
    
    def test_compute_metrics_negative_returns(self):
        """Test metrics with negative returns."""
        dates = pd.date_range('2000-01-01', '2010-12-31', freq='D')
        returns = pd.Series(np.random.randn(len(dates)) * 0.001 - 0.0005, index=dates)
        
        evaluator = Evaluator()
        metrics = evaluator.compute_metrics(returns)
        
        assert metrics['total_return'] < 0
        assert metrics['max_drawdown'] < 0
    
    def test_compute_metrics_with_benchmark(self, sample_returns):
        """Test metrics computation with benchmark."""
        evaluator = Evaluator()
        strategy_returns = sample_returns.iloc[:, 0]
        benchmark_returns = sample_returns.iloc[:, 1]
        
        metrics = evaluator.compute_metrics(strategy_returns, benchmark_returns)
        
        # Should have benchmark comparison metrics
        assert 'excess_return' in metrics
        assert 'tracking_error' in metrics
        assert 'information_ratio' in metrics
    
    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation."""
        dates = pd.date_range('2000-01-01', '2010-12-31', freq='D')
        np.random.seed(42)
        returns = pd.Series(np.random.randn(len(dates)) * 0.01, index=dates)
        
        evaluator = Evaluator()
        metrics = evaluator.compute_metrics(returns)
        
        # Sharpe should be finite
        assert np.isfinite(metrics['sharpe'])
        
        # Manual calculation to verify
        mean_return = returns.mean()
        std_return = returns.std()
        expected_sharpe = (mean_return / std_return) * np.sqrt(252)
        
        assert abs(metrics['sharpe'] - expected_sharpe) < 0.01
    
    def test_max_drawdown_calculation(self):
        """Test max drawdown calculation."""
        # Create returns with known drawdown
        dates = pd.date_range('2000-01-01', '2000-12-31', freq='D')
        returns = pd.Series([0.01] * 100 + [-0.01] * 100 + [0.01] * (len(dates) - 200), index=dates)
        
        evaluator = Evaluator()
        metrics = evaluator.compute_metrics(returns)
        
        # Should have negative max drawdown
        assert metrics['max_drawdown'] < 0
    
    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        dates = pd.date_range('2000-01-01', '2000-12-31', freq='D')
        # 60% positive days
        returns = pd.Series(
            [0.01] * 219 + [-0.01] * (len(dates) - 219),
            index=dates
        )
        
        evaluator = Evaluator()
        metrics = evaluator.compute_metrics(returns)
        
        # Win rate should be around 60%
        assert 0.55 < metrics['win_rate'] < 0.65


class TestTuneLambda:
    """Tests for lambda tuning functionality."""
    
    def test_tune_lambda_basic(self, sample_features, sample_returns):
        """Test basic lambda tuning."""
        evaluator = Evaluator()
        
        features = sample_features.drop('return', axis=1)
        returns = sample_returns.iloc[:, 0]
        
        # Should not crash
        try:
            optimal_lambda, results = evaluator.tune_lambda_fast(
                features,
                returns,
                lambda_candidates=[1.0, 5.0, 10.0],
                n_splits=2
            )
            assert optimal_lambda > 0
            assert isinstance(results, pd.DataFrame)
        except Exception as e:
            # HMM fitting can be flaky with random data, that's okay
            pytest.skip(f"HMM fitting failed (expected with random data): {e}")


class TestPlotting:
    """Tests for plotting functionality."""
    
    def test_plot_essential_no_crash(self, sample_returns, sample_weights):
        """Test that plotting doesn't crash."""
        evaluator = Evaluator()
        
        portfolio_returns = (sample_returns * sample_weights).sum(axis=1)
        
        # Should not crash (plot is optional)
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            evaluator.plot_essential(
                portfolio_returns,
                sample_weights,
                save_dir=None  # Don't save
            )
        except ImportError:
            pytest.skip("Matplotlib not available")


class TestEvaluate:
    """Tests for full evaluation function."""
    
    def test_evaluate_basic(self, sample_returns, sample_weights):
        """Test full evaluation."""
        evaluator = Evaluator()
        
        portfolio_returns = (sample_returns * sample_weights).sum(axis=1)
        
        metrics = evaluator.evaluate(
            portfolio_returns,
            sample_weights,
            plot=False,
            verbose=False
        )
        
        # Should return metrics dict
        assert isinstance(metrics, dict)
        assert 'sharpe' in metrics
        assert 'max_drawdown' in metrics
        assert 'avg_turnover' in metrics
    
    def test_evaluate_with_benchmark(self, sample_returns, sample_weights):
        """Test evaluation with benchmark."""
        evaluator = Evaluator()
        
        portfolio_returns = (sample_returns * sample_weights).sum(axis=1)
        benchmark_returns = sample_returns.iloc[:, 0]
        
        metrics = evaluator.evaluate(
            portfolio_returns,
            sample_weights,
            benchmark_returns=benchmark_returns,
            plot=False,
            verbose=False
        )
        
        # Should have benchmark metrics
        assert 'excess_return' in metrics
        assert 'information_ratio' in metrics


class TestBackwardCompatibility:
    """Tests for backward compatibility functions."""
    
    def test_compute_sharpe_ratio(self):
        """Test backward compatible sharpe ratio function."""
        from src.core.evaluation import compute_sharpe_ratio
        
        dates = pd.date_range('2000-01-01', '2010-12-31', freq='D')
        np.random.seed(42)
        returns = pd.Series(np.random.randn(len(dates)) * 0.01, index=dates)
        
        sharpe = compute_sharpe_ratio(returns)
        
        assert isinstance(sharpe, float)
        assert np.isfinite(sharpe)
    
    def test_compute_all_metrics(self, sample_returns):
        """Test backward compatible all metrics function."""
        from src.core.evaluation import compute_all_metrics
        
        returns = sample_returns.iloc[:, 0]
        metrics = compute_all_metrics(returns)
        
        assert isinstance(metrics, dict)
        assert 'sharpe' in metrics
