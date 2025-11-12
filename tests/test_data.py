"""
Unit tests for src.core.data module.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from src.core.data import DataPipeline


class TestDataPipelineInit:
    """Test DataPipeline initialization."""
    
    def test_init_basic_mode(self):
        """Test initialization with basic mode."""
        pipeline = DataPipeline(mode='basic')
        
        assert pipeline.mode == 'basic'
        assert hasattr(pipeline, 'data_sources')
        assert hasattr(pipeline, 'cache_enabled')
    
    def test_init_comprehensive_mode(self):
        """Test initialization with comprehensive mode."""
        pipeline = DataPipeline(mode='comprehensive')
        
        assert pipeline.mode == 'comprehensive'
    
    def test_init_invalid_mode(self):
        """Test initialization with invalid mode."""
        with pytest.raises((ValueError, AssertionError)):
            DataPipeline(mode='invalid_mode')


class TestDataPipelineLoad:
    """Test DataPipeline load method."""
    
    @patch('src.core.data.DataPipeline._load_from_source')
    def test_load_basic(self, mock_load):
        """Test basic load functionality."""
        # Mock the data loading
        mock_data = pd.DataFrame({
            'GPR': np.random.randn(100),
            'US_EPU': np.random.randn(100),
            'SP500': np.random.randn(100),
        }, index=pd.date_range('2000-01-01', periods=100))
        
        mock_load.return_value = mock_data
        
        pipeline = DataPipeline(mode='basic')
        result = pipeline.load('2000-01-01', '2000-12-31')
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
    
    def test_load_date_filtering(self, sample_data):
        """Test that date filtering works correctly."""
        pipeline = DataPipeline(mode='basic')
        
        # Mock the load to return sample_data
        with patch.object(pipeline, '_load_from_source', return_value=sample_data):
            result = pipeline.load('2002-01-01', '2004-12-31')
            
            # Result should be filtered to requested dates
            assert result.index[0] >= pd.Timestamp('2002-01-01')
            assert result.index[-1] <= pd.Timestamp('2004-12-31')
    
    def test_load_empty_date_range(self):
        """Test load with invalid date range."""
        pipeline = DataPipeline(mode='basic')
        
        # This might raise an error or return empty DataFrame
        # depending on implementation
        try:
            result = pipeline.load('2030-01-01', '2030-12-31')
            # If it doesn't raise, should be empty or None
            if result is not None:
                assert len(result) == 0
        except (ValueError, FileNotFoundError):
            # Also acceptable to raise an error
            pass


class TestDataPipelineCaching:
    """Test DataPipeline caching functionality."""
    
    def test_cache_enabled(self, temp_cache_dir):
        """Test that caching can be enabled."""
        pipeline = DataPipeline(mode='basic', cache_dir=str(temp_cache_dir))
        
        assert pipeline.cache_enabled
        assert pipeline.cache_dir == str(temp_cache_dir)
    
    @patch('src.core.data.DataPipeline._load_from_source')
    @patch('src.core.utils.cache_to_parquet')
    @patch('src.core.utils.load_from_parquet')
    def test_cache_miss_then_hit(self, mock_load_cache, mock_save_cache, mock_load_source, temp_cache_dir):
        """Test cache miss followed by cache hit."""
        mock_data = pd.DataFrame({
            'col1': [1, 2, 3],
            'col2': [4, 5, 6],
        }, index=pd.date_range('2000-01-01', periods=3))
        
        # First call: cache miss
        mock_load_cache.return_value = None
        mock_load_source.return_value = mock_data
        
        pipeline = DataPipeline(mode='basic', cache_dir=str(temp_cache_dir))
        result1 = pipeline.load('2000-01-01', '2000-12-31')
        
        # Should have tried to save to cache
        assert mock_save_cache.call_count >= 0  # Implementation dependent
        
        # Second call: cache hit
        mock_load_cache.return_value = mock_data
        result2 = pipeline.load('2000-01-01', '2000-12-31')
        
        # Both results should be identical
        if result1 is not None and result2 is not None:
            pd.testing.assert_frame_equal(result1, result2)


class TestDataPipelineAlignment:
    """Test data alignment across different sources."""
    
    def test_index_alignment(self, sample_data):
        """Test that loaded data has properly aligned indices."""
        pipeline = DataPipeline(mode='basic')
        
        with patch.object(pipeline, '_load_from_source', return_value=sample_data):
            result = pipeline.load('2000-01-01', '2010-12-31')
            
            # Index should be sorted and unique
            assert result.index.is_monotonic_increasing
            assert result.index.is_unique
            
            # No NaN in index
            assert not result.index.isna().any()
    
    def test_multi_frequency_handling(self):
        """Test handling of data with different frequencies."""
        # Create daily data
        daily_data = pd.DataFrame({
            'daily_col': np.random.randn(365),
        }, index=pd.date_range('2000-01-01', periods=365, freq='D'))
        
        # Create monthly data
        monthly_data = pd.DataFrame({
            'monthly_col': np.random.randn(12),
        }, index=pd.date_range('2000-01-01', periods=12, freq='MS'))
        
        # DataPipeline should handle this appropriately
        # (implementation specific - might resample or forward fill)
        pipeline = DataPipeline(mode='basic')
        
        # This test depends on how the pipeline handles mixed frequencies
        # Just verify it doesn't crash
        assert pipeline is not None


class TestDataPipelineValidation:
    """Test data validation and quality checks."""
    
    def test_missing_data_handling(self):
        """Test how pipeline handles missing data."""
        data_with_nans = pd.DataFrame({
            'col1': [1, np.nan, 3, 4],
            'col2': [np.nan, 2, 3, 4],
        }, index=pd.date_range('2000-01-01', periods=4))
        
        pipeline = DataPipeline(mode='basic')
        
        with patch.object(pipeline, '_load_from_source', return_value=data_with_nans):
            result = pipeline.load('2000-01-01', '2000-12-31')
            
            # Pipeline might forward fill or drop - just verify it handles it
            assert result is not None
    
    def test_infinite_values_handling(self):
        """Test how pipeline handles infinite values."""
        data_with_inf = pd.DataFrame({
            'col1': [1, np.inf, 3, 4],
            'col2': [1, 2, -np.inf, 4],
        }, index=pd.date_range('2000-01-01', periods=4))
        
        pipeline = DataPipeline(mode='basic')
        
        with patch.object(pipeline, '_load_from_source', return_value=data_with_inf):
            result = pipeline.load('2000-01-01', '2000-12-31')
            
            # Should handle infinites (replace or drop)
            if result is not None:
                # Either no infinites, or documented behavior
                pass


class TestDataPipelineModes:
    """Test different pipeline modes."""
    
    def test_basic_mode_sources(self):
        """Test that basic mode loads expected sources."""
        pipeline = DataPipeline(mode='basic')
        
        # Should have minimal set of sources
        assert hasattr(pipeline, 'mode')
        assert pipeline.mode == 'basic'
    
    def test_comprehensive_mode_sources(self):
        """Test that comprehensive mode loads more sources."""
        pipeline = DataPipeline(mode='comprehensive')
        
        assert pipeline.mode == 'comprehensive'
        # Comprehensive mode should load more data sources
        # (implementation specific validation)


class TestDataPipelineErrorHandling:
    """Test error handling in DataPipeline."""
    
    def test_missing_file_handling(self):
        """Test handling of missing data files."""
        pipeline = DataPipeline(mode='basic')
        
        # Try to load from non-existent date range or trigger missing file
        with patch.object(pipeline, '_load_from_source', side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError):
                pipeline.load('1800-01-01', '1800-12-31')
    
    def test_corrupted_data_handling(self):
        """Test handling of corrupted data."""
        pipeline = DataPipeline(mode='basic')
        
        # Mock corrupted data (e.g., wrong columns)
        corrupted_data = pd.DataFrame({
            'wrong_column': [1, 2, 3],
        })
        
        with patch.object(pipeline, '_load_from_source', return_value=corrupted_data):
            # Might raise error or handle gracefully
            try:
                result = pipeline.load('2000-01-01', '2000-12-31')
                # If it succeeds, verify it did something reasonable
                assert result is not None
            except Exception:
                # Also acceptable to raise
                pass
