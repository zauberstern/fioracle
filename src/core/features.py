"""
Feature engineering for regime identification and forecasting.

Two feature sets:
1. Return Features (8 features per asset) - For Jump Model
2. Macro Features - Cross-asset features for XGBoost forecasting

IMPORTANT: Uses ancillary data (RF rate, SP500, yields) for features
but these are NEVER used in portfolio construction.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import warnings

warnings.filterwarnings('ignore')

# Halflives for return features
AVG_RETURN_HALFLIVES = [5, 10, 21]
DD_HALFLIVES = [5, 21]
SORTINO_HALFLIVES = [5, 10, 21]


def engineer_features(
    raw_data: pd.DataFrame,
    config: Optional[dict] = None
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    """
    Engineer features from raw data.
    
    Returns:
        Tuple of (asset_features_dict, macro_features_df)
    """
    print("Engineering features...")
    
    # Get risk-free returns from ancillary data
    rf_returns = _get_risk_free_returns(raw_data)
    
    # Build asset returns (investable assets ONLY)
    asset_returns = _construct_asset_returns(raw_data, rf_returns)
    
    # Compute asset-specific features
    asset_features = {}
    for asset_name, excess_returns in asset_returns.items():
        asset_features[asset_name] = compute_asset_features(excess_returns)
    
    print(f"  ✓ Computed features for {len(asset_features)} assets")
    
    # Compute macro features (uses ancillary SP500, yields)
    macro_features = _compute_macro_features(raw_data, asset_returns, config=config)
    
    print(f"  ✓ Computed {len(macro_features.columns)} macro features")
    
    return asset_features, macro_features


def _get_risk_free_returns(raw_data: pd.DataFrame) -> pd.Series:
    """Get risk-free rate returns from ancillary data."""
    rf_col = [c for c in raw_data.columns if 'ancillary_risk_free' in c.lower()]
    if rf_col:
        rf_series = raw_data[rf_col[0]].pct_change()
        # Forward-fill short gaps, but don't fill long periods of missing data
        rf_series = rf_series.ffill(limit=5)
        return rf_series
    
    # Fallback to NaN (not zero!) - this will propagate and be handled downstream
    warnings.warn("Risk-free rate not found in ancillary data. Returns will be raw (not excess).")
    return pd.Series(np.nan, index=raw_data.index)


def _construct_asset_returns(raw_data: pd.DataFrame, rf_returns: pd.Series) -> Dict[str, pd.Series]:
    """Construct excess returns for INVESTABLE assets only."""
    asset_returns = {}
    
    # Check if RF is available (not all NaN)
    rf_available = rf_returns.notna().any()
    
    for col in raw_data.columns:
        # Only process asset_ columns (NOT ancillary_)
        if not col.startswith('asset_'):
            continue
        
        asset_return = raw_data[col].pct_change()
        
        # Compute excess return only where both asset and RF are available
        if rf_available:
            # Align RF to asset's index and compute excess return
            rf_aligned = rf_returns.reindex(asset_return.index)
            excess_return = asset_return - rf_aligned.fillna(0.0)  # Use 0 only where RF unavailable
        else:
            # If no RF data at all, use raw returns (not excess)
            excess_return = asset_return
        
        # Clean asset name
        asset_name = col.replace('asset_', '').upper()
        asset_returns[asset_name] = excess_return
    
    return asset_returns


def compute_asset_features(excess_returns: pd.Series) -> pd.DataFrame:
    """Compute 8 return features for a single asset."""
    features = pd.DataFrame(index=excess_returns.index, dtype=float)
    
    # Average returns
    avg_map = {}
    for hl in AVG_RETURN_HALFLIVES:
        avg = excess_returns.ewm(halflife=hl, min_periods=hl).mean()
        features[f'avg_return_hl{hl}'] = avg
        avg_map[hl] = avg
    
    # Downside deviation
    required_halflives = sorted(set(DD_HALFLIVES + SORTINO_HALFLIVES))
    dd_map = {hl: _compute_downside_deviation(excess_returns, hl) for hl in required_halflives}
    
    # Log DD features
    for hl in DD_HALFLIVES:
        log_dd = np.log(dd_map[hl] + 1e-12)
        features[f'log_dd_hl{hl}'] = log_dd
    
    # Sortino ratios
    for hl in SORTINO_HALFLIVES:
        avg_hl = hl if hl in avg_map else min(avg_map.keys(), key=lambda x: abs(x - hl))
        sortino = avg_map[avg_hl] / (dd_map[hl] + 1e-12)
        features[f'sortino_hl{hl}'] = sortino.replace([np.inf, -np.inf], np.nan)
    
    return _standardize_features(features)


def _compute_downside_deviation(returns: pd.Series, halflife: int) -> pd.Series:
    """Compute exponentially weighted downside deviation."""
    downside = returns.copy()
    downside[downside > 0] = 0
    squared = downside ** 2
    ewm = squared.ewm(halflife=halflife, min_periods=halflife).mean()
    return np.sqrt(ewm)


def _apply_macro_lag(series: pd.Series, lag_days: int, enabled: bool) -> pd.Series:
    """Shift data forward to prevent look-ahead bias from publication delays."""
    if not enabled or lag_days is None or lag_days <= 0:
        return series
    return series.shift(lag_days)


def _compute_macro_features(
    raw_data: pd.DataFrame,
    asset_returns: Dict[str, pd.Series],
    config: Optional[dict] = None
) -> pd.DataFrame:
    """
    Compute macro features from macro_universe and ancillary data.
    
    Includes VIX, GPR, Debt/GDP, HY OAS, inflation, yield curve, and stock-bond correlation.
    Optionally applies publication lags to prevent look-ahead bias.
    """
    macro_features = pd.DataFrame(index=raw_data.index, dtype=float)
    
    # Get macro lag configuration
    macro_lags_cfg = (config or {}).get('macro_lags', {})
    lags_enabled = macro_lags_cfg.get('enabled', False)
    lag_vix = macro_lags_cfg.get('vix_days', 0)
    lag_gpr = macro_lags_cfg.get('gpr_days', 0)
    lag_epu = macro_lags_cfg.get('epu_days', 0)
    lag_debt = macro_lags_cfg.get('debt_to_gdp_days', 0)
    lag_infl = macro_lags_cfg.get('inflation_days', 0)
    lag_gdp = macro_lags_cfg.get('gdp_growth_days', 0)
    lag_unemp = macro_lags_cfg.get('unemployment_days', 0)
    lag_hy = macro_lags_cfg.get('hy_oas_days', 0)
    
    # ========================================================================
    # VIX - Market Volatility
    # ========================================================================
    vix_col = _find_column(raw_data, ['macro_vix', 'macro_synthesized_vix'])
    if vix_col:
        vix_data = _apply_macro_lag(raw_data[vix_col], lag_vix, lags_enabled)
        # Forward-fill gaps up to 5 days for VIX (daily data)
        vix_data = vix_data.ffill(limit=5)
        macro_features['vix_logdiff_ewma63'] = _ewm_logdiff(vix_data, halflife=63)
        vix_level = vix_data.ewm(halflife=21, min_periods=21).mean()
        vix_std = vix_level.std()
        if vix_std > 1e-10:
            macro_features['vix_level_norm'] = (vix_level - vix_level.mean()) / vix_std
    
    # ========================================================================
    # GPRI - Geopolitical Risk
    # ========================================================================
    gpr_col = _find_column(raw_data, ['macro_gpri', 'macro_gpr'])
    if gpr_col:
        gpr_data = _apply_macro_lag(raw_data[gpr_col], lag_gpr, lags_enabled)
        # Forward-fill gaps up to 7 days for GPR (may have weekends/holidays)
        gpr_data = gpr_data.ffill(limit=7)
        macro_features['gpr_logdiff_ewma21'] = _ewm_logdiff(gpr_data, halflife=21)
        gpr_level = gpr_data.ewm(halflife=21, min_periods=21).mean()
        gpr_std = gpr_level.std()
        if gpr_std > 1e-10:
            macro_features['gpr_level_norm'] = (gpr_level - gpr_level.mean()) / gpr_std
    
    # ========================================================================
    # US Debt to GDP (quarterly data - forward-fill up to 90 days)
    # ========================================================================
    debt_col = _find_column(raw_data, ['macro_us_debt_to_gdp'])
    if debt_col:
        debt_data = _apply_macro_lag(raw_data[debt_col], lag_debt, lags_enabled)
        debt_data = debt_data.ffill(limit=90)  # Quarterly data
        debt_std = debt_data.std()
        if debt_std > 1e-10:
            macro_features['debt_gdp_level'] = (debt_data - debt_data.mean()) / debt_std
        debt_diff = debt_data.diff()
        macro_features['debt_gdp_change_ewma63'] = debt_diff.ewm(halflife=63, min_periods=63).mean()
    
    # ========================================================================
    # HY Corporate OAS (Credit Spreads)
    # ========================================================================
    hy_col = _find_column(raw_data, ['macro_us_hy_corp_oas'])
    if hy_col:
        hy_data = _apply_macro_lag(raw_data[hy_col], lag_hy, lags_enabled)
        hy_data = hy_data.ffill(limit=5)
        hy_returns = hy_data.pct_change()
        macro_features['hy_oas_return_ewma21'] = hy_returns.ewm(halflife=21, min_periods=21).mean()
        hy_std = hy_data.std()
        if hy_std > 1e-10:
            macro_features['hy_oas_level_norm'] = (hy_data - hy_data.mean()) / hy_std
    
    # ========================================================================
    # EPU - Economic Policy Uncertainty (monthly data - forward-fill up to 30 days)
    # ========================================================================
    epu_col = _find_column(raw_data, ['macro_epu'])
    if epu_col:
        epu_data = _apply_macro_lag(raw_data[epu_col], lag_epu, lags_enabled)
        epu_data = epu_data.ffill(limit=30)
        macro_features['epu_logdiff_ewma21'] = _ewm_logdiff(epu_data, halflife=21)
        epu_level = epu_data.ewm(halflife=21, min_periods=21).mean()
        epu_std = epu_level.std()
        if epu_std > 1e-10:
            macro_features['epu_level_norm'] = (epu_level - epu_level.mean()) / epu_std
    
    # ========================================================================
    # GDP Growth (quarterly data - forward-fill up to 90 days)
    # ========================================================================
    gdp_col = _find_column(raw_data, ['macro_us_gdp_growth'])
    if gdp_col:
        gdp_data = _apply_macro_lag(raw_data[gdp_col], lag_gdp, lags_enabled)
        gdp_data = gdp_data.ffill(limit=90)
        macro_features['gdp_growth_level'] = gdp_data / 100.0
        gdp_ewm = gdp_data.ewm(halflife=63, min_periods=63).mean()
        macro_features['gdp_growth_ewma63'] = gdp_ewm / 100.0
    
    # ========================================================================
    # Unemployment Rate (monthly data - forward-fill up to 30 days)
    # ========================================================================
    unemp_col = _find_column(raw_data, ['macro_us_unemployment_rate'])
    if unemp_col:
        unemp_data = _apply_macro_lag(raw_data[unemp_col], lag_unemp, lags_enabled)
        unemp_data = unemp_data.ffill(limit=30)
        macro_features['unemployment_level'] = unemp_data / 100.0
        unemp_diff = unemp_data.diff()
        macro_features['unemployment_change_ewma21'] = unemp_diff.ewm(halflife=21, min_periods=21).mean()
    
    # ========================================================================
    # US Inflation (monthly data - forward-fill up to 30 days)
    # ========================================================================
    infl_col = _find_column(raw_data, ['macro_us_inflation_rate', 'macro_us_inflation'])
    if infl_col:
        infl_data = _apply_macro_lag(raw_data[infl_col], lag_infl, lags_enabled)
        infl_data = infl_data.ffill(limit=30)
        # Inflation is already in % terms
        macro_features['inflation_level'] = infl_data / 100.0
        infl_diff = infl_data.diff()
        macro_features['inflation_change_ewma21'] = infl_diff.ewm(halflife=21, min_periods=21).mean()
    
    # ========================================================================
    # Yield Curve Features (from ancillary - daily, forward-fill weekends)
    # ========================================================================
    yield_2y_col = _find_column(raw_data, ['ancillary_yield_2y'])
    slope_col = _find_column(raw_data, ['ancillary_yield_slope'])
    
    if yield_2y_col:
        yield_2y = raw_data[yield_2y_col].ffill(limit=5)
        yield_2y_diff = yield_2y.diff()
        macro_features['yield_2y_diff_ewma21'] = yield_2y_diff.ewm(halflife=21, min_periods=21).mean()
    
    if slope_col:
        slope = raw_data[slope_col].ffill(limit=5)
        macro_features['yield_slope_ewma10'] = slope.ewm(halflife=10, min_periods=10).mean()
        slope_diff = slope.diff()
        macro_features['yield_slope_diff_ewma21'] = slope_diff.ewm(halflife=21, min_periods=21).mean()
    
    # ========================================================================
    # Stock-Bond Correlation (uses ancillary SP500)
    # ========================================================================
    sp500_col = _find_column(raw_data, ['ancillary_sp500'])
    bond_col = _find_asset_column(asset_returns, ['US_BOND_AGG', 'IBOXX_USD_TREASURY', 'US_10Y_GOV_BOND'])
    
    if sp500_col and bond_col:
        sp500_returns = raw_data[sp500_col].pct_change()
        bond_returns = asset_returns[bond_col]
        # Align the series before computing correlation
        common_idx = sp500_returns.dropna().index.intersection(bond_returns.dropna().index)
        if len(common_idx) > 252:
            sp500_aligned = sp500_returns.reindex(common_idx)
            bond_aligned = bond_returns.reindex(common_idx)
            corr = sp500_aligned.rolling(window=252, min_periods=126).corr(bond_aligned)
            macro_features['stock_bond_corr_252d'] = corr.reindex(raw_data.index)
    
    # Clean up
    macro_features = macro_features.dropna(axis=1, how='all')
    return macro_features


def _find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Find first matching column."""
    for name in candidates:
        matches = [c for c in df.columns if name.lower() in c.lower()]
        if matches:
            return matches[0]
    return None


def _find_asset_column(asset_returns: Dict[str, pd.Series], candidates: List[str]) -> Optional[str]:
    """Find matching asset."""
    for name in candidates:
        if name in asset_returns:
            return name
        for key in asset_returns.keys():
            if name.upper() in key.upper():
                return key
    return None


def _ewm_logdiff(series: pd.Series, halflife: int) -> pd.Series:
    """Compute log-difference and EWM."""
    clean = series.replace(0, np.nan)
    log_diff = np.log(clean).diff()
    return log_diff.ewm(halflife=halflife, min_periods=halflife).mean()


def _standardize_features(features: pd.DataFrame) -> pd.DataFrame:
    """Standardize features to zero mean, unit variance."""
    standardized = features.replace([np.inf, -np.inf], np.nan)
    means = standardized.mean(skipna=True)
    stds = standardized.std(skipna=True, ddof=0).replace(0, np.nan)
    return (standardized - means) / stds


def get_expanded_feature_set(asset_features: pd.DataFrame, macro_features: pd.DataFrame) -> pd.DataFrame:
    """Combine asset and macro features for XGBoost."""
    common_idx = asset_features.index.intersection(macro_features.index)
    
    expanded = pd.DataFrame(index=common_idx)
    for col in asset_features.columns:
        expanded[col] = asset_features.loc[common_idx, col]
    for col in macro_features.columns:
        expanded[col] = macro_features.loc[common_idx, col]
    
    return expanded
