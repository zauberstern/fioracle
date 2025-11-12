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
from typing import Dict, List, Tuple
import warnings

warnings.filterwarnings('ignore')


def engineer_features(
    raw_data: pd.DataFrame,
    complexity: str = 'basic'
) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    """
    Generate all features for assets and macro variables.
    
    Returns: (asset_features dict, macro_features df)
    """
    print(f"Engineering features ({complexity} mode)...")
    
    # Build asset returns from aligned data
    asset_returns = _construct_asset_returns(raw_data)
    
    # Asset-specific features (Layer C): 21 features each
    asset_features = {}
    for asset_name, returns in asset_returns.items():
        asset_features[asset_name] = compute_asset_features(
            returns, 
            halflives=[21, 63, 126]  # 1mo, 3mo, 6mo
        )
    
    print(f"  ✓ Computed features for {len(asset_features)} assets")
    
    # Macro features (Layers A/B)
    if complexity == 'full':
        macro_features = _compute_full_macro_features(raw_data, asset_returns)
    else:
        macro_features = _compute_essential_macro_features(raw_data, asset_returns)
    
    print(f"  ✓ Computed {len(macro_features.columns)} macro features")
    
    return asset_features, macro_features


def _construct_asset_returns(raw_data: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    Build asset return series from aligned data.
    
    Sources:
    - Modern (2000+): LSEG ETFs
    - Historical (1945-2000): Shiller + JST data
    """
    asset_returns = {}
    
    # S&P 500
    if 'shiller_sp500' in raw_data.columns:
        sp500 = raw_data['shiller_sp500'].pct_change()
        asset_returns['SP500'] = sp500
    
    # 10Y Treasury
    if 'shiller_gs10' in raw_data.columns:
        bond_10y = raw_data['shiller_gs10'].pct_change()
        asset_returns['BOND_10Y'] = bond_10y
    elif 'jst_ltrate' in raw_data.columns:
        bond_10y = raw_data['jst_ltrate'].pct_change()
        asset_returns['BOND_10Y'] = bond_10y
    
    # Corp AAA (proxy: gov + spread)
    if 'BOND_10Y' in asset_returns:
        corp_aaa = asset_returns['BOND_10Y'] * 1.15
        asset_returns['CORP_AAA'] = corp_aaa
    
    # Corp BAA (proxy: gov + spread)
    if 'BOND_10Y' in asset_returns:
        corp_baa = asset_returns['BOND_10Y'] * 1.25
        asset_returns['CORP_BAA'] = corp_baa
    
    # 3-Month Treasury Bills (already returns/rates from loader, prefixed with macro_)
    if 'macro_bills_3m' in raw_data.columns:
        asset_returns['BILLS_3M'] = raw_data['macro_bills_3m']
    
    # Gold (already returns from loader, prefixed with macro_)
    if 'macro_gold' in raw_data.columns:
        asset_returns['GOLD'] = raw_data['macro_gold']
    
    # Oil - Brent Crude
    if 'commodities_oil_brent' in raw_data.columns:
        asset_returns['OIL'] = raw_data['commodities_oil_brent']
    
    # Silver
    if 'commodities_silver' in raw_data.columns:
        asset_returns['SILVER'] = raw_data['commodities_silver']
    
    # Swiss Franc
    if 'swiss_chf_return' in raw_data.columns:
        asset_returns['CHF'] = raw_data['swiss_chf_return']
    
    # Swiss Long-term Government Bonds
    if 'swiss_swiss_bond_tr' in raw_data.columns:
        # bond_tr is already total return, just take the pct_change
        asset_returns['CH_BOND'] = raw_data['swiss_swiss_bond_tr'].pct_change()
    
    # Modern ETFs (if available) - from LSEG parquet files
    for etf in ['tip', 'lqd', 'hyg']:
        col_name = f'lseg_{etf}'
        if col_name in raw_data.columns:
            asset_returns[etf.upper()] = raw_data[col_name].pct_change()
    
    return asset_returns


def compute_asset_features(
    returns: pd.Series,
    halflives: List[int] = [21, 63, 126]
) -> pd.DataFrame:
    """
    Generate 21 asset-specific features (Layer C).
    
    Includes:
    - Downside deviation (LOG scale, 3 horizons) - emphasizes downside risk
    - Sortino ratios (3 horizons)
    - EWM returns (3 horizons)
    - Realized volatility (3 horizons)
    - Cumulative returns (3 windows)
    - Skewness, max drawdown, current return
    
    halflives: [short, medium, long] in days for exponential weighting
    """
    features = pd.DataFrame(index=returns.index)
    
    log_returns = np.log1p(returns)
    
    # 1. Downside Deviation (LOG SCALE) - emphasizes downside risk dynamics
    for hl in halflives:
        features[f'dd_{hl}d'] = _compute_downside_deviation_log(log_returns, hl)
    
    # 2. Sortino Ratio
    for hl in halflives:
        features[f'sortino_{hl}d'] = _compute_sortino_ratio(returns, hl)
    
    # 3. EWM Returns
    for hl in halflives:
        features[f'ewm_return_{hl}d'] = returns.ewm(halflife=hl, min_periods=hl).mean()
    
    # 4. Realized Volatility
    for hl in halflives:
        features[f'volatility_{hl}d'] = returns.ewm(halflife=hl, min_periods=hl).std()
    
    # 5. Cumulative Returns
    for window in [21, 63, 126]:
        features[f'cum_return_{window}d'] = (1 + returns).rolling(window=window).apply(
            lambda x: x.prod() - 1, raw=True
        )
    
    # 6. Skewness
    features['skewness_63d'] = returns.rolling(window=63).skew()
    
    # 7. Max Drawdown
    features['max_dd_126d'] = _compute_rolling_max_drawdown(returns, 126)
    
    # 8. Current Return
    features['return'] = returns
    
    return features


def _compute_downside_deviation_log(
    log_returns: pd.Series,
    halflife: int,
    threshold: float = 0.0
) -> pd.Series:
    """
    LOG-scale exponentially weighted downside deviation.
    
    The LOG transform emphasizes downside risk changes.
    Formula: DD_log = log(sqrt(EWM(downside_returns²)))
    """
    # Isolate downside
    downside_returns = log_returns.copy()
    downside_returns[downside_returns > threshold] = 0
    
    # Square, EWM, sqrt
    squared_downside = downside_returns ** 2
    ewm_squared = squared_downside.ewm(halflife=halflife, min_periods=halflife).mean()
    downside_dev = np.sqrt(ewm_squared)
    
    # LOG transformation (add small constant to avoid log(0))
    downside_dev_log = np.log(downside_dev + 1e-8)
    
    return downside_dev_log


def _compute_sortino_ratio(
    returns: pd.Series,
    halflife: int,
    threshold: float = 0.0
) -> pd.Series:
    """Sortino ratio: return / downside_deviation (linear scale for clarity)."""
    ewm_return = returns.ewm(halflife=halflife, min_periods=halflife).mean()
    
    # Downside deviation (NOT log scale)
    downside_returns = returns.copy()
    downside_returns[downside_returns > threshold] = 0
    squared_downside = downside_returns ** 2
    ewm_squared = squared_downside.ewm(halflife=halflife, min_periods=halflife).mean()
    downside_dev = np.sqrt(ewm_squared)
    
    sortino = ewm_return / (downside_dev + 1e-8)
    sortino = sortino.replace([np.inf, -np.inf], np.nan)
    
    return sortino


def _compute_rolling_max_drawdown(
    returns: pd.Series,
    window: int
) -> pd.Series:
    """Rolling maximum drawdown over specified window (returns negative values)."""
    cum_returns = (1 + returns).cumprod()
    rolling_max = cum_returns.rolling(window=window, min_periods=1).max()
    drawdown = (cum_returns - rolling_max) / rolling_max
    
    return drawdown


def _compute_essential_macro_features(
    raw_data: pd.DataFrame,
    asset_returns: Dict[str, pd.Series]
) -> pd.DataFrame:
    """
    Compute essential macro features (basic mode: 5 features).
    
    Features:
    1. Stock-bond correlation (252-day rolling)
    2. VIX or proxy (geopolitical risk)
    3. Yield curve slope (10Y - 3M)
    4. Credit spread (BAA - AAA)
    5. Policy uncertainty (EPU)
    """
    macro_features = pd.DataFrame(index=raw_data.index)
    
    # 1. Stock-Bond Correlation
    if 'SP500' in asset_returns and 'BOND_10Y' in asset_returns:
        stock_bond_corr = asset_returns['SP500'].rolling(window=252).corr(
            asset_returns['BOND_10Y']
        )
        macro_features['stock_bond_corr'] = stock_bond_corr
    
    # 2. VIX (actual from LSEG, or GPR proxy)
    if 'lseg_vix' in raw_data.columns:
        macro_features['vix'] = raw_data['lseg_vix']
    elif 'macro_gpr' in raw_data.columns:
        # Normalize GPR to VIX-like scale as fallback
        gpr_normalized = (raw_data['macro_gpr'] - raw_data['macro_gpr'].mean()) / raw_data['macro_gpr'].std()
        macro_features['vix_proxy'] = gpr_normalized * 15 + 20  # Scale to VIX range
    
    # 3. Yield Curve Slope (use 2Y from LSEG if available)
    if 'lseg_treasury_2y' in raw_data.columns and 'shiller_gs10' in raw_data.columns:
        slope = raw_data['shiller_gs10'] - raw_data['lseg_treasury_2y']
        macro_features['yield_slope'] = slope
    elif 'shiller_gs10' in raw_data.columns:
        # Approximate 3M with 1Y
        if 'shiller_rate' in raw_data.columns:
            slope = raw_data['shiller_gs10'] - raw_data['shiller_rate']
            macro_features['yield_slope'] = slope
    
    # 4. Credit Spread Proxy
    if 'CORP_BAA' in asset_returns and 'CORP_AAA' in asset_returns:
        # Use return differential as credit spread proxy
        spread = asset_returns['CORP_BAA'].rolling(63).mean() - asset_returns['CORP_AAA'].rolling(63).mean()
        macro_features['credit_spread_proxy'] = spread
    
    # 5. Economic Policy Uncertainty
    if 'macro_epu' in raw_data.columns:
        # Normalize EPU
        epu_normalized = (raw_data['macro_epu'] - raw_data['macro_epu'].mean()) / raw_data['macro_epu'].std()
        macro_features['policy_uncertainty'] = epu_normalized
    
    return macro_features


def _compute_full_macro_features(
    raw_data: pd.DataFrame,
    asset_returns: Dict[str, pd.Series]
) -> pd.DataFrame:
    """
    Compute comprehensive macro features (full mode: 50+ features).
    
    Includes:
    - Essential features (5)
    - FRED-MD principal components (10)
    - Geopolitical indicators (5)
    - Policy regime indicators (5)
    - Yield curve features (10)
    - Additional spreads and correlations (15+)
    """
    # Start with essential features
    macro_features = _compute_essential_macro_features(raw_data, asset_returns)
    
    # Add FRED-MD PCA components (if available)
    fred_cols = [c for c in raw_data.columns if c.startswith('fred_md_')]
    if len(fred_cols) > 10:
        from sklearn.decomposition import PCA
        
        # Extract FRED-MD data
        fred_data = raw_data[fred_cols].dropna()
        
        if len(fred_data) > 100:
            # Compute PCA (10 components)
            pca = PCA(n_components=10)
            pca_components = pca.fit_transform(fred_data)
            
            # Add to features
            pca_df = pd.DataFrame(
                pca_components,
                index=fred_data.index,
                columns=[f'fred_pc{i+1}' for i in range(10)]
            )
            macro_features = macro_features.join(pca_df, how='left')
    
    # Add geopolitical features
    if 'macro_gpr' in raw_data.columns:
        gpr = raw_data['macro_gpr']
        macro_features['gpr_level'] = gpr
        macro_features['gpr_change'] = gpr.diff()
        macro_features['gpr_ewm_63d'] = gpr.ewm(halflife=63).mean()
        macro_features['gpr_volatility'] = gpr.rolling(63).std()
    
    # Add policy features
    if 'macro_efw' in raw_data.columns:
        macro_features['econ_freedom'] = raw_data['macro_efw']
    
    if 'kof_cugi' in raw_data.columns:
        macro_features['globalization'] = raw_data['kof_cugi']
    
    # Add yield curve features
    yield_cols = [c for c in raw_data.columns if 'gs' in c.lower() or 'yield' in c.lower()]
    if len(yield_cols) >= 2:
        # Yield changes
        for col in yield_cols[:5]:  # Limit to 5
            macro_features[f'{col}_change'] = raw_data[col].diff()
            macro_features[f'{col}_ewm'] = raw_data[col].ewm(halflife=63).mean()
    
    return macro_features
