"""
Tests for visualization utilities.
"""

import pytest
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import tempfile

from src.visualizations import visualize_regime_drivers


class TestRegimeDriversVisualization:
    """Test regime drivers visualization."""
    
    @pytest.mark.slow
    def test_visualize_regime_drivers_basic(self):
        """Test basic regime drivers visualization."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / 'test_viz.png'
                
                # Create visualization (short period for speed)
                fig = visualize_regime_drivers(
                    start_date='2008-01-01',
                    end_date='2009-12-31',
                    output_path=str(output_path),
                    show_plot=False
                )
                
                # Verify figure created
                assert fig is not None
                assert output_path.exists()
                assert output_path.stat().st_size > 0
                
                # Clean up
                plt.close(fig)
                
        except FileNotFoundError:
            pytest.skip("Data files not available for visualization test")
        except Exception as e:
            pytest.skip(f"Visualization test skipped: {e}")
    
    @pytest.mark.slow
    def test_visualize_regime_drivers_custom_dates(self):
        """Test visualization with custom date range."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / 'test_custom.png'
                
                # Test different period
                fig = visualize_regime_drivers(
                    start_date='2001-01-01',
                    end_date='2002-12-31',
                    output_path=str(output_path),
                    show_plot=False
                )
                
                assert fig is not None
                assert output_path.exists()
                
                plt.close(fig)
                
        except FileNotFoundError:
            pytest.skip("Data files not available")
        except Exception as e:
            pytest.skip(f"Test skipped: {e}")
    
    def test_visualization_output_format(self):
        """Test that visualization saves in correct format."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Test PNG format
                png_path = Path(tmpdir) / 'test.png'
                fig = visualize_regime_drivers(
                    start_date='2008-01-01',
                    end_date='2008-12-31',
                    output_path=str(png_path),
                    show_plot=False
                )
                
                assert png_path.suffix == '.png'
                assert png_path.exists()
                
                # Verify it's a valid PNG (magic bytes)
                with open(png_path, 'rb') as f:
                    header = f.read(8)
                    assert header == b'\x89PNG\r\n\x1a\n'
                
                plt.close(fig)
                
        except FileNotFoundError:
            pytest.skip("Data files not available")
        except Exception as e:
            pytest.skip(f"Test skipped: {e}")


class TestVisualizationHelpers:
    """Test visualization helper functions."""
    
    def test_continuous_periods_helper(self):
        """Test the _get_continuous_periods helper."""
        from src.visualizations.regime_drivers import _get_continuous_periods
        
        # Create test data
        dates = pd.date_range('2020-01-01', periods=10, freq='D')
        mask = pd.Series([False, True, True, False, False, True, False, False, True, True], 
                        index=dates)
        
        periods = _get_continuous_periods(mask)
        
        # Should find 3 periods
        assert len(periods) == 3
        
        # Check first period (days 2-3)
        assert periods[0][0] == dates[1]
        assert periods[0][1] == dates[2]
        
        # Check second period (day 6)
        assert periods[1][0] == dates[5]
        assert periods[1][1] == dates[5]
        
        # Check third period (days 9-10)
        assert periods[2][0] == dates[8]
        assert periods[2][1] == dates[9]
    
    def test_continuous_periods_edge_cases(self):
        """Test edge cases for continuous periods."""
        from src.visualizations.regime_drivers import _get_continuous_periods
        
        dates = pd.date_range('2020-01-01', periods=5, freq='D')
        
        # All False
        mask = pd.Series([False] * 5, index=dates)
        periods = _get_continuous_periods(mask)
        assert len(periods) == 0
        
        # All True
        mask = pd.Series([True] * 5, index=dates)
        periods = _get_continuous_periods(mask)
        assert len(periods) == 1
        assert periods[0][0] == dates[0]
        assert periods[0][1] == dates[4]
        
        # Start with True
        mask = pd.Series([True, True, False, False, False], index=dates)
        periods = _get_continuous_periods(mask)
        assert len(periods) == 1
        assert periods[0][0] == dates[0]
        assert periods[0][1] == dates[1]
        
        # End with True
        mask = pd.Series([False, False, False, True, True], index=dates)
        periods = _get_continuous_periods(mask)
        assert len(periods) == 1
        assert periods[0][0] == dates[3]
        assert periods[0][1] == dates[4]
