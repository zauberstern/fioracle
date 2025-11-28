"""
Streamlined core modules for Fioracle.

Consolidates all functionality into 6 essential modules:
- utils: Shared utilities
- data: Data loading and alignment
- features: Feature engineering
- regimes: Regime identification
- portfolio: Portfolio optimization
- evaluation: Performance evaluation
"""

from .utils import (
    setup_logging, load_config, get_default_config,
    cache_to_parquet, load_from_parquet,
    get_project_root, get_data_dir, get_output_dir, get_config_dir,
    ensure_dir, parse_date, validate_date_range, get_annualization_factor
)
from .data import DataPipeline
from .features import engineer_features
from .regimes import RegimeEngine
from .portfolio import PortfolioEngine
from .evaluation import Evaluator

__all__ = [
    # Utilities
    'setup_logging',
    'load_config',
    'get_default_config',
    'cache_to_parquet',
    'load_from_parquet',
    'get_project_root',
    'get_data_dir',
    'get_output_dir',
    'get_config_dir',
    'ensure_dir',
    'parse_date',
    'validate_date_range',
    'get_annualization_factor',
    # Core modules
    'DataPipeline',
    'engineer_features',
    'RegimeEngine',
    'PortfolioEngine',
    'Evaluator',
]

__version__ = '2.0.0'
