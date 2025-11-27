"""
Tests for temporal disaggregation pipeline.

Includes:
- Synthetic round-trip tests (annual->monthly->annual, monthly->daily->monthly)
- Real-data validation tests
- Consistency checks
"""

import numpy as np
import pandas as pd
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.disaggregation.chowlin import (
    chow_lin_opt_disaggregate,
    aggregate_to_low,
)
from src.disaggregation.composite import build_composite_monthly

# Optional pytest import
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


class TestChowLinRoundTrip:
    """Test round-trip consistency of Chow-Lin disaggregation."""
    
    def test_monthly_to_daily_flow_sum(self):
        """Test monthly->daily->monthly for flow variable with sum aggregation."""
        # Create synthetic monthly flow data
        monthly_index = pd.date_range('2000-01-31', '2000-12-31', freq='ME')
        y_monthly = pd.Series(
            np.random.uniform(10, 20, len(monthly_index)),
            index=monthly_index,
            name='test_flow'
        )
        
        # Create daily indicator
        daily_index = pd.date_range('2000-01-01', '2000-12-31', freq='B')
        x_daily = pd.Series(
            np.random.randn(len(daily_index)) + 10,
            index=daily_index
        )
        
        # Disaggregate
        y_daily = chow_lin_opt_disaggregate(
            y_low=y_monthly,
            x_high=x_daily,
            low_freq='M',
            target_freq='D',
            flow_stock='flow',
            agg_type='sum',
            enforce_positivity=False
        )
        
        # Re-aggregate
        y_monthly_check = aggregate_to_low(y_daily, 'M', 'sum')
        
        # Check consistency
        common_idx = y_monthly.index.intersection(y_monthly_check.index)
        np.testing.assert_allclose(
            y_monthly.loc[common_idx].values,
            y_monthly_check.loc[common_idx].values,
            rtol=1e-6,
            atol=1e-8
        )
    
    def test_monthly_to_daily_stock_last(self):
        """Test monthly->daily->monthly for stock variable with last aggregation."""
        # Create synthetic monthly stock data (levels)
        monthly_index = pd.date_range('2000-01-31', '2000-12-31', freq='ME')
        y_monthly = pd.Series(
            100 + np.cumsum(np.random.randn(len(monthly_index))),
            index=monthly_index,
            name='test_stock'
        )
        
        # Create daily indicator
        daily_index = pd.date_range('2000-01-01', '2000-12-31', freq='B')
        x_daily = pd.Series(
            np.random.randn(len(daily_index)) + 10,
            index=daily_index
        )
        
        # Disaggregate
        y_daily = chow_lin_opt_disaggregate(
            y_low=y_monthly,
            x_high=x_daily,
            low_freq='M',
            target_freq='D',
            flow_stock='stock',
            agg_type='last',
            enforce_positivity=False
        )
        
        # Re-aggregate
        y_monthly_check = aggregate_to_low(y_daily, 'M', 'last')
        
        # Check consistency
        common_idx = y_monthly.index.intersection(y_monthly_check.index)
        np.testing.assert_allclose(
            y_monthly.loc[common_idx].values,
            y_monthly_check.loc[common_idx].values,
            rtol=1e-5,
            atol=1e-6
        )
    
    def test_annual_to_monthly_flow_sum(self):
        """Test annual->monthly->annual for flow variable."""
        # Create synthetic annual flow data
        annual_index = pd.date_range('2000-12-31', '2010-12-31', freq='YE')
        y_annual = pd.Series(
            np.random.uniform(100, 200, len(annual_index)),
            index=annual_index,
            name='test_annual_flow'
        )
        
        # Create monthly indicator
        monthly_index = pd.date_range('2000-01-31', '2010-12-31', freq='ME')
        x_monthly = pd.Series(
            np.random.randn(len(monthly_index)) + 10,
            index=monthly_index
        )
        
        # Disaggregate
        y_monthly = chow_lin_opt_disaggregate(
            y_low=y_annual,
            x_high=x_monthly,
            low_freq='A',
            target_freq='M',
            flow_stock='flow',
            agg_type='sum',
            enforce_positivity=False
        )
        
        # Re-aggregate
        y_annual_check = aggregate_to_low(y_monthly, 'A', 'sum')
        
        # Check consistency
        common_idx = y_annual.index.intersection(y_annual_check.index)
        np.testing.assert_allclose(
            y_annual.loc[common_idx].values,
            y_annual_check.loc[common_idx].values,
            rtol=1e-6,
            atol=1e-8
        )
    
    def test_annual_to_monthly_stock_last(self):
        """Test annual->monthly->annual for stock variable."""
        # Create synthetic annual stock data
        annual_index = pd.date_range('2000-12-31', '2010-12-31', freq='YE')
        y_annual = pd.Series(
            100 + np.cumsum(np.random.randn(len(annual_index)) * 10),
            index=annual_index,
            name='test_annual_stock'
        )
        
        # Create monthly indicator
        monthly_index = pd.date_range('2000-01-31', '2010-12-31', freq='ME')
        x_monthly = pd.Series(
            np.random.randn(len(monthly_index)) + 10,
            index=monthly_index
        )
        
        # Disaggregate
        y_monthly = chow_lin_opt_disaggregate(
            y_low=y_annual,
            x_high=x_monthly,
            low_freq='A',
            target_freq='M',
            flow_stock='stock',
            agg_type='last',
            enforce_positivity=False
        )
        
        # Re-aggregate
        y_annual_check = aggregate_to_low(y_monthly, 'A', 'last')
        
        # Check consistency
        common_idx = y_annual.index.intersection(y_annual_check.index)
        np.testing.assert_allclose(
            y_annual.loc[common_idx].values,
            y_annual_check.loc[common_idx].values,
            rtol=1e-5,
            atol=1e-6
        )


class TestComposite:
    """Test composite series construction."""
    
    def test_shiller_only(self):
        """Test composite with Shiller only."""
        monthly_index = pd.date_range('2000-01-31', '2010-12-31', freq='ME')
        y_sh_m = pd.Series(
            np.random.randn(len(monthly_index)) + 100,
            index=monthly_index,
            name='test_shiller'
        )
        
        composite = build_composite_monthly(
            y_sh_m=y_sh_m,
            y_jst_a=None,
            metric_name='TEST_SHILLER_ONLY',
            flow_stock='stock',
            agg_type='last'
        )
        
        assert len(composite) == len(y_sh_m)
        np.testing.assert_array_equal(composite.values, y_sh_m.values)
    
    def test_jst_only(self):
        """Test composite with JST only."""
        annual_index = pd.date_range('2000-12-31', '2010-12-31', freq='YE')
        y_jst_a = pd.Series(
            np.random.randn(len(annual_index)) + 100,
            index=annual_index,
            name='test_jst'
        )
        
        composite = build_composite_monthly(
            y_sh_m=None,
            y_jst_a=y_jst_a,
            metric_name='TEST_JST_ONLY',
            flow_stock='stock',
            agg_type='last'
        )
        
        # Should have ~11 years * 12 months
        assert len(composite) > 100
    
    def test_splice(self):
        """Test composite with both Shiller and JST (splice)."""
        # Shiller: 2005-2010
        sh_index = pd.date_range('2005-01-31', '2010-12-31', freq='ME')
        y_sh_m = pd.Series(
            np.random.randn(len(sh_index)) + 100,
            index=sh_index,
            name='test_shiller'
        )
        
        # JST: 2000-2010
        jst_index = pd.date_range('2000-12-31', '2010-12-31', freq='YE')
        y_jst_a = pd.Series(
            np.random.randn(len(jst_index)) + 100,
            index=jst_index,
            name='test_jst'
        )
        
        composite = build_composite_monthly(
            y_sh_m=y_sh_m,
            y_jst_a=y_jst_a,
            metric_name='TEST_SPLICE',
            flow_stock='stock',
            agg_type='last'
        )
        
        # Should cover full range (composite may start slightly later due to disaggregation)
        # Just check that we have data from both sources
        assert len(composite) > len(y_sh_m)
        assert composite.index[-1].year == 2010
        
        # Shiller part should be preserved
        sh_overlap = composite.loc[y_sh_m.index]
        np.testing.assert_array_equal(sh_overlap.values, y_sh_m.values)


def run_tests():
    """Run all tests."""
    print("=" * 80)
    print("RUNNING TEMPORAL DISAGGREGATION TESTS")
    print("=" * 80)
    
    test_roundtrip = TestChowLinRoundTrip()
    test_composite = TestComposite()
    
    # Round-trip tests
    print("\n[1/7] Monthly->Daily->Monthly (flow, sum)")
    test_roundtrip.test_monthly_to_daily_flow_sum()
    print("  ✓ PASSED")
    
    print("\n[2/7] Monthly->Daily->Monthly (stock, last)")
    test_roundtrip.test_monthly_to_daily_stock_last()
    print("  ✓ PASSED")
    
    print("\n[3/7] Annual->Monthly->Annual (flow, sum)")
    test_roundtrip.test_annual_to_monthly_flow_sum()
    print("  ✓ PASSED")
    
    print("\n[4/7] Annual->Monthly->Annual (stock, last)")
    test_roundtrip.test_annual_to_monthly_stock_last()
    print("  ✓ PASSED")
    
    # Composite tests
    print("\n[5/7] Composite: Shiller only")
    test_composite.test_shiller_only()
    print("  ✓ PASSED")
    
    print("\n[6/7] Composite: JST only")
    test_composite.test_jst_only()
    print("  ✓ PASSED")
    
    print("\n[7/7] Composite: Shiller + JST splice")
    test_composite.test_splice()
    print("  ✓ PASSED")
    
    print("\n" + "=" * 80)
    print("ALL TESTS PASSED")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
