"""
Benchmark Portfolio Strategies

Implements multiple benchmark strategies for comparison:
1. Equal-Weight Buy & Hold (EW B&H)
2. 60/40 Government/Credit Benchmark
3. Barbell Strategy (80-90% safe, 10-20% risky)
4. Diversified Core FI Strategy (balanced allocation)
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
import warnings

warnings.filterwarnings('ignore')


class BenchmarkEngine:
    """
    Engine for computing various benchmark portfolio returns.
    
    Supports:
    - Equal-weight buy-and-hold
    - 60/40 Government/Credit (quarterly rebalanced)
    - Barbell Strategy
    - Diversified Core FI Strategy
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize benchmark engine.
        
        Args:
            config: Configuration dictionary with asset categories
        """
        self.config = config or {}
        
        # Asset categories from config
        asset_cfg = self.config.get('assets', {})
        self.categories = asset_cfg.get('categories', {})
        
        # Default category mappings if not in config
        if not self.categories:
            self.categories = {
                'cash': ['US_CASH_RETURN'],
                'government_bonds': ['US_10Y_GOV_BOND_RETURN', 'IBOXX_USD_TREASURY_TOTAL_RETURN'],
                'investment_grade': ['US_BOND_AGG_TOTAL_RETURN', 'IBOXX_USD_CORPORATE_TOTAL_RETURN',
                                    'US_AAA_CORP_BOND_TOTAL_RETURN', 'US_BAA_CORP_BOND_TOTAL_RETURN'],
                'high_yield': ['CDX_HY_5Y_TOTAL_RETURN', 'CDX_IG_5Y_TOTAL_RETURN'],
                'inflation_linked': ['US_TIPS_0_5_TOTAL_RETURN', 'US_INFLATION_SWAP_5Y_RETURN'],
                'safe_havens': ['GOLD_TOTAL_RETURN', 'CHF_TOTAL_RETURN'],
                'volatility_hedges': ['USD_SWAPTION_6M_5Y_TOTAL_RETURN'],
                'commodities': ['WTI_TOTAL_RETURN'],
            }
    
    def _find_matching_assets(self, asset_list: List[str], available_cols: List[str]) -> List[str]:
        """Find assets from list that are available in columns."""
        matches = []
        for asset in asset_list:
            asset_upper = asset.upper()
            for col in available_cols:
                if asset_upper in col.upper() or col.upper() in asset_upper:
                    matches.append(col)
                    break
        return list(set(matches))
    
    def _get_category_assets(self, category: str, available_cols: List[str]) -> List[str]:
        """Get available assets for a category."""
        category_assets = self.categories.get(category, [])
        return self._find_matching_assets(category_assets, available_cols)
    
    def compute_ew_benchmark(self, returns_df: pd.DataFrame) -> pd.Series:
        """
        Compute equal-weight buy-and-hold benchmark.
        
        Args:
            returns_df: DataFrame of asset returns
            
        Returns:
            Series of benchmark returns
        """
        available = [c for c in returns_df.columns if not returns_df[c].isna().all()]
        if len(available) == 0:
            return pd.Series(0.0, index=returns_df.index)
        
        return returns_df[available].mean(axis=1)
    
    def compute_60_40_benchmark(
        self,
        returns_df: pd.DataFrame,
        gov_weight: float = 0.6,
        credit_weight: float = 0.4,
        rebalance_freq: str = 'Q'
    ) -> Tuple[pd.Series, pd.DataFrame]:
        """
        Compute 60/40 Government/Credit benchmark.
        
        Traditional fixed income allocation:
        - 60% to government bonds (equal-weight average of Treasury indices)
        - 40% to credit (equal-weight average of corporate and credit indices)
        - Rebalanced quarterly to maintain target weights
        
        Args:
            returns_df: DataFrame of asset returns
            gov_weight: Weight for government bonds (default 0.6)
            credit_weight: Weight for credit (default 0.4)
            rebalance_freq: Rebalancing frequency ('Q' = quarterly, 'M' = monthly)
            
        Returns:
            Tuple of (benchmark_returns, weights_df)
        """
        available_cols = returns_df.columns.tolist()
        
        # Find government bond assets
        gov_assets = self._get_category_assets('government_bonds', available_cols)
        
        # Find credit assets (investment grade + high yield)
        credit_assets = (
            self._get_category_assets('investment_grade', available_cols) +
            self._get_category_assets('high_yield', available_cols)
        )
        
        if not gov_assets and not credit_assets:
            # Fallback: use any available assets
            return self.compute_ew_benchmark(returns_df), pd.DataFrame()
        
        # If only one category available, use only that
        if not gov_assets:
            gov_weight = 0.0
            credit_weight = 1.0
        elif not credit_assets:
            gov_weight = 1.0
            credit_weight = 0.0
        
        # Compute equal-weight returns within each category
        gov_returns = returns_df[gov_assets].mean(axis=1) if gov_assets else pd.Series(0.0, index=returns_df.index)
        credit_returns = returns_df[credit_assets].mean(axis=1) if credit_assets else pd.Series(0.0, index=returns_df.index)
        
        # Simple approach: constant weights with quarterly rebalancing effect
        # For quarterly rebalancing, we need to track cumulative returns and rebalance
        
        benchmark_returns = []
        weights_history = []
        
        current_gov_weight = gov_weight
        current_credit_weight = credit_weight
        
        rebalance_dates = returns_df.resample(rebalance_freq).last().index
        
        for date in returns_df.index:
            # Check if it's a rebalance date
            if date in rebalance_dates:
                current_gov_weight = gov_weight
                current_credit_weight = credit_weight
            
            # Compute portfolio return
            gov_ret = gov_returns.loc[date] if not pd.isna(gov_returns.loc[date]) else 0.0
            credit_ret = credit_returns.loc[date] if not pd.isna(credit_returns.loc[date]) else 0.0
            
            port_ret = current_gov_weight * gov_ret + current_credit_weight * credit_ret
            benchmark_returns.append(port_ret)
            
            weights_history.append({
                'date': date,
                'gov_weight': current_gov_weight,
                'credit_weight': current_credit_weight
            })
            
            # Update weights based on returns (drift)
            total_value = current_gov_weight * (1 + gov_ret) + current_credit_weight * (1 + credit_ret)
            if total_value > 0:
                current_gov_weight = current_gov_weight * (1 + gov_ret) / total_value
                current_credit_weight = current_credit_weight * (1 + credit_ret) / total_value
        
        returns_series = pd.Series(benchmark_returns, index=returns_df.index)
        weights_df = pd.DataFrame(weights_history).set_index('date')
        
        return returns_series, weights_df
    
    def compute_barbell_benchmark(
        self,
        returns_df: pd.DataFrame,
        safe_weight: float = 0.85,
        risky_weight: float = 0.15,
        rebalance_freq: str = 'Q'
    ) -> Tuple[pd.Series, pd.DataFrame]:
        """
        Compute Barbell Strategy benchmark.
        
        Concentrates 80-90% of capital in cash or short-dated safe assets,
        with remaining 10-20% allocated to risky or hedging instruments
        (high-yield-exposed credit and tail hedges).
        
        Args:
            returns_df: DataFrame of asset returns
            safe_weight: Weight for safe assets (default 0.85)
            risky_weight: Weight for risky/hedging assets (default 0.15)
            rebalance_freq: Rebalancing frequency
            
        Returns:
            Tuple of (benchmark_returns, weights_df)
        """
        available_cols = returns_df.columns.tolist()
        
        # Safe assets: cash + short-duration government bonds
        safe_assets = (
            self._get_category_assets('cash', available_cols) +
            self._get_category_assets('government_bonds', available_cols)
        )
        
        # Risky/hedging assets: high yield + volatility hedges + commodities
        risky_assets = (
            self._get_category_assets('high_yield', available_cols) +
            self._get_category_assets('volatility_hedges', available_cols) +
            self._get_category_assets('safe_havens', available_cols)
        )
        
        if not safe_assets and not risky_assets:
            return self.compute_ew_benchmark(returns_df), pd.DataFrame()
        
        # Adjust weights if one category missing
        if not safe_assets:
            safe_weight = 0.0
            risky_weight = 1.0
        elif not risky_assets:
            safe_weight = 1.0
            risky_weight = 0.0
        
        # Compute equal-weight returns within each category
        safe_returns = returns_df[safe_assets].mean(axis=1) if safe_assets else pd.Series(0.0, index=returns_df.index)
        risky_returns = returns_df[risky_assets].mean(axis=1) if risky_assets else pd.Series(0.0, index=returns_df.index)
        
        benchmark_returns = []
        weights_history = []
        
        current_safe_weight = safe_weight
        current_risky_weight = risky_weight
        
        rebalance_dates = returns_df.resample(rebalance_freq).last().index
        
        for date in returns_df.index:
            if date in rebalance_dates:
                current_safe_weight = safe_weight
                current_risky_weight = risky_weight
            
            safe_ret = safe_returns.loc[date] if not pd.isna(safe_returns.loc[date]) else 0.0
            risky_ret = risky_returns.loc[date] if not pd.isna(risky_returns.loc[date]) else 0.0
            
            port_ret = current_safe_weight * safe_ret + current_risky_weight * risky_ret
            benchmark_returns.append(port_ret)
            
            weights_history.append({
                'date': date,
                'safe_weight': current_safe_weight,
                'risky_weight': current_risky_weight
            })
            
            # Drift
            total_value = current_safe_weight * (1 + safe_ret) + current_risky_weight * (1 + risky_ret)
            if total_value > 0:
                current_safe_weight = current_safe_weight * (1 + safe_ret) / total_value
                current_risky_weight = current_risky_weight * (1 + risky_ret) / total_value
        
        returns_series = pd.Series(benchmark_returns, index=returns_df.index)
        weights_df = pd.DataFrame(weights_history).set_index('date')
        
        return returns_series, weights_df
    
    def compute_diversified_core_benchmark(
        self,
        returns_df: pd.DataFrame,
        rebalance_freq: str = 'Q'
    ) -> Tuple[pd.Series, pd.DataFrame]:
        """
        Compute Diversified Core FI Strategy benchmark.
        
        Spreads capital more evenly across rates, credit, inflation-linked bonds,
        and tail hedges with moderate weights (e.g., 20-30% each bucket).
        
        Target allocation:
        - Rates (Government bonds): 25%
        - Credit (IG + HY): 25%
        - Inflation-linked: 25%
        - Safe havens/hedges: 25%
        
        Args:
            returns_df: DataFrame of asset returns
            rebalance_freq: Rebalancing frequency
            
        Returns:
            Tuple of (benchmark_returns, weights_df)
        """
        available_cols = returns_df.columns.tolist()
        
        # Define buckets
        buckets = {
            'rates': self._get_category_assets('government_bonds', available_cols),
            'credit': (
                self._get_category_assets('investment_grade', available_cols) +
                self._get_category_assets('high_yield', available_cols)
            ),
            'inflation': self._get_category_assets('inflation_linked', available_cols),
            'hedges': (
                self._get_category_assets('safe_havens', available_cols) +
                self._get_category_assets('volatility_hedges', available_cols)
            ),
        }
        
        # Filter to non-empty buckets
        active_buckets = {k: v for k, v in buckets.items() if v}
        
        if not active_buckets:
            return self.compute_ew_benchmark(returns_df), pd.DataFrame()
        
        # Equal weight across active buckets
        n_buckets = len(active_buckets)
        target_weight = 1.0 / n_buckets
        
        # Compute returns per bucket
        bucket_returns = {}
        for bucket_name, assets in active_buckets.items():
            bucket_returns[bucket_name] = returns_df[assets].mean(axis=1)
        
        benchmark_returns = []
        weights_history = []
        
        current_weights = {k: target_weight for k in active_buckets.keys()}
        rebalance_dates = returns_df.resample(rebalance_freq).last().index
        
        for date in returns_df.index:
            if date in rebalance_dates:
                current_weights = {k: target_weight for k in active_buckets.keys()}
            
            # Compute portfolio return
            port_ret = 0.0
            for bucket_name, weight in current_weights.items():
                ret = bucket_returns[bucket_name].loc[date]
                if not pd.isna(ret):
                    port_ret += weight * ret
            
            benchmark_returns.append(port_ret)
            weights_history.append({'date': date, **current_weights})
            
            # Drift
            total_value = 0.0
            for bucket_name, weight in current_weights.items():
                ret = bucket_returns[bucket_name].loc[date]
                ret = ret if not pd.isna(ret) else 0.0
                total_value += weight * (1 + ret)
            
            if total_value > 0:
                for bucket_name in current_weights:
                    ret = bucket_returns[bucket_name].loc[date]
                    ret = ret if not pd.isna(ret) else 0.0
                    current_weights[bucket_name] = current_weights[bucket_name] * (1 + ret) / total_value
        
        returns_series = pd.Series(benchmark_returns, index=returns_df.index)
        weights_df = pd.DataFrame(weights_history).set_index('date')
        
        return returns_series, weights_df
    
    def compute_all_benchmarks(
        self,
        returns_df: pd.DataFrame
    ) -> Dict[str, Tuple[pd.Series, Optional[pd.DataFrame]]]:
        """
        Compute all benchmark strategies.
        
        Args:
            returns_df: DataFrame of asset returns
            
        Returns:
            Dict mapping benchmark name to (returns_series, weights_df)
        """
        n_assets = len([c for c in returns_df.columns if not returns_df[c].isna().all()])
        
        benchmarks = {}
        
        # 1. Equal-weight B&H
        ew_returns = self.compute_ew_benchmark(returns_df)
        benchmarks[f'EW {n_assets}-Asset B&H'] = (ew_returns, None)
        
        # 2. 60/40 Gov/Credit
        try:
            gov_credit_returns, gov_credit_weights = self.compute_60_40_benchmark(returns_df)
            benchmarks['60/40 Gov/Credit'] = (gov_credit_returns, gov_credit_weights)
        except Exception as e:
            print(f"  Warning: 60/40 benchmark failed: {e}")
        
        # 3. Barbell Strategy
        try:
            barbell_returns, barbell_weights = self.compute_barbell_benchmark(returns_df)
            benchmarks['Barbell (85/15)'] = (barbell_returns, barbell_weights)
        except Exception as e:
            print(f"  Warning: Barbell benchmark failed: {e}")
        
        # 4. Diversified Core FI
        try:
            div_returns, div_weights = self.compute_diversified_core_benchmark(returns_df)
            benchmarks['Diversified Core FI'] = (div_returns, div_weights)
        except Exception as e:
            print(f"  Warning: Diversified Core benchmark failed: {e}")
        
        return benchmarks


def build_all_benchmarks_enhanced(
    split_returns: pd.DataFrame,
    config: dict
) -> Dict[str, pd.Series]:
    """
    Build all benchmarks for comparison.
    
    Args:
        split_returns: DataFrame of asset returns
        config: Configuration dict
        
    Returns:
        Dict mapping benchmark_name -> returns series
    """
    engine = BenchmarkEngine(config)
    all_benchmarks = engine.compute_all_benchmarks(split_returns)
    
    # Return just the series (not weights)
    return {name: data[0] for name, data in all_benchmarks.items()}

