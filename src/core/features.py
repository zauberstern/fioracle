"""
Feature engineering for regime identification and forecasting.

Two feature sets per methodology:
1. Return Features (8 features) - For Jump Model regime identification
   - Downside Deviation (log): halflives 5, 21 days
   - Average Return: halflives 5, 10, 21 days
   - Sortino Ratio: halflives 5, 10, 21 days

2. Macro Features (5 features) - Cross-asset features for XGBoost forecasting
   - US Treasury 2Y Yield: diff and EWMA(hl=21)
   - Yield Curve Slope: EWMA(hl=10) and diff EWMA(hl=21)
   - VIX: log-diff and EWMA(hl=63)
   - Stock-Bond Correlation: 252-day rolling

Critical: LOG transform on downside deviation for stable fitting.
Asset-specific: DD excluded for AggBond, Treasury, Gold in JM only.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import warnings

warnings.filterwarnings('ignore')

# Columns that are not investable returns
NON_RETURN_ASSET_COLUMNS = {
    'asset_us_treasury_2y_yield',
    'asset_us_10y2y_slope',
    'asset_us_risk_free_rate',
    'asset_dgs2',
    'asset_t10y2y',
}

# Assets for which DD features should be excluded in JM (per paper methodology)
DD_EXCLUSION_ASSETS = {
    'US_BOND_AGG',
    'US_10Y_GOV_BOND',
    'GOLD',
}

# Feature halflives (trading days) per paper specification
AVG_RETURN_HALFLIVES = [5, 10, 21]  # 1 week, 2 weeks, 1 month
DD_HALFLIVES = [5, 21]  # 1 week, 1 month (only 2 to reduce correlation)
SORTINO_HALFLIVES = [5, 10, 21]  # Same as avg return


def engineer_features(
    raw_data: pd.DataFrame,
    exclude_dd_for_jm: Optional[List[str]] = None
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    """
    Engineer features from raw data.
    
    Args:
        raw_data: DataFrame with asset prices and macro indicators
        exclude_dd_for_jm: List of assets to exclude DD features for JM
        
    Returns:
        Tuple of (asset_features_dict, macro_features_df)
        - asset_features_dict: {asset_name: DataFrame with 8 return features}
        - macro_features_df: DataFrame with 5 cross-asset macro features
    """
    print("Engineering features...")
    
    aligned = raw_data.copy()
    
    # Build excess returns for each asset
    asset_returns = _construct_asset_returns(aligned)
    
    # Compute asset-specific return features
    asset_features = {}
    for asset_name, excess_returns in asset_returns.items():
        # Check if DD should be excluded for this asset (for JM only)
        exclude_dd = False
        if exclude_dd_for_jm:
            for pattern in exclude_dd_for_jm:
                if pattern.upper() in asset_name.upper():
                    exclude_dd = True
                    break
        
        asset_features[asset_name] = compute_asset_features(excess_returns, exclude_dd=exclude_dd)
    
    print(f"  ✓ Computed features for {len(asset_features)} assets")
    
    # Compute cross-asset macro features
    macro_features = _compute_macro_features(aligned, asset_returns)
    
    print(f"  ✓ Computed {len(macro_features.columns)} macro features")
    
    return asset_features, macro_features


def _construct_asset_returns(raw_data: pd.DataFrame) -> Dict[str, pd.Series]:
    """Construct excess returns (vs risk-free) for each asset including SP500 for correlation."""
    asset_returns = {}
    
    risk_free_col = _detect_risk_free_series(raw_data.columns)
    if risk_free_col is None:
        warnings.warn("Risk-free series not found. Using zero risk-free rate.")
        risk_free_returns = pd.Series(0.0, index=raw_data.index)
    else:
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
    
    # SP500 is loaded separately (for stock-bond correlation) but not investable
    # Include it in asset_returns for feature computation only
    sp500_col = [c for c in raw_data.columns if 'sp500' in c.lower()]
    if sp500_col and 'SP500_TOTAL_RETURN' not in asset_returns:
        sp500_return = raw_data[sp500_col[0]].pct_change()
        sp500_excess = sp500_return - risk_free_returns
        asset_returns['SP500_TOTAL_RETURN'] = sp500_excess
    
    return asset_returns


def compute_asset_features(
    excess_returns: pd.Series,
    exclude_dd: bool = False
) -> pd.DataFrame:
    """
    Compute 8 return features for a single asset.
    
    Features (per paper Table 2):
    1-2. Log Downside Deviation (hl=5, 21) - excluded for some assets
    3-5. Average Return (hl=5, 10, 21)
    6-8. Sortino Ratio (hl=5, 10, 21)
    
    Args:
        excess_returns: Asset excess return series
        exclude_dd: If True, exclude DD features (for AggBond, Treasury, Gold in JM)
    """
    features = pd.DataFrame(index=excess_returns.index, dtype=float)
    
    # Compute average returns for all halflives
    avg_map = {}
    for hl in AVG_RETURN_HALFLIVES:
        avg = excess_returns.ewm(halflife=hl, min_periods=hl).mean()
        features[f'avg_return_hl{hl}'] = avg
        avg_map[hl] = avg
    
    # Compute downside deviation for all needed halflives
    required_dd_halflives = sorted(set(DD_HALFLIVES + SORTINO_HALFLIVES))
    dd_map = {hl: _compute_downside_deviation(excess_returns, hl) for hl in required_dd_halflives}
    
    # Add log DD features (unless excluded)
    if not exclude_dd:
        for hl in DD_HALFLIVES:
            log_dd = np.log(dd_map[hl] + 1e-12)
            features[f'log_dd_hl{hl}'] = log_dd
    
    # Compute Sortino ratios
    for hl in SORTINO_HALFLIVES:
        # Use appropriate avg_return halflife
        avg_hl = hl if hl in avg_map else min(avg_map.keys(), key=lambda x: abs(x - hl))
        sortino = avg_map[avg_hl] / (dd_map[hl] + 1e-12)
        features[f'sortino_hl{hl}'] = sortino.replace([np.inf, -np.inf], np.nan)
    
    return _standardize_features(features)


def _compute_downside_deviation(
    returns: pd.Series,
    halflife: int,
) -> pd.Series:
    """
    Compute exponentially weighted downside deviation.
    
    Downside deviation emphasizes downside risk (negative returns only).
    """
    downside = returns.copy()
    downside[downside > 0] = 0
    squared = downside ** 2
    ewm = squared.ewm(halflife=halflife, min_periods=halflife).mean()
    return np.sqrt(ewm)


def _compute_macro_features(
    raw_data: pd.DataFrame,
    asset_returns: Dict[str, pd.Series],
) -> pd.DataFrame:
    """
    Compute macro features based on available data.
    
    Core Features (based on user's macro_universe):
    1. VIX: log-diff and EWMA(hl=63) - market volatility
    2. GPR: log-diff and EWMA(hl=21) - geopolitical risk
    3. US Debt/GDP: level and diff - fiscal sustainability
    
    Optional Features (if yield data available):
    4. Yield Curve Slope: level and changes
    5. Stock-Bond Correlation: regime indicator
    """
    macro_features = pd.DataFrame(index=raw_data.index, dtype=float)
    
    # ========================================================================
    # CORE FEATURE 1: VIX - Market Volatility
    # ========================================================================
    vix_col = _first_column_containing(raw_data, ['macro_vix', 'macro_cboe_vix', 'macro_synthesized_vix'])
    if vix_col is not None:
        vix_data = raw_data[vix_col]
        # Log-diff with EWMA smoothing
        macro_features['vix_logdiff_ewma63'] = _ewm_logdiff(vix_data, halflife=63)
        # Also include level (normalized)
        vix_level = vix_data.ewm(halflife=21, min_periods=21).mean()
        macro_features['vix_level_ewma21'] = (vix_level - vix_level.mean()) / vix_level.std()
    
    # ========================================================================
    # CORE FEATURE 2: GPR - Geopolitical Risk
    # ========================================================================
    gpr_col = _first_column_containing(raw_data, ['macro_gpr', 'macro_gprd'])
    if gpr_col is not None:
        gpr_data = raw_data[gpr_col]
        # Log-diff with EWMA smoothing
        macro_features['gpr_logdiff_ewma21'] = _ewm_logdiff(gpr_data, halflife=21)
        # Also include level (normalized)
        gpr_level = gpr_data.ewm(halflife=21, min_periods=21).mean()
        macro_features['gpr_level_ewma21'] = (gpr_level - gpr_level.mean()) / gpr_level.std()
    
    # ========================================================================
    # CORE FEATURE 3: US Debt to GDP - Fiscal Risk
    # ========================================================================
    debt_col = _first_column_containing(raw_data, ['macro_us_debt_to_gdp', 'macro_debt_gdp'])
    if debt_col is not None:
        debt_data = raw_data[debt_col]
        # Level (normalized)
        macro_features['debt_gdp_level'] = (debt_data - debt_data.mean()) / debt_data.std()
        # Rate of change
        debt_diff = debt_data.diff()
        macro_features['debt_gdp_change_ewma63'] = debt_diff.ewm(halflife=63, min_periods=63).mean()
    
    # ========================================================================
    # OPTIONAL: Yield Curve Features (if available)
    # ========================================================================
    slope_col = _first_column_containing(raw_data, ['asset_us_10y2y_slope', 'asset_t10y2y'])
    if slope_col is not None:
        slope_series = raw_data[slope_col]
        macro_features['slope_ewma10'] = slope_series.ewm(halflife=10, min_periods=10).mean()
        slope_diff = slope_series.diff()
        macro_features['slope_diff_ewma21'] = slope_diff.ewm(halflife=21, min_periods=21).mean()
    
    two_year_col = _first_column_containing(raw_data, ['asset_us_treasury_2y_yield', 'asset_dgs2'])
    if two_year_col is not None:
        two_year_diff = raw_data[two_year_col].diff()
        macro_features['yield_2y_diff_ewma21'] = two_year_diff.ewm(halflife=21, min_periods=21).mean()
    
    # ========================================================================
    # CORE FEATURE 4: Stock-Bond Correlation (key regime indicator)
    # ========================================================================
    stock_col = _find_asset_column(asset_returns, ['SP500_TOTAL_RETURN', 'SP500'])
    bond_col = _find_asset_column(asset_returns, ['US_BOND_AGG', 'IBOXX_USD_TREASURY', 'US_10Y_GOV_BOND'])
    
    if stock_col and bond_col:
        stock_returns = asset_returns[stock_col]
        bond_returns = asset_returns[bond_col]
        # Rolling 252-day correlation - key for understanding regime dynamics
        macro_features['stock_bond_corr_252d'] = stock_returns.rolling(window=252, min_periods=126).corr(bond_returns)
    elif len(asset_returns) >= 2 and bond_col:
        # Fallback: correlation between bonds and another risky asset
        other_assets = [k for k in asset_returns.keys() if k != bond_col and 'SP500' not in k.upper()]
        if other_assets:
            other_col = other_assets[0]
            r1 = asset_returns[bond_col]
            r2 = asset_returns[other_col]
            macro_features['bond_asset_corr_252d'] = r1.rolling(window=252, min_periods=126).corr(r2)
    
    # Clean up
    macro_features = macro_features.dropna(axis=1, how='all')
    return macro_features


def _standardize_features(features: pd.DataFrame) -> pd.DataFrame:
    """Standardize features to zero mean, unit variance."""
    standardized = features.replace([np.inf, -np.inf], np.nan)
    means = standardized.mean(skipna=True)
    stds = standardized.std(skipna=True, ddof=0).replace(0, np.nan)
    standardized = (standardized - means) / stds
    return standardized


def _ewm_logdiff(series: pd.Series, halflife: int) -> pd.Series:
    """Compute log-difference and exponentially weighted moving average."""
    clean = series.replace(0, np.nan)
    log_diff = np.log(clean).diff()
    return log_diff.ewm(halflife=halflife, min_periods=halflife).mean()


def _first_column_containing(raw_data: pd.DataFrame, prefixes: List[str]) -> Optional[str]:
    """Find first column matching any of the prefixes."""
    for prefix in prefixes:
        matches = [col for col in raw_data.columns if col.lower().startswith(prefix.lower())]
        if matches:
            return matches[0]
    return None


def _find_asset_column(asset_returns: Dict[str, pd.Series], candidates: List[str]) -> Optional[str]:
    """Find matching asset from candidates list."""
    for name in candidates:
        if name in asset_returns:
            return name
        # Try partial match
        for key in asset_returns.keys():
            if name.upper() in key.upper():
                return key
    return None


def _detect_risk_free_series(columns: List[str]) -> Optional[str]:
    """Detect risk-free rate column."""
    for col in columns:
        if 'risk_free' in col.lower():
            return col
    return None


def get_expanded_feature_set(
    asset_features: pd.DataFrame,
    macro_features: pd.DataFrame
) -> pd.DataFrame:
    """
    Combine asset-specific and macro features for XGBoost forecasting.
    
    The expanded feature set includes all 8 return features (including DD
    even for assets that excluded it in JM) plus all macro features.
    
    Args:
        asset_features: DataFrame with asset-specific return features
        macro_features: DataFrame with cross-asset macro features
        
    Returns:
        Combined feature DataFrame
    """
    # Align indices
    common_idx = asset_features.index.intersection(macro_features.index)
    
    expanded = pd.DataFrame(index=common_idx)
    
    # Add all asset features
    for col in asset_features.columns:
        if col in asset_features:
            expanded[col] = asset_features.loc[common_idx, col]
    
    # Add all macro features
    for col in macro_features.columns:
        expanded[col] = macro_features.loc[common_idx, col]
    
    return expanded
