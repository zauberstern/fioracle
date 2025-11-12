"""
Pytest configuration and shared fixtures.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path


@pytest.fixture
def sample_data():
    """Create sample financial data for testing."""
    dates = pd.date_range('2000-01-01', '2010-12-31', freq='D')
    np.random.seed(42)
    
    data = pd.DataFrame({
        'gpr_index': np.random.randn(len(dates)).cumsum() + 100,
        'epu_index': np.random.randn(len(dates)).cumsum() + 50,
        'sp500': np.random.randn(len(dates)).cumsum() + 1000,
        'bond_10y': np.random.randn(len(dates)) * 0.1 + 3.0,
        'corp_aaa': np.random.randn(len(dates)) * 0.1 + 4.0,
        'corp_baa': np.random.randn(len(dates)) * 0.1 + 5.0,
    }, index=dates)
    
    return data


@pytest.fixture
def sample_returns():
    """Create sample return series for testing."""
    dates = pd.date_range('2000-01-01', '2010-12-31', freq='D')
    np.random.seed(42)
    
    returns = pd.DataFrame({
        'BOND_10Y': np.random.randn(len(dates)) * 0.01,
        'CORP_AAA': np.random.randn(len(dates)) * 0.012,
        'CORP_BAA': np.random.randn(len(dates)) * 0.015,
    }, index=dates)
    
    return returns


@pytest.fixture
def sample_features():
    """Create sample feature dataframe for testing."""
    dates = pd.date_range('2000-01-01', '2010-12-31', freq='D')
    np.random.seed(42)
    
    n_features = 18
    features = pd.DataFrame(
        np.random.randn(len(dates), n_features),
        index=dates,
        columns=[f'feature_{i}' for i in range(n_features)]
    )
    
    # Add return column
    features['return'] = np.random.randn(len(dates)) * 0.01
    
    return features


@pytest.fixture
def sample_regimes():
    """Create sample regime labels for testing."""
    dates = pd.date_range('2000-01-01', '2010-12-31', freq='D')
    np.random.seed(42)
    
    # Create regime series with some persistence
    regimes = pd.Series(0, index=dates)
    regime_changes = np.random.choice(len(dates), size=10, replace=False)
    
    for i, idx in enumerate(sorted(regime_changes)):
        regimes.iloc[idx:] = i % 2
    
    return regimes


@pytest.fixture
def sample_weights():
    """Create sample portfolio weights for testing."""
    dates = pd.date_range('2000-01-01', '2010-12-31', freq='D')
    np.random.seed(42)
    
    weights = pd.DataFrame({
        'BOND_10Y': np.random.random(len(dates)),
        'CORP_AAA': np.random.random(len(dates)),
        'CORP_BAA': np.random.random(len(dates)),
    }, index=dates)
    
    # Normalize to sum to 1
    weights = weights.div(weights.sum(axis=1), axis=0)
    
    return weights


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create temporary cache directory for testing."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def temp_config(tmp_path):
    """Create temporary config file for testing."""
    config_content = """
data:
  mode: basic
  start_date: '2000-01-01'
  end_date: '2010-12-31'
  cache_dir: 'data/cache'

regimes:
  jump_model:
    default_lambda: 5.0
  hmm:
    n_states: 3

portfolio:
  gamma_risk: 10.0
  gamma_trade: 1.0
  transaction_cost: 0.0005
  max_weight: 0.40
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return config_file
