"""
Shared utilities: logging, config, caching, and path management.

Provides essential utility functions for:
- Logging configuration
- Configuration file loading with defaults
- Fast parquet caching for data
- Path resolution for data and output directories
- Date validation and conversion
"""

import logging
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional, Union, Tuple
import warnings


def setup_logging(level: str = 'INFO', config: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """
    Configure logger with optional config file settings.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        config: Optional config dict with logging settings
        
    Returns:
        Configured logger instance
    """
    log_config = {}
    if config and isinstance(config, dict) and 'logging' in config:
        log_config = config.get('logging', {})
    
    log_level = log_config.get('level', level).upper()
    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_file = log_config.get('file', None)
    console = log_config.get('console', True)
    
    handlers = []
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level))
        console_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format,
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers if handlers else None,
        force=True
    )
    
    logger = logging.getLogger('fioracle')
    logger.setLevel(getattr(logging, log_level))
    
    return logger


def load_config(config_path: Union[str, Path] = 'config/config.yaml') -> Dict[str, Any]:
    """
    Load YAML config file with fallback to defaults.
    
    Args:
        config_path: Path to config YAML file
        
    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        warnings.warn(f"Config not found: {config_path}. Using defaults.")
        return get_default_config()
    
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        # Merge with defaults to ensure all keys exist
        defaults = get_default_config()
        config = _deep_merge(defaults, config)
        
        return config
    
    except Exception as e:
        warnings.warn(f"Error loading config: {e}. Using defaults.")
        return get_default_config()


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Recursively merge two dictionaries, with override taking precedence."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def get_default_config() -> Dict[str, Any]:
    """
    Fallback configuration matching config.yaml structure.
    
    Returns:
        Default configuration dictionary
    """
    return {
        'data': {
            'start_date': '1945-01-01',
            'end_date': '2025-11-12',
            'train_start': '1945-01-01',
            'train_end': '1977-05-06',
            'val_start': '1977-05-07',
            'val_end': '1993-07-08',
            'test_start': '1993-07-09',
            'test_end': '2025-11-12',
            'cache_dir': 'data/cache',
            'sources': {
                'lseg': {'enabled': True, 'credential_file': 'config/lseg_credentials.yaml'},
                'fred_md': {'enabled': True, 'n_components': 5},
                'jst': {'enabled': True, 'start_year': 1945, 'end_year': 2017}
            }
        },
        'assets': {
            'basic': ['SP500', 'BOND_10Y', 'CORP_AAA', 'CORP_BAA', 'BILLS_3M', 
                     'GOLD', 'SILVER', 'OIL', 'CHF', 'CH_BOND'],
            'full': ['SP500', 'BOND_10Y', 'CORP_AAA', 'CORP_BAA', 'BILLS_3M',
                    'GOLD', 'SILVER', 'OIL', 'CHF', 'CH_BOND', 'TIP', 'LQD', 'HYG']
        },
        'regimes': {
            'jump_model': {
                'lambda_candidates': [0.0, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0],
                'default_lambda': 5.0
            },
            'hmm': {
                'n_states': 3,
                'covariance_type': 'full',
                'n_iter': 200
            },
            'xgboost': {
                'max_depth': 5,
                'n_estimators': 100,
                'learning_rate': 0.1,
                'random_state': 42
            }
        },
        'features': {
            'asset': {
                'halflives': [21, 63, 126],
                'windows': [21, 63, 126]
            },
            'macro': {
                'stock_bond_correlation_window': 252,
                'use_pca': True,
                'pca_components': 10
            }
        },
        'portfolio': {
            'gamma_risk': 10.0,
            'gamma_trade': 1.0,
            'transaction_cost': 0.0005,
            'max_weight': 0.40,
            'min_weight': 0.00,
            'max_leverage': 1.0,
            'capital_preservation_threshold': 3,
            'ewmc_decay': 0.94,
            'use_gpr_scaling': True
        },
        'evaluation': {
            'use_walk_forward': True,
            'rebalance_frequency': 'monthly',
            'cv_folds': 5,
            'metrics': ['sharpe', 'max_dd', 'var_99', 'calmar', 'sortino', 'omega'],
            'benchmarks': ['equal_weight', 'buy_hold', 'sp500']
        },
        'output': {
            'figures_dir': 'output/figures',
            'models_dir': 'output/models',
            'results_dir': 'output/results',
            'performance_file': 'performance_summary.csv',
            'weights_file': 'portfolio_weights.csv',
            'returns_file': 'portfolio_returns.csv',
            'lambdas_file': 'optimal_lambdas.json',
            'plot_types': ['cumulative_returns', 'drawdown', 'weights', 
                          'regime_timeline', 'feature_importance', 'performance_summary'],
            'dpi': 300,
            'format': 'png'
        },
        'performance': {
            'use_numba': True,
            'use_cache': True,
            'cache_compression': 'snappy',
            'cache_size_mb': 1000
        },
        'logging': {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'file': 'output/fioracle.log',
            'console': True
        }
    }


def cache_to_parquet(
    df: pd.DataFrame, 
    name: str, 
    cache_dir: Union[str, Path] = 'data/cache',
    compression: str = 'snappy'
) -> Path:
    """
    Save DataFrame to parquet with compression.
    
    Args:
        df: DataFrame to cache
        name: Cache filename (without extension)
        cache_dir: Cache directory path
        compression: Compression algorithm (snappy, gzip, brotli)
        
    Returns:
        Path to cached file
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    
    output_file = cache_path / f"{name}.parquet"
    df.to_parquet(output_file, compression=compression, index=True)
    
    return output_file


def load_from_parquet(
    name: str, 
    cache_dir: Union[str, Path] = 'data/cache'
) -> Optional[pd.DataFrame]:
    """
    Load DataFrame from parquet cache.
    
    Args:
        name: Cache filename (without extension)
        cache_dir: Cache directory path
        
    Returns:
        DataFrame if found, None otherwise
    """
    cache_path = Path(cache_dir) / f"{name}.parquet"
    
    if cache_path.exists():
        try:
            return pd.read_parquet(cache_path)
        except Exception as e:
            warnings.warn(f"Error loading cache {cache_path}: {e}")
            return None
    
    return None


def get_project_root() -> Path:
    """
    Get path to project root directory.
    
    Returns:
        Path to project root
    """
    return Path(__file__).resolve().parent.parent.parent


def get_data_dir() -> Path:
    """
    Get path to dataset directory.
    
    Returns:
        Path to dataset directory
    """
    return get_project_root() / "dataset"


def get_output_dir() -> Path:
    """
    Get path to output directory.
    
    Returns:
        Path to output directory
    """
    return get_project_root() / "output"


def get_config_dir() -> Path:
    """
    Get path to config directory.
    
    Returns:
        Path to config directory
    """
    return get_project_root() / "config"


def ensure_dir(path: Union[str, Path]) -> Path:
    """
    Ensure directory exists, create if it doesn't.
    
    Args:
        path: Directory path
        
    Returns:
        Path object for the directory
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def parse_date(date: Union[str, pd.Timestamp, None]) -> Optional[pd.Timestamp]:
    """
    Parse date string or Timestamp to pandas Timestamp.
    
    Args:
        date: Date as string, Timestamp, or None
        
    Returns:
        Parsed Timestamp or None
    """
    if date is None:
        return None
    
    if isinstance(date, pd.Timestamp):
        return date
    
    try:
        return pd.to_datetime(date)
    except Exception:
        warnings.warn(f"Could not parse date: {date}")
        return None


def validate_date_range(
    start_date: Optional[Union[str, pd.Timestamp]],
    end_date: Optional[Union[str, pd.Timestamp]]
) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """
    Validate and parse date range.
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        Tuple of (start_timestamp, end_timestamp)
        
    Raises:
        ValueError: If dates are invalid or start > end
    """
    start = parse_date(start_date)
    end = parse_date(end_date)
    
    if start is not None and end is not None and start > end:
        raise ValueError(f"Start date {start} is after end date {end}")
    
    return start, end


def get_annualization_factor(frequency: str = 'daily') -> int:
    """
    Get annualization factor for given frequency.
    
    Args:
        frequency: Data frequency ('daily', 'monthly', 'annual')
        
    Returns:
        Annualization factor (252 for daily, 12 for monthly, 1 for annual)
    """
    factors = {
        'daily': 252,
        'monthly': 12,
        'annual': 1,
        'annualized': 1
    }
    
    return factors.get(frequency.lower(), 252)
