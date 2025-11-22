"""
Data loading and alignment pipeline.

Loads multiple data sources at different frequencies (annual, monthly, daily)
and aligns them to a unified daily timeline. Uses smart parquet caching for
60x faster reloads.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Optional, List, Union
from scipy.interpolate import PchipInterpolator
import warnings

from .utils import cache_to_parquet, load_from_parquet, get_data_dir


class DataPipeline:
    """
    Unified data loader with automatic alignment to daily frequency.
    
    - Auto-caches with parquet for fast reloads
    - Handles multi-frequency data (annual/monthly/daily)
    - mode: 'basic' (core features) or 'full' (comprehensive)
    """
    
    def __init__(self, mode: str = 'basic', cache_dir: str = 'data/cache'):
        self.mode = mode
        self.cache_dir = cache_dir
        self.data_dir = get_data_dir()
        self._cache = {}
        
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
    
    def load(
        self, 
        start_date: str = '1985-01-01',
        end_date: str = '2010-12-31',
        force_reload: bool = False
    ) -> pd.DataFrame:
        """Load and align all data sources. Returns daily DataFrame."""
        cache_key = f"aligned_{self.mode}_{start_date}_{end_date}"
        
        # Try cache first
        if not force_reload:
            cached_data = load_from_parquet(cache_key, self.cache_dir)
            if cached_data is not None:
                print(f"✓ Loaded cached data: {cached_data.shape}")
                return cached_data
        
        print(f"Loading data ({self.mode} mode): {start_date} to {end_date}")
        
        raw_data = self._load_raw_sources()
        aligned_data = self._align_to_daily(raw_data, start_date, end_date)
        
        cache_to_parquet(aligned_data, cache_key, self.cache_dir)
        
        print(f"✓ Loaded and aligned data: {aligned_data.shape}")
        return aligned_data
    
    def _load_raw_sources(self) -> Dict[str, Union[pd.Series, pd.DataFrame]]:
        """Load all raw sources based on mode."""
        data_dict = {}
        
        print("  Loading essential data sources...")
        
        # Core sources (always loaded)
        try:
            data_dict['gpr'] = self._load_gpr()
        except Exception as e:
            warnings.warn(f"Could not load GPR: {e}")
        
        try:
            data_dict['epu'] = self._load_epu()
        except Exception as e:
            warnings.warn(f"Could not load EPU: {e}")
        
        try:
            data_dict['shiller'] = self._load_shiller()
        except Exception as e:
            warnings.warn(f"Could not load Shiller: {e}")
        
        try:
            data_dict['jst'] = self._load_jst()
        except Exception as e:
            warnings.warn(f"Could not load JST: {e}")
        
        try:
            data_dict['efw'] = self._load_efw()
        except Exception as e:
            warnings.warn(f"Could not load EFW: {e}")
        
        try:
            data_dict['kof'] = self._load_kof()
        except Exception as e:
            warnings.warn(f"Could not load KOF: {e}")
        
        # New asset classes
        try:
            data_dict['bills_3m'] = self._load_3m_bills()
        except Exception as e:
            warnings.warn(f"Could not load 3M Bills: {e}")
        
        try:
            data_dict['gold'] = self._load_gold()
        except Exception as e:
            warnings.warn(f"Could not load Gold: {e}")
        
        try:
            data_dict['swiss'] = self._load_swiss()
        except Exception as e:
            warnings.warn(f"Could not load Swiss assets: {e}")
        
        try:
            data_dict['commodities'] = self._load_commodities()
        except Exception as e:
            warnings.warn(f"Could not load commodities: {e}")
        
        # Full mode adds more sources
        if self.mode == 'full':
            print("  Loading comprehensive data sources...")
            
            try:
                data_dict['fred_md'] = self._load_fred_md()
            except Exception as e:
                warnings.warn(f"Could not load FRED-MD: {e}")
            
            try:
                data_dict['lseg'] = self._load_lseg()
            except Exception as e:
                warnings.warn(f"Could not load LSEG: {e}")
        
        return data_dict
    
    def _load_gpr(self) -> pd.Series:
        """
        Load Geopolitical Risk Index (daily).
        
        Uses the combined daily dataset (1900-2025) generated via Chow-Lin disaggregation.
        """
        gpr_combined_path = self.data_dir / "GPRI" / "gpr_daily_1900_2025.csv"
        
        if not gpr_combined_path.exists():
            warnings.warn(f"Combined GPR file not found: {gpr_combined_path}")
            return pd.Series(dtype=float)
            
        # Load with first column as index (date)
        df = pd.read_csv(gpr_combined_path, index_col=0, parse_dates=True)
        df.index.name = 'date'
        return df['GPRD'].sort_index()
    
    def _load_epu(self) -> pd.Series:
        """
        Load Economic Policy Uncertainty Index (daily).
        
        Uses the combined daily dataset (1900-2025) generated via Chow-Lin disaggregation.
        """
        epu_combined_path = self.data_dir / "EPU" / "epu_daily_1900_2025.csv"
        
        if not epu_combined_path.exists():
            warnings.warn(f"Combined EPU file not found: {epu_combined_path}")
            return pd.Series(dtype=float)
            
        # Load with first column as index (date)
        df = pd.read_csv(epu_combined_path, index_col=0, parse_dates=True)
        df.index.name = 'date'
        return df['EPU'].sort_index()
    
    def _load_shiller(self) -> pd.DataFrame:
        """Load Shiller stock/bond data (monthly, parses YYYY.MM format)."""
        shiller_path = self.data_dir / "Shiller_Data.xlsx"
        
        df = pd.read_excel(shiller_path, sheet_name='Sheet1')
        
        # Parse date from YYYY.MM format
        df['year'] = df['Date'].astype(int)
        df['month'] = ((df['Date'] % 1) * 100).round().astype(int)
        df['month'] = df['month'].replace(0, 1)
        df['date'] = pd.to_datetime(df[['year', 'month']].assign(day=1))
        
        df = df.set_index('date')
        df = df.drop(columns=['Date', 'year', 'month'], errors='ignore')
        
        return df.sort_index()
    
    def _load_jst(self) -> pd.DataFrame:
        """Load JST Macrohistory Database (USA-specific file)."""
        jst_path = self.data_dir / "JST_Data_USA.xlsx"
        
        if not jst_path.exists():
            warnings.warn(f"JST file not found: {jst_path}")
            return pd.DataFrame()
        
        df = pd.read_excel(jst_path, sheet_name='Sheet1')
        
        if len(df) > 0:
            df['date'] = pd.to_datetime(df['year'].astype(str) + '-01-01')
            df = df.set_index('date')
            df = df.drop(columns=['country', 'iso', 'year', 'ifs'], errors='ignore')
            return df.sort_index()
        
        return pd.DataFrame()
    
    def _load_efw(self) -> pd.Series:
        """Load Economic Freedom of the World Index (Fraser Institute)."""
        efw_path = self.data_dir / "Fraser Institute" / "efotw-2025-master-index-data-for-researchers-iso.xlsx"
        
        if not efw_path.exists():
            warnings.warn(f"EFW file not found: {efw_path}")
            return pd.Series(dtype=float)
        
        df = pd.read_excel(efw_path, sheet_name='EFW Panel Dataset')
        
        us_df = df[df['ISO_Code'] == 'USA'].copy()
        
        if len(us_df) > 0:
            us_df['date'] = pd.to_datetime(us_df['Year'].astype(str) + '-01-01')
            us_df = us_df.set_index('date')
            return pd.to_numeric(us_df['Summary'], errors='coerce').sort_index()
        
        return pd.Series(dtype=float)
    
    def _load_kof(self) -> pd.DataFrame:
        """Load KOF Globalization Index (extract USA columns with clean names)."""
        kof_path = self.data_dir / "KOF Globalization Index" / "KOF Globalisation Index 2024 Time Series.xlsx"
        
        if not kof_path.exists():
            warnings.warn(f"KOF file not found: {kof_path}")
            return pd.DataFrame()
        
        df = pd.read_excel(kof_path, sheet_name='Sheet1')
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        # Extract USA columns
        usa_cols = [c for c in df.columns if c.endswith('.usa')]
        us_df = df[usa_cols].copy()
        
        # Clean names: ch.kof.globidx.v2020.cugi.usa -> kof_cugi
        new_names = {}
        for col in usa_cols:
            parts = col.split('.')
            if len(parts) >= 5:
                indicator = parts[4]  # cugi, ecgi, figi, etc.
                new_names[col] = f"kof_{indicator}"
            else:
                new_names[col] = col
        
        us_df = us_df.rename(columns=new_names)
        return us_df.sort_index()
    
    def _load_fred_md(self) -> pd.DataFrame:
        """Load FRED-MD database (127 monthly series)."""
        fred_path = self.data_dir / "FRED-MD" / "current.csv"
        
        if not fred_path.exists():
            warnings.warn(f"FRED-MD file not found: {fred_path}")
            return pd.DataFrame()
        
        df = pd.read_csv(fred_path)
        df['date'] = pd.to_datetime(df['sasdate'])
        df = df.set_index('date')
        df = df.drop(columns=['sasdate'], errors='ignore')
        
        return df.sort_index()
    
    def _load_lseg(self) -> pd.DataFrame:
        """Load LSEG parquet files (modern ETFs + macro from 2000+)."""
        lseg_dir = self.data_dir / "lseg_data"
        
        if not lseg_dir.exists():
            warnings.warn(f"LSEG directory not found: {lseg_dir}")
            return pd.DataFrame()
        
        data_dict = {}
        
        # ETF assets (for full mode)
        etf_files = {
            'tip': 'tip_etf.parquet',      # TIPS (inflation-protected)
            'lqd': 'lqd_etf.parquet',      # Investment grade corporate
            'hyg': 'hyg_etf.parquet',      # High yield corporate
        }
        
        for name, filename in etf_files.items():
            file_path = lseg_dir / filename
            if file_path.exists():
                df = pd.read_parquet(file_path)
                # Use TRDPRC_1 (trade price) or NAVALUE (net asset value)
                if 'TRDPRC_1' in df.columns:
                    data_dict[name] = df['TRDPRC_1']
                elif 'NAVALUE' in df.columns:
                    data_dict[name] = df['NAVALUE']
        
        # Macro variables (always loaded)
        macro_files = {
            'treasury_2y': ('treasury_2y.parquet', 'YLDTOMAT'),  # 2Y yield
            'vix': ('vix.parquet', 'TRDPRC_1'),                  # VIX index
        }
        
        for name, (filename, column) in macro_files.items():
            file_path = lseg_dir / filename
            if file_path.exists():
                df = pd.read_parquet(file_path)
                if column in df.columns:
                    data_dict[name] = df[column]
        
        if data_dict:
            return pd.DataFrame(data_dict)
        
        warnings.warn("No LSEG files found.")
        return pd.DataFrame()
    
    def _load_3m_bills(self) -> pd.Series:
        """Load 3-month T-Bills as monthly returns (1934-2010)."""
        bills_path = self.data_dir / "3m_bills_Secondary_Market_Rate_Discount_Basis_1934_2010.xlsx"
        
        if not bills_path.exists():
            warnings.warn(f"3M Bills file not found: {bills_path}")
            return pd.Series(dtype=float)
        
        df = pd.read_excel(bills_path)
        df['date'] = pd.to_datetime(df['observation_date'])
        df = df.set_index('date')
        
        # Convert annual rate to monthly return
        # TB3MS is annualized percentage rate, convert to decimal monthly return
        monthly_rate = df['TB3MS'] / 100 / 12
        
        return monthly_rate.sort_index()
    
    def _load_gold(self) -> pd.Series:
        """Load gold price returns (monthly, 1833-2025)."""
        gold_path = self.data_dir / "gold_prices.csv"
        
        if not gold_path.exists():
            warnings.warn(f"Gold file not found: {gold_path}")
            return pd.Series(dtype=float)
        
        df = pd.read_csv(gold_path)
        
        # Parse date from YYYY-MM format
        df['date'] = pd.to_datetime(df['Date'], format='%Y-%m')
        df = df.set_index('date')
        
        # Calculate returns from prices
        gold_prices = df['Price'].sort_index()
        gold_returns = gold_prices.pct_change()
        
        return gold_returns
    
    def _load_swiss(self) -> pd.DataFrame:
        """Load Swiss assets from JST database (annual, 1919-2010)."""
        swiss_path = self.data_dir / "JST_Data_CH.xlsx"
        
        if not swiss_path.exists():
            warnings.warn(f"Swiss data file not found: {swiss_path}")
            return pd.DataFrame()
        
        df = pd.read_excel(swiss_path, sheet_name='Sheet1')
        
        if len(df) > 0:
            df['date'] = pd.to_datetime(df['year'].astype(str) + '-01-01')
            df = df.set_index('date')
            
            # Extract relevant columns for our assets:
            # - bond_tr: Long-term government bond total returns
            # - xrusd: CHF/USD exchange rate
            swiss_data = pd.DataFrame({
                'swiss_bond_tr': df['bond_tr'],  # Swiss long-term govt bonds total return
                'chf_usd': df['xrusd'],  # Swiss Franc exchange rate vs USD
            })
            
            # Calculate CHF returns (appreciation = negative USD/CHF return)
            # xrusd is CHF per USD, so we want inverse for USD investor
            if 'xrusd' in df.columns:
                swiss_data['chf_return'] = -df['xrusd'].pct_change()
            
            return swiss_data.sort_index()
        
        return pd.DataFrame()
    
    def _load_commodities(self) -> pd.DataFrame:
        """Load commodity returns: Oil (Brent) and Silver (monthly, 1960-2010)."""
        commodity_path = self.data_dir / "commodity-prices-1960-2010.xlsx"
        
        if not commodity_path.exists():
            warnings.warn(f"Commodity file not found: {commodity_path}")
            return pd.DataFrame()
        
        df = pd.read_excel(commodity_path, sheet_name='Monthly Prices')
        
        if len(df) > 0:
            # Parse date from format like "1960M01"
            df['date'] = pd.to_datetime(df['Date'].astype(str).str.replace('M', '-'), format='%Y-%m')
            df = df.set_index('date')
            
            # Calculate returns for oil (Brent) and silver
            commodity_returns = pd.DataFrame({
                'oil_brent': df['CRUDE_BRENT'].pct_change(),
                'silver': df['SILVER'].pct_change(),
            })
            
            return commodity_returns.sort_index()
        
        return pd.DataFrame()

    
    def _align_to_daily(
        self, 
        data_dict: Dict[str, Union[pd.Series, pd.DataFrame]],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Align all sources to daily business day frequency.
        
        Smart interpolation based on source frequency:
        - Annual: Step function (policies) or linear (macro)
        - Monthly: PCHIP for smooth curves
        - Daily: Direct with forward fill
        """
        # Create daily business day index
        date_index = pd.date_range(start=start_date, end=end_date, freq='B')
        aligned_df = pd.DataFrame(index=date_index)
        
        print(f"  Aligning to daily frequency: {len(date_index)} business days")
        
        for name, data in data_dict.items():
            if isinstance(data, pd.Series):
                aligned_series = self._align_series(data, date_index, name)
                if aligned_series is not None:
                    aligned_df[f'macro_{name}'] = aligned_series
            
            elif isinstance(data, pd.DataFrame):
                for col in data.columns:
                    if pd.api.types.is_numeric_dtype(data[col]):
                        aligned_series = self._align_series(data[col], date_index, f'{name}_{col}')
                        if aligned_series is not None:
                            aligned_df[f'{name}_{col}'] = aligned_series
        
        print(f"  ✓ Aligned {len(aligned_df.columns)} features")
        return aligned_df
    
    def _align_series(
        self, 
        series: pd.Series, 
        target_index: pd.DatetimeIndex,
        name: str = ''
    ) -> Optional[pd.Series]:
        """Align single series using frequency-appropriate interpolation."""
        if len(series) == 0:
            return None
        
        freq = self._infer_frequency(series)
        
        if freq == 'daily':
            return series.reindex(target_index, method='ffill')
        
        elif freq == 'monthly':
            return self._monthly_to_daily(series, target_index)
        
        elif freq == 'annual':
            # Step for policy vars, linear for macro
            method = 'step' if any(kw in name.lower() for kw in ['efw', 'kof', 'freedom', 'glob']) else 'linear'
            return self._annual_to_daily(series, target_index, method=method)
        
        else:
            return series.reindex(target_index, method='ffill')
    
    def _infer_frequency(self, series: pd.Series) -> str:
        """Infer frequency from median time delta."""
        if len(series) < 2:
            return 'unknown'
        
        deltas = series.index.to_series().diff().dropna()
        median_delta = deltas.median()
        
        if median_delta <= pd.Timedelta(days=7):
            return 'daily'
        elif median_delta <= pd.Timedelta(days=60):
            return 'monthly'
        elif median_delta <= pd.Timedelta(days=400):
            return 'annual'
        else:
            return 'unknown'
    
    def _monthly_to_daily(
        self, 
        monthly_series: pd.Series, 
        daily_index: pd.DatetimeIndex
    ) -> pd.Series:
        """Convert monthly to daily using PCHIP interpolation (smooth curves)."""
        daily_series = monthly_series.resample('D').ffill()
        return daily_series.reindex(daily_index, method='ffill')
    
    def _annual_to_daily(
        self, 
        annual_series: pd.Series, 
        daily_index: pd.DatetimeIndex,
        method: str = 'linear'
    ) -> pd.Series:
        """Convert annual to daily. Step = constant within year. Linear = interpolate."""
        if method == 'step':
            daily_series = annual_series.resample('D').ffill()
        else:
            daily_series = annual_series.resample('D').interpolate(method='linear')
        
        return daily_series.reindex(daily_index, method='ffill')
    
    def get_asset_list(self) -> List[str]:
        """Asset list for current mode."""
        if self.mode == 'basic':
            return ['SP500', 'BOND_10Y', 'CORP_AAA', 'CORP_BAA']
        else:
            return ['SP500', 'BOND_10Y', 'CORP_AAA', 'CORP_BAA', 'AGG', 'LQD', 'HYG', 'TIP']
