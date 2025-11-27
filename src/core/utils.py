"""
Shared utilities: logging, config, and fast parquet caching.
"""

import logging
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
import warnings


def setup_logging(level: str = 'INFO') -> logging.Logger:
    """Configure logger and return instance."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger = logging.getLogger('fioracle')
    logger.setLevel(getattr(logging, level.upper()))
    
    return logger


def load_config(config_path: str = 'config/config.yaml') -> Dict[str, Any]:
    """Load YAML config file, returns defaults if missing."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        warnings.warn(f"Config not found: {config_path}. Using defaults.")
        return get_default_config()
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def get_default_config() -> Dict[str, Any]:
    """Fallback configuration if config.yaml not found."""
    return {
        'data': {
            'start_date': '1985-01-01',
            'end_date': '2025-11-12',
            'cache_dir': 'data/cache',
            'train_start': '1945-01-01',
            'train_end': '1977-05-06',
            'val_start': '1977-05-07',
            'val_end': '1993-07-08',
            'test_start': '1993-07-09',
            'test_end': '2025-11-12',
        },
        'assets': {
            'basic': ['SP500', 'BOND_10Y', 'CORP_AAA', 'CORP_BAA'],
            'full': ['SP500', 'BOND_10Y', 'CORP_AAA', 'CORP_BAA', 'AGG', 'LQD', 'HYG', 'TIP'],
        },
        'regimes': {
            'jump_model': {
                'lambda_candidates': [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0],
                'default_lambda': 5.0,
            },
            'hmm': {
                'n_states': 3,
                'covariance_type': 'full',
            },
            'xgboost': {
                'max_depth': 5,
                'n_estimators': 100,
                'learning_rate': 0.1,
            },
        },
        'portfolio': {
            'gamma_risk': 10.0,
            'gamma_trade': 1.0,
            'transaction_cost': 0.0005,
            'max_weight': 0.40,
            'capital_preservation_threshold': 2,
        },
        'evaluation': {
            'test_size': 0.2,
            'cv_folds': 5,
            'metrics': ['sharpe', 'max_dd', 'var_99', 'calmar'],
        },
        'output': {
            'figures_dir': 'output/figures',
            'models_dir': 'output/models',
            'results_file': 'output/results.csv',
        },
    }


def cache_to_parquet(
    df: pd.DataFrame, 
    name: str, 
    cache_dir: str = 'data/cache',
    compression: str = 'snappy'
) -> None:
    """Save DataFrame to parquet with compression."""
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    
    output_file = cache_path / f"{name}.parquet"
    df.to_parquet(output_file, compression=compression)


def load_from_parquet(
    name: str, 
    cache_dir: str = 'data/cache'
) -> Optional[pd.DataFrame]:
    """Load DataFrame from parquet cache (None if not found)."""
    cache_path = Path(cache_dir) / f"{name}.parquet"
    
    if cache_path.exists():
        return pd.read_parquet(cache_path)
    
    return None


def get_data_dir() -> Path:
    """Get path to dataset directory."""
    return Path(__file__).parent.parent.parent / "dataset"


def get_output_dir() -> Path:
    """Get path to output directory."""
    return Path(__file__).parent.parent.parent / "output"
