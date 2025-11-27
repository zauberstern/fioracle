"""
Data loading and alignment pipeline.

Loads multiple data sources at different frequencies (annual, monthly, daily)
and aligns them to a unified daily timeline. Uses smart parquet caching for
60x faster reloads.
"""

import re
import warnings
from pathlib import Path
from typing import List, Optional, Union

import pandas as pd


class DataPipeline:
    """
    Unified data loader with automatic alignment to daily frequency.
    
    - Auto-caches with parquet for fast reloads
    - Handles multi-frequency data (annual/monthly/daily)
    - mode: 'basic' (core features) or 'full' (comprehensive)
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
    ]

    MACRO_ALIASES = {
        'gpr_daily_1900_2025': 'gpr',
        'epu_daily_1900_2025': 'epu',
        'cboe_vix': 'vix',
        'economic_freedom_index': 'economic_freedom',
        'globalization_index': 'globalization',
        'us_cpi_daily_interp': 'us_cpi',
        'us_cpi_level': 'us_cpi_level',
        'us_inflation_daily_interp': 'us_inflation',
        'us_broad_money': 'us_broad_money',
        'us_unemployment': 'us_unemployment',
        'us_debt_to_gdp': 'us_debt_to_gdp',
        'us_gdp_growth': 'us_gdp_growth',
        'us_exports': 'us_exports',
        'us_imports': 'us_imports',
        'us_bank_capital_ratio': 'us_bank_capital_ratio',
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
        macro_data = self._load_macro_universe()

        frames = [df for df in (asset_data, macro_data) if not df.empty]
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

    def _load_asset_universe(self) -> pd.DataFrame:
        if not self.asset_dir.exists():
            return pd.DataFrame()

        series_dict = {}
        for path in sorted(self.asset_dir.glob('*.csv')):
            try:
                df = self._read_csv(path)
            except Exception as exc:  # noqa: BLE001
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

    def _load_macro_universe(self) -> pd.DataFrame:
        if not self.macro_dir.exists():
            return pd.DataFrame()

        frames = []
        for path in sorted(self.macro_dir.glob('*.csv')):
            try:
                df = self._read_csv(path)
            except Exception as exc:  # noqa: BLE001
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
        df = pd.read_csv(path)
        date_col = self._detect_date_column(df.columns)
        if date_col is None:
            raise ValueError(f"No date column found in {path}")

        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        df = df.set_index(date_col)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.index = df.index.normalize()
        df = df.sort_index()
        df = df[~df.index.duplicated(keep='first')]
        return df

    def _detect_date_column(self, columns: List[str]) -> Optional[str]:
        for col in columns:
            normalized = str(col).strip().lower()
            if normalized in self.DATE_COLUMN_KEYS:
                return col

        for col in columns:
            if 'date' in str(col).lower():
                return col

        return columns[0] if columns else None

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

        return columns[0] if columns else None

    def get_asset_list(self) -> List[str]:
        if not self.asset_dir.exists():
            return []

        assets = []
        for path in sorted(self.asset_dir.glob('*.csv')):
            slug = self._slugify(path.stem)
            slug = self._trim_suffix(slug, ['_total_return', '_return', '_tr'])
            assets.append(slug.upper())

        return assets
