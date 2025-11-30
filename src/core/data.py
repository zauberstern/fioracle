"""
Data loading and alignment pipeline.

Loads from three directories:
1. asset_universe/ - Investable fixed income assets
2. macro_universe/ - Macro indicators for features
3. ancillary/ - Supporting data (RF rate, SP500, yields) for features ONLY

Key principle: Ancillary data is NEVER investable, only used for feature engineering.
"""

import re
import warnings
from pathlib import Path
from typing import List, Optional, Union, Dict

import pandas as pd
import numpy as np


class DataPipeline:
    """
    Unified data loader with config-driven asset/macro management.
    """

    DATE_COLUMN_KEYS = {'date', 'timestamp', 'time', 'observation_date', 'ds', 'day'}
    
    VALUE_COLUMN_PREFERENCES = [
        'total return index', 'total_return_index', 'synthesized_vix',
        'debt_to_gdp_ratio', 'inflation_rate', 'gpri', 'gdp_growth',
        'unemployment', 'inflation', 'epu', 't10y2y', 'dgs2',
        'value', 'price', 'close'
    ]

    def __init__(
        self,
        asset_dir: Optional[Union[str, Path]] = None,
        macro_dir: Optional[Union[str, Path]] = None,
        ancillary_dir: Optional[Union[str, Path]] = None,
        config: Optional[dict] = None
    ):
        base_dir = Path(__file__).resolve().parents[2]
        self.asset_dir = Path(asset_dir) if asset_dir else base_dir / "asset_universe"
        self.macro_dir = Path(macro_dir) if macro_dir else base_dir / "macro_universe"
        self.ancillary_dir = Path(ancillary_dir) if ancillary_dir else base_dir / "ancillary"
        self.config = config or {}

    def load(
        self,
        start_date: Optional[Union[str, pd.Timestamp]] = None,
        end_date: Optional[Union[str, pd.Timestamp]] = None,
    ) -> pd.DataFrame:
        """Load and align all data sources."""
        # Load investable assets
        asset_data = self._load_asset_universe()
        
        # Load macro indicators
        macro_data = self._load_macro_universe()
        
        # Load ancillary data (RF, SP500, yields) - for features ONLY
        ancillary_data = self._load_ancillary_data()

        frames = [df for df in (asset_data, macro_data, ancillary_data) if not df.empty]
        if not frames:
            return pd.DataFrame()

        # Ensure each frame has unique index before concat
        cleaned_frames = []
        for df in frames:
            df_clean = df[~df.index.duplicated(keep='first')]
            cleaned_frames.append(df_clean)
        
        combined = pd.concat(cleaned_frames, axis=1).sort_index()
        combined = combined[~combined.index.duplicated(keep='first')]
        combined = combined.dropna(how='all')
        
        # Apply forward-fill for macro and ancillary data (published at varying frequencies)
        # Asset data should NOT be forward-filled as it represents actual price levels
        macro_cols = [c for c in combined.columns if c.startswith('macro_')]
        ancillary_cols = [c for c in combined.columns if c.startswith('ancillary_')]
        
        for col in macro_cols + ancillary_cols:
            # Forward-fill missing values (data published at lower frequency)
            # Limit to 30 days to avoid carrying stale data too far
            combined[col] = combined[col].ffill(limit=30)

        # Date filtering
        if start_date:
            combined = combined[combined.index >= pd.to_datetime(start_date)]
        if end_date:
            combined = combined[combined.index <= pd.to_datetime(end_date)]

        return combined
    
    def _load_ancillary_data(self) -> pd.DataFrame:
        """Load ancillary data: RF rate, SP500, yields (for features ONLY)."""
        if not self.ancillary_dir.exists():
            warnings.warn(f"Ancillary directory not found: {self.ancillary_dir}")
            return pd.DataFrame()
        
        series_dict = {}
        
        def _load_and_clean(path, col_name):
            """Helper to load and clean series."""
            if not path.exists():
                return None
            try:
                df = self._read_csv(path)
                df = df[~df.index.duplicated(keep='first')]
                val_col = self._select_value_column(df.columns)
                if val_col:
                    series = pd.to_numeric(df[val_col], errors='coerce')
                    series = series[~series.index.duplicated(keep='first')]
                    return series
            except Exception as e:
                warnings.warn(f"Could not load {path.name}: {e}")
            return None
        
        # Risk-free rate
        rf_series = _load_and_clean(self.ancillary_dir / 'US_RISK_FREE_RATE.csv', 'rf')
        if rf_series is not None:
            series_dict['ancillary_risk_free_rate'] = rf_series
        
        # SP500 (for stock-bond correlation)
        sp500_series = _load_and_clean(self.ancillary_dir / 'SP500_TOTAL_RETURN.csv', 'sp500')
        if sp500_series is not None:
            series_dict['ancillary_sp500'] = sp500_series
        
        # 2Y Yield
        yield_2y = _load_and_clean(self.ancillary_dir / 'US 2Y Yield (1976-present).csv', 'yield')
        if yield_2y is not None:
            series_dict['ancillary_yield_2y'] = yield_2y
        
        # 10Y-2Y Slope
        slope = _load_and_clean(self.ancillary_dir / 'US 10Y2Y (1976-present).csv', 'slope')
        if slope is not None:
            series_dict['ancillary_yield_slope'] = slope
        
        if not series_dict:
            return pd.DataFrame()
        
        result = pd.DataFrame(series_dict)
        result = result[~result.index.duplicated(keep='first')]
        return result

    def _load_asset_universe(self) -> pd.DataFrame:
        """Load investable assets from asset_universe/."""
        if not self.asset_dir.exists():
            return pd.DataFrame()

        series_dict = {}
        for path in sorted(self.asset_dir.glob('*.csv')):
            try:
                df = self._read_csv(path)
                
                # Remove duplicate index entries
                df = df[~df.index.duplicated(keep='first')]
                
                val_col = self._select_value_column(df.columns)
                if val_col is None:
                    continue

                series = pd.to_numeric(df[val_col], errors='coerce')
                series = series[~series.index.duplicated(keep='first')]
                
                if series.dropna().empty:
                    continue

                # Create clean column name
                slug = self._slugify(path.stem)
                column_name = f'asset_{slug}'
                series_dict[column_name] = series

            except Exception as e:
                warnings.warn(f"Could not load {path.name}: {e}")

        if not series_dict:
            return pd.DataFrame()

        result = pd.DataFrame(series_dict)
        result = result[~result.index.duplicated(keep='first')]
        return result.sort_index()

    def _load_macro_universe(self) -> pd.DataFrame:
        """Load macro indicators from macro_universe/, respecting config enabled/disabled lists."""
        if not self.macro_dir.exists():
            return pd.DataFrame()

        # Get enabled/disabled lists from config
        macro_cfg = self.config.get('macro', {})
        enabled_list = macro_cfg.get('enabled', [])
        disabled_list = macro_cfg.get('disabled', [])
        
        # Normalize names for matching (uppercase, no extension)
        enabled_set = {e.upper().replace('.CSV', '').replace('_', '') for e in enabled_list} if enabled_list else None
        disabled_set = {d.upper().replace('.CSV', '').replace('_', '') for d in disabled_list}

        series_dict = {}
        for path in sorted(self.macro_dir.glob('*.csv')):
            # Check if macro is enabled/disabled
            file_stem = path.stem.upper().replace('_', '')
            
            # If disabled list has items, skip if in disabled list
            if file_stem in disabled_set:
                continue
            
            # If enabled list has items, skip if NOT in enabled list
            if enabled_set and file_stem not in enabled_set:
                # Try partial match (e.g., "VIX" matches "VIX.csv")
                partial_match = any(e in file_stem or file_stem in e for e in enabled_set)
                if not partial_match:
                    continue
            try:
                df = self._read_csv(path)
                
                # Remove duplicate index entries
                df = df[~df.index.duplicated(keep='first')]
                
                val_col = self._select_value_column(df.columns)
                if val_col is None:
                    # Try first numeric column
                    for col in df.columns:
                        if df[col].dtype in ['float64', 'int64'] or col.lower() not in self.DATE_COLUMN_KEYS:
                            val_col = col
                            break
                
                if val_col is None:
                    continue

                series = pd.to_numeric(df[val_col], errors='coerce')
                
                # Remove duplicate index from series
                series = series[~series.index.duplicated(keep='first')]
                
                if series.dropna().empty:
                    continue

                slug = self._slugify(path.stem)
                column_name = f'macro_{slug}'
                series_dict[column_name] = series

            except Exception as e:
                warnings.warn(f"Could not load macro {path.name}: {e}")

        if not series_dict:
            return pd.DataFrame()

        # Create dataframe and handle duplicates
        result = pd.DataFrame(series_dict)
        result = result[~result.index.duplicated(keep='first')]
        return result.sort_index()

    def _read_csv(self, path: Path) -> pd.DataFrame:
        """Read CSV with automatic date parsing."""
        df = pd.read_csv(path)
        
        # Find date column
        date_col = None
        for col in df.columns:
            if col.lower().replace(' ', '_') in self.DATE_COLUMN_KEYS or 'date' in col.lower():
                date_col = col
                break
        
        if date_col is None:
            date_col = df.columns[0]
        
        # Parse dates with multiple format attempts
        dates = pd.to_datetime(df[date_col], errors='coerce')
        
        # Handle M/D/YY format (e.g., 1/1/00)
        if dates.isna().all():
            try:
                dates = pd.to_datetime(df[date_col], format='%m/%d/%y', errors='coerce')
                # Fix century for dates > 2050
                future_mask = dates.dt.year > 2050
                if future_mask.any():
                    dates = dates.where(~future_mask, dates - pd.DateOffset(years=100))
            except:
                pass
        
        df.index = dates
        df = df.drop(columns=[date_col], errors='ignore')
        df = df[~df.index.isna()]
        
        return df

    def _select_value_column(self, columns: List[str]) -> Optional[str]:
        """Select the best value column."""
        cols_lower = {c.lower().replace(' ', '_'): c for c in columns}
        
        for pref in self.VALUE_COLUMN_PREFERENCES:
            if pref in cols_lower:
                return cols_lower[pref]
        
        # Return first non-date column
        for col in columns:
            if col.lower().replace(' ', '_') not in self.DATE_COLUMN_KEYS:
                return col
        
        return None

    def _slugify(self, name: str) -> str:
        """Convert filename to column name slug."""
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9]+', '_', slug)
        slug = re.sub(r'_+', '_', slug)
        slug = slug.strip('_')
        # Remove common suffixes
        for suffix in ['_total_return', '_return', '_tr']:
            if slug.endswith(suffix):
                slug = slug[:-len(suffix)]
        return slug

    def get_asset_availability(self, data: pd.DataFrame) -> Dict[str, pd.Timestamp]:
        """Get first available date for each asset."""
        availability = {}
        for col in data.columns:
            if col.startswith('asset_'):
                first_valid = data[col].first_valid_index()
                if first_valid:
                    availability[col] = first_valid
        return availability
