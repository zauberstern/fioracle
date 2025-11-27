"""
Feature engineering for regime identification.

Creates asset-specific features (Layer C): 21 per asset including downside deviation,
Sortino ratio, volatility metrics.

Builds macro features (Layers A/B): 5-75 features including correlations, PCA components,
regime indicators.

Critical: LOG transform on downside deviation emphasizes risk dynamics.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import warnings

warnings.filterwarnings('ignore')

TRAIN_START = pd.Timestamp('1991-01-01')
TRAIN_END = pd.Timestamp('2023-12-31')
NON_RETURN_ASSET_COLUMNS = {
    'asset_us_treasury_2y_yield',
    'asset_us_10y2y_slope',
}


def engineer_features(
    raw_data: pd.DataFrame
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    print("Engineering features...")
    
    aligned = raw_data.copy()
    aligned = aligned.loc[
        (aligned.index >= TRAIN_START) & (aligned.index <= TRAIN_END)
    ]
    
    asset_returns = _construct_asset_returns(aligned)
    asset_features = {}
    for asset_name, excess_returns in asset_returns.items():
        asset_features[asset_name] = compute_asset_features(excess_returns)
    
    print(f"  ✓ Computed features for {len(asset_features)} assets")
    
    macro_features = _compute_macro_features(aligned, asset_returns)
    
    print(f"  ✓ Computed {len(macro_features.columns)} macro features")
    
    return asset_features, macro_features


def _construct_asset_returns(raw_data: pd.DataFrame) -> Dict[str, pd.Series]:
    asset_returns = {}
    
    risk_free_col = _detect_risk_free_series(raw_data.columns)
    if risk_free_col is None:
        raise ValueError("Risk-free series not found in loaded data.")
    
    risk_free_returns = raw_data[risk_free_col].pct_change()
    
    for col in raw_data.columns:
        if not col.startswith('asset_'):
            continue
        if col in NON_RETURN_ASSET_COLUMNS:
            continue
        if col == risk_free_col:
            continue
        
        asset_return = raw_data[col].pct_change()
        excess_return = asset_return - risk_free_returns
        asset_name = col.replace('asset_', '').upper()
        asset_returns[asset_name] = excess_return
    
    return asset_returns


ASSET_AVG_HALFLIVES = [5, 10, 21]
ASSET_DD_HALFLIVES = [5, 21]
ASSET_SORTINO_HALFLIVES = [5, 10, 21]


def compute_asset_features(
    excess_returns: pd.Series,
) -> pd.DataFrame:
    features = pd.DataFrame(index=excess_returns.index, dtype=float)
    
    avg_map = {}
    for hl in ASSET_AVG_HALFLIVES:
        avg = excess_returns.ewm(halflife=hl, min_periods=hl).mean()
        features[f'avg_return_hl{hl}'] = avg
        avg_map[hl] = avg
    
    required_dd_halflives = sorted(set(ASSET_DD_HALFLIVES + ASSET_SORTINO_HALFLIVES))
    dd_map = {hl: _compute_downside_deviation(excess_returns, hl) for hl in required_dd_halflives}
    
    for hl in ASSET_DD_HALFLIVES:
        log_dd = np.log(dd_map[hl] + 1e-12)
        features[f'log_dd_hl{hl}'] = log_dd
    
    for hl in ASSET_SORTINO_HALFLIVES:
        sortino = avg_map[hl] / (dd_map[hl] + 1e-12)
        features[f'sortino_hl{hl}'] = sortino.replace([np.inf, -np.inf], np.nan)
    
    return _standardize_features(features)


def _compute_downside_deviation(
    returns: pd.Series,
    halflife: int,
) -> pd.Series:
    downside = returns.copy()
    downside[downside > 0] = 0
    squared = downside ** 2
    ewm = squared.ewm(halflife=halflife, min_periods=halflife).mean()
    return np.sqrt(ewm)


def _compute_macro_features(
    raw_data: pd.DataFrame,
    asset_returns: Dict[str, pd.Series],
) -> pd.DataFrame:
    macro_features = pd.DataFrame(index=raw_data.index, dtype=float)
    
    vix_col = _first_column_with_prefix(raw_data, 'macro_vix')
    if vix_col is not None:
        macro_features['vix_logdiff_ewma_63d'] = _ewm_logdiff(raw_data[vix_col], halflife=63)
    
    epu_col = _first_column_with_prefix(raw_data, 'macro_epu')
    if epu_col is not None:
        macro_features['epu_logdiff_ewma_21d'] = _ewm_logdiff(raw_data[epu_col], halflife=21)
    
    globalization_col = _first_column_with_prefix(raw_data, 'macro_globalization')
    if globalization_col is not None:
        macro_features['globalization_logdiff_ewma_21d'] = _ewm_logdiff(raw_data[globalization_col], halflife=21)
    
    freedom_col = _first_column_with_prefix(raw_data, 'macro_economic_freedom')
    if freedom_col is not None:
        macro_features['economic_freedom_logdiff_ewma_21d'] = _ewm_logdiff(raw_data[freedom_col], halflife=21)
    
    broad_money_col = _first_column_with_prefix(raw_data, 'macro_us_broad_money')
    if broad_money_col is not None:
        macro_features['broad_money_logdiff_ewma_63d'] = _ewm_logdiff(raw_data[broad_money_col], halflife=63)
    
    debt_col = _first_column_with_prefix(raw_data, 'macro_us_debt_to_gdp')
    if debt_col is not None:
        macro_features['debt_to_gdp_ratio'] = raw_data[debt_col] / 100.0
    
    cpi_col = _first_column_with_prefix(raw_data, 'macro_us_cpi_level')
    if cpi_col is None:
        cpi_col = _first_column_with_prefix(raw_data, 'macro_us_cpi')
    if cpi_col is not None:
        cpi_series = raw_data[cpi_col]
        macro_features['daily_inflation_rate'] = cpi_series.pct_change()
    
    unemployment_col = _first_column_with_prefix(raw_data, 'macro_us_unemployment')
    if unemployment_col is not None:
        macro_features['unemployment_rate'] = raw_data[unemployment_col] / 100.0
    
    gdp_col = _first_column_with_prefix(raw_data, 'macro_us_gdp_growth')
    if gdp_col is not None:
        macro_features['gdp_growth_rate'] = raw_data[gdp_col] / 100.0
    
    two_year_col = _first_column_with_prefix(raw_data, 'asset_us_treasury_2y_yield')
    if two_year_col is not None:
        two_year_diff = raw_data[two_year_col].diff()
        macro_features['yield_2y_change'] = two_year_diff
        macro_features['yield_2y_change_ewma_21d'] = two_year_diff.ewm(halflife=21, min_periods=21).mean()
    
    slope_col = _first_column_with_prefix(raw_data, 'asset_us_10y2y_slope')
    if slope_col is None:
        slope_col = _first_column_with_prefix(raw_data, 'asset_us_10y2y')
    if slope_col is not None:
        slope_series = raw_data[slope_col]
        macro_features['yield_curve_slope_ewma_10d'] = slope_series.ewm(halflife=10, min_periods=10).mean()
        slope_change = slope_series.diff()
        macro_features['yield_curve_slope_change_ewma_21d'] = slope_change.ewm(halflife=21, min_periods=21).mean()
    
    stock_col = _find_asset_column(asset_returns, ['SP500_INDEX', 'SP500'])
    bond_col = _find_asset_column(asset_returns, ['BLOOMBERG_US_AGGREGATE_TOTAL_RETURN', 'AGGBOND'])
    if stock_col and bond_col:
        stock_returns = asset_returns[stock_col]
        bond_returns = asset_returns[bond_col]
        macro_features['stock_bond_corr_252d'] = stock_returns.rolling(window=252, min_periods=252).corr(bond_returns)
    
    macro_features = macro_features.dropna(axis=1, how='all')
    return macro_features


def _standardize_features(features: pd.DataFrame) -> pd.DataFrame:
    standardized = features.replace([np.inf, -np.inf], np.nan)
    means = standardized.mean(skipna=True)
    stds = standardized.std(skipna=True, ddof=0).replace(0, np.nan)
    standardized = (standardized - means) / stds
    return standardized


def _ewm_logdiff(series: pd.Series, halflife: int) -> pd.Series:
    clean = series.replace(0, np.nan)
    log_diff = np.log(clean).diff()
    return log_diff.ewm(halflife=halflife, min_periods=halflife).mean()


def _first_column_with_prefix(raw_data: pd.DataFrame, prefix: str) -> Optional[str]:
    matches = [col for col in raw_data.columns if col.startswith(prefix)]
    return matches[0] if matches else None


def _find_asset_column(asset_returns: Dict[str, pd.Series], candidates: List[str]) -> Optional[str]:
    for name in candidates:
        if name in asset_returns:
            return name
    return None


def _detect_risk_free_series(columns: List[str]) -> Optional[str]:
    for col in columns:
        if 'risk_free' in col:
            return col
    return None
