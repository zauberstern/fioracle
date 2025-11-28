"""
Data loading and alignment pipeline.

Loads asset universe and macro indicators at different frequencies,
aligns them to a unified daily timeline. Handles:
- Multiple date formats (YYYY-MM-DD, m/d/yy)
- Different column naming conventions
- Excludes non-investable assets (SP500, US_RISK_FREE_RATE)
"""

import re
import warnings
from pathlib import Path
from typing import List, Optional, Union, Dict

import pandas as pd
import numpy as np


class DataPipeline:
    """
    Unified data loader with automatic alignment to daily frequency.
    
    - Auto-excludes SP500 and US_RISK_FREE_RATE from investable assets
    - Handles multi-frequency data (annual/monthly/daily)
    - Properly parses historical dates (1900s)
    """

    DATE_COLUMN_KEYS = {
        'date',
        'timestamp',
        'time',
        'observation_date',
        'ds',
        'day',
        'unnamed: 0',
    }

    ASSET_VALUE_PREFERENCES = [
        'total return index',
        'total_return_index',
        'total_return',
        'value',
        'price',
        'close',
        'dgs2',      # 2Y yield
        't10y2y',    # 10Y-2Y slope
    ]

    MACRO_ALIASES = {
        'gpr_daily_1900_2025': 'gpr',
        'epu_daily_1900_2025': 'epu',
        'cboe_vix': 'vix',
        'us_inflation_daily_interp': 'us_inflation',
        'us_unemployment': 'us_unemployment',
        'us_debt_to_gdp': 'us_debt_to_gdp',
        'us_gdp_growth': 'us_gdp_growth',
    }

    # Excluded from investable assets but loaded separately
    EXCLUDED_INVESTABLE_FILES = {
        'SP500_TOTAL_RETURN.csv',      # Equity - excluded per user requirement
        'US_RISK_FREE_RATE.csv',       # Used only for excess return calculation
    }
    
    # Non-return columns (yields, spreads) - not investable but useful
    YIELD_COLUMNS = {
        'US 2Y Yield (1976-present).csv',
        'US 10Y2Y (1976-present).csv',
    }

    def __init__(
        self,
        asset_dir: Optional[Union[str, Path]] = None,
        macro_dir: Optional[Union[str, Path]] = None,
    ):
        base_dir = Path(__file__).resolve().parents[2]
        self.asset_dir = Path(asset_dir) if asset_dir else base_dir / "asset_universe"
        self.macro_dir = Path(macro_dir) if macro_dir else base_dir / "macro_universe"

        if not self.asset_dir.exists():
            warnings.warn(f"Asset universe directory not found: {self.asset_dir}")
        if not self.macro_dir.exists():
            warnings.warn(f"Macro universe directory not found: {self.macro_dir}")

    def load(
        self,
        start_date: Optional[Union[str, pd.Timestamp]] = None,
        end_date: Optional[Union[str, pd.Timestamp]] = None,
    ) -> pd.DataFrame:
        """Load and align all data sources. Returns daily DataFrame."""
        asset_data = self._load_asset_universe()
        yield_data = self._load_yield_data()
        macro_data = self._load_macro_universe()
        risk_free_data = self._load_risk_free_rate()
        sp500_data = self._load_sp500_for_correlation()  # For stock-bond correlation

        frames = [df for df in (asset_data, yield_data, macro_data, risk_free_data, sp500_data) if not df.empty]
        if not frames:
            return pd.DataFrame()

        combined = pd.concat(frames, axis=1).sort_index()
        combined = combined[~combined.index.duplicated(keep='first')]
        combined = combined.dropna(how='all')

        start_ts = pd.to_datetime(start_date) if start_date is not None else None
        end_ts = pd.to_datetime(end_date) if end_date is not None else None

        if start_ts is not None and end_ts is not None and start_ts > end_ts:
            return pd.DataFrame(columns=combined.columns)

        if start_ts is not None:
            combined = combined[combined.index >= start_ts]
        if end_ts is not None:
            combined = combined[combined.index <= end_ts]

        return combined
    
    def _load_risk_free_rate(self) -> pd.DataFrame:
        """Load risk-free rate separately (not as investible asset)."""
        risk_free_path = self.asset_dir / 'US_RISK_FREE_RATE.csv'
        
        # Try alternative: US_CASH_RETURN as risk-free proxy
        if not risk_free_path.exists():
            risk_free_path = self.asset_dir / 'US_CASH_RETURN.csv'
            
        if not risk_free_path.exists():
            return pd.DataFrame()
        
        try:
            df = self._read_csv(risk_free_path)
            value_col = self._select_value_column(df.columns)
            if value_col is None:
                return pd.DataFrame()
            
            series = pd.to_numeric(df[value_col], errors='coerce')
            if series.dropna().empty:
                return pd.DataFrame()
            
            return pd.DataFrame({'asset_us_risk_free_rate': series})
        except Exception as exc:
            warnings.warn(f"Could not load risk-free rate: {exc}")
            return pd.DataFrame()
    
    def _load_sp500_for_correlation(self) -> pd.DataFrame:
        """Load SP500 separately for stock-bond correlation (NOT investable)."""
        sp500_path = self.asset_dir / 'SP500_TOTAL_RETURN.csv'
        
        if not sp500_path.exists():
            return pd.DataFrame()
        
        try:
            df = self._read_csv(sp500_path)
            value_col = self._select_value_column(df.columns)
            if value_col is None:
                return pd.DataFrame()
            
            series = pd.to_numeric(df[value_col], errors='coerce')
            if series.dropna().empty:
                return pd.DataFrame()
            
            # Mark as non-investable via naming convention
            return pd.DataFrame({'asset_sp500_total_return': series})
        except Exception as exc:
            warnings.warn(f"Could not load SP500 for correlation: {exc}")
            return pd.DataFrame()

    def _load_asset_universe(self) -> pd.DataFrame:
        """Load investable asset universe (excluding SP500 and RF)."""
        if not self.asset_dir.exists():
            return pd.DataFrame()

        series_dict = {}
        for path in sorted(self.asset_dir.glob('*.csv')):
            # Skip excluded and yield files
            if path.name in self.EXCLUDED_INVESTABLE_FILES:
                continue
            if path.name in self.YIELD_COLUMNS:
                continue
            
            try:
                df = self._read_csv(path)
            except Exception as exc:
                warnings.warn(f"Could not load asset file {path.name}: {exc}")
                continue

            value_col = self._select_value_column(df.columns)
            if value_col is None:
                continue

            series = pd.to_numeric(df[value_col], errors='coerce')
            if series.dropna().empty:
                continue

            slug = self._slugify(path.stem)
            slug = self._trim_suffix(slug, ['_total_return', '_return', '_tr'])
            column_name = f'asset_{slug}'
            series_dict[column_name] = series

        if not series_dict:
            return pd.DataFrame()

        assets_df = pd.DataFrame(series_dict)
        assets_df = assets_df.sort_index()
        return assets_df

    def _load_yield_data(self) -> pd.DataFrame:
        """Load yield curve data (2Y yield, 10Y-2Y slope) as features."""
        if not self.asset_dir.exists():
            return pd.DataFrame()

        series_dict = {}
        
        # Load 2Y yield
        yield_2y_path = self.asset_dir / 'US 2Y Yield (1976-present).csv'
        if yield_2y_path.exists():
            try:
                df = self._read_csv(yield_2y_path)
                value_col = self._select_value_column(df.columns)
                if value_col:
                    series = pd.to_numeric(df[value_col], errors='coerce')
                    if not series.dropna().empty:
                        series_dict['asset_us_treasury_2y_yield'] = series
            except Exception as exc:
                warnings.warn(f"Could not load 2Y yield: {exc}")
        
        # Load 10Y-2Y slope
        slope_path = self.asset_dir / 'US 10Y2Y (1976-present).csv'
        if slope_path.exists():
            try:
                df = self._read_csv(slope_path)
                value_col = self._select_value_column(df.columns)
                if value_col:
                    series = pd.to_numeric(df[value_col], errors='coerce')
                    if not series.dropna().empty:
                        series_dict['asset_us_10y2y_slope'] = series
            except Exception as exc:
                warnings.warn(f"Could not load 10Y-2Y slope: {exc}")

        if not series_dict:
            return pd.DataFrame()

        yield_df = pd.DataFrame(series_dict)
        yield_df = yield_df.sort_index()
        return yield_df

    def _load_macro_universe(self) -> pd.DataFrame:
        if not self.macro_dir.exists():
            return pd.DataFrame()

        frames = []
        for path in sorted(self.macro_dir.glob('*.csv')):
            try:
                df = self._read_csv(path)
            except Exception as exc:
                warnings.warn(f"Could not load macro file {path.name}: {exc}")
                continue

            numeric_df = df.apply(pd.to_numeric, errors='coerce')
            numeric_df = numeric_df.dropna(how='all', axis=1)
            if numeric_df.empty:
                continue

            file_slug = self._slugify(path.stem)
            alias = self.MACRO_ALIASES.get(file_slug, file_slug)

            if numeric_df.shape[1] == 1:
                col = numeric_df.columns[0]
                renamed = numeric_df.rename(columns={col: f'macro_{alias}'})
            else:
                rename_map = {}
                for col in numeric_df.columns:
                    col_slug = self._slugify(col)
                    suffix = f'_{col_slug}' if col_slug else ''
                    rename_map[col] = f'macro_{alias}{suffix}'
                renamed = numeric_df.rename(columns=rename_map)

            frames.append(renamed)

        if not frames:
            return pd.DataFrame()

        macro_df = pd.concat(frames, axis=1)
        macro_df = macro_df.sort_index()
        return macro_df

    def _read_csv(self, path: Path) -> pd.DataFrame:
        """Read CSV with intelligent date parsing."""
        df = pd.read_csv(path)
        date_col = self._detect_date_column(df.columns)
        if date_col is None:
            raise ValueError(f"No date column found in {path}")

        date_series = df[date_col].copy()
        
        # Detect date format
        format_type = self._detect_date_format(date_series)
        
        if format_type == 'mdyy':
            # Parse M/D/YY format, forcing 1900s for historical data
            parsed_dates = date_series.apply(self._parse_mdyy)
        else:
            # Standard parsing
            parsed_dates = pd.to_datetime(date_series, errors='coerce', infer_datetime_format=True)
            
            # Fix any dates that got parsed incorrectly to future
            if parsed_dates.notna().any():
                future_mask = parsed_dates > pd.Timestamp('2030-01-01')
                if future_mask.any():
                    # Re-parse these with 1900s assumption
                    for idx in parsed_dates[future_mask].index:
                        parsed_dates.loc[idx] = self._parse_mdyy(date_series.loc[idx])

        df[date_col] = parsed_dates
        df = df.dropna(subset=[date_col])
        
        # Filter to reasonable date range
        min_date = pd.Timestamp('1800-01-01')
        max_date = pd.Timestamp('2100-12-31')
        valid_dates = (df[date_col] >= min_date) & (df[date_col] <= max_date)
        df = df[valid_dates]
        
        if len(df) == 0:
            warnings.warn(f"No valid dates found in {path}")
            return pd.DataFrame()
        
        df = df.set_index(date_col)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.index = df.index.normalize()
        df = df.sort_index()
        df = df[~df.index.duplicated(keep='first')]
        return df

    def _detect_date_format(self, series: pd.Series) -> str:
        """Detect if dates are in M/D/YY format."""
        sample_size = min(100, len(series))
        mdyy_count = 0
        
        for val in series.head(sample_size):
            if isinstance(val, str) and '/' in val:
                parts = val.split('/')
                if len(parts) == 3:
                    try:
                        year_part = parts[2]
                        if len(year_part) == 2:
                            mdyy_count += 1
                    except:
                        pass
        
        return 'mdyy' if mdyy_count > sample_size * 0.5 else 'standard'

    def _parse_mdyy(self, date_str) -> pd.Timestamp:
        """Parse M/D/YY format, always using 1900s for historical financial data."""
        try:
            if isinstance(date_str, str) and '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    month, day, year_str = parts
                    year_int = int(year_str)
                    
                    # Handle 2-digit years - always use 1900s for historical data
                    if year_int < 100:
                        year_int += 1900
                    
                    return pd.Timestamp(year=int(year_int), month=int(month), day=int(day))
            return pd.NaT
        except:
            return pd.NaT

    def _detect_date_column(self, columns: List[str]) -> Optional[str]:
        for col in columns:
            normalized = str(col).strip().lower()
            if normalized in self.DATE_COLUMN_KEYS:
                return col

        for col in columns:
            if 'date' in str(col).lower():
                return col

        return columns[0] if len(columns) > 0 else None

    @staticmethod
    def _slugify(value: str) -> str:
        value = (value or '').replace('-', '_').replace(' ', '_')
        value = re.sub(r'[^0-9a-zA-Z_]+', '', value)
        value = re.sub(r'_+', '_', value)
        return value.strip('_').lower()

    @staticmethod
    def _trim_suffix(value: str, suffixes: List[str]) -> str:
        for suffix in suffixes:
            if value.endswith(suffix):
                return value[: -len(suffix)]
        return value

    def _select_value_column(self, columns: List[str]) -> Optional[str]:
        normalized = {col: str(col).strip().lower() for col in columns}
        for preferred in self.ASSET_VALUE_PREFERENCES:
            for original, norm in normalized.items():
                if norm == preferred:
                    return original

        # Skip date-like columns
        for original, norm in normalized.items():
            if norm not in self.DATE_COLUMN_KEYS and 'date' not in norm:
                return original
                
        return None

    def get_asset_list(self) -> List[str]:
        """Get list of investable asset names."""
        if not self.asset_dir.exists():
            return []

        assets = []
        for path in sorted(self.asset_dir.glob('*.csv')):
            if path.name in self.EXCLUDED_INVESTABLE_FILES:
                continue
            if path.name in self.YIELD_COLUMNS:
                continue
                
            slug = self._slugify(path.stem)
            slug = self._trim_suffix(slug, ['_total_return', '_return', '_tr'])
            assets.append(slug.upper())

        return assets
    
    def get_asset_availability(self, data: pd.DataFrame) -> Dict[str, pd.Timestamp]:
        """
        Get first available date for each asset.
        
        Assets become investable when their data becomes available.
        
        Returns:
            Dict mapping asset name to first available date
        """
        availability = {}
        
        asset_cols = [c for c in data.columns if c.startswith('asset_') 
                      and 'risk_free' not in c 
                      and '2y_yield' not in c 
                      and '10y2y' not in c]
        
        for col in asset_cols:
            non_null = data[col].dropna()
            if len(non_null) > 0:
                asset_name = col.replace('asset_', '').upper()
                availability[asset_name] = non_null.index[0]
        
        return availability
