"""
Unit tests for utils module.
"""

import pytest
import pandas as pd
import yaml
from pathlib import Path

from src.core.utils import (
    setup_logging,
    load_config,
    get_default_config,
    cache_to_parquet,
    load_from_parquet,
)


class TestSetupLogging:
    """Tests for logging setup."""
    
    def test_setup_logging_default(self):
        """Test logging setup with default level."""
        logger = setup_logging()
        assert logger.name == 'fioracle'
        assert logger.level == 20  # INFO level
    
    def test_setup_logging_custom_level(self):
        """Test logging setup with custom level."""
        logger = setup_logging(level='DEBUG')
        assert logger.level == 10  # DEBUG level
    
    def test_setup_logging_warning_level(self):
        """Test logging setup with WARNING level."""
        logger = setup_logging(level='WARNING')
        assert logger.level == 30  # WARNING level


class TestLoadConfig:
    """Tests for config loading."""
    
    def test_load_config_existing_file(self, temp_config):
        """Test loading existing config file."""
        config = load_config(str(temp_config))
        assert 'data' in config
        assert config['data']['start_date'] == '2000-01-01'
    
    def test_load_config_missing_file(self):
        """Test loading non-existent config file returns defaults."""
        with pytest.warns(UserWarning):
            config = load_config('nonexistent.yaml')
        assert isinstance(config, dict)
        assert 'data' in config
    
    def test_get_default_config(self):
        """Test default config structure."""
        config = get_default_config()
        
        # Check main sections exist
        assert 'data' in config
        assert 'assets' in config
        assert 'regimes' in config
        assert 'portfolio' in config
        assert 'evaluation' in config
        assert 'output' in config
        
        # Check specific values
        assert config['regimes']['jump_model']['default_lambda'] == 5.0
        assert config['portfolio']['gamma_risk'] == 10.0


class TestParquetCaching:
    """Tests for parquet caching utilities."""
    
    def test_cache_to_parquet(self, sample_data, temp_cache_dir):
        """Test saving DataFrame to parquet."""
        cache_to_parquet(sample_data, 'test_data', cache_dir=str(temp_cache_dir))
        
        # Check file was created
        cache_file = temp_cache_dir / 'test_data.parquet'
        assert cache_file.exists()
    
    def test_load_from_parquet_existing(self, sample_data, temp_cache_dir):
        """Test loading existing parquet file."""
        # First save
        cache_to_parquet(sample_data, 'test_data', cache_dir=str(temp_cache_dir))
        
        # Then load
        loaded_data = load_from_parquet('test_data', cache_dir=str(temp_cache_dir))
        
        assert loaded_data is not None
        assert len(loaded_data) == len(sample_data)
        pd.testing.assert_frame_equal(loaded_data, sample_data)
    
    def test_load_from_parquet_missing(self, temp_cache_dir):
        """Test loading non-existent parquet file returns None."""
        result = load_from_parquet('nonexistent', cache_dir=str(temp_cache_dir))
        assert result is None
    
    def test_cache_with_compression(self, sample_data, temp_cache_dir):
        """Test caching with different compression."""
        cache_to_parquet(
            sample_data, 
            'compressed_data', 
            cache_dir=str(temp_cache_dir),
            compression='gzip'
        )
        
        cache_file = temp_cache_dir / 'compressed_data.parquet'
        assert cache_file.exists()
        
        # Verify data can be loaded back
        loaded = load_from_parquet('compressed_data', cache_dir=str(temp_cache_dir))
        assert len(loaded) == len(sample_data)


class TestDataIntegrity:
    """Tests for data integrity in caching."""
    
    def test_roundtrip_preserves_index(self, sample_data, temp_cache_dir):
        """Test that index is preserved through save/load cycle."""
        cache_to_parquet(sample_data, 'test', cache_dir=str(temp_cache_dir))
        loaded = load_from_parquet('test', cache_dir=str(temp_cache_dir))
        
        pd.testing.assert_index_equal(loaded.index, sample_data.index)
    
    def test_roundtrip_preserves_columns(self, sample_data, temp_cache_dir):
        """Test that columns are preserved through save/load cycle."""
        cache_to_parquet(sample_data, 'test', cache_dir=str(temp_cache_dir))
        loaded = load_from_parquet('test', cache_dir=str(temp_cache_dir))
        
        assert list(loaded.columns) == list(sample_data.columns)
    
    def test_roundtrip_preserves_dtypes(self, sample_data, temp_cache_dir):
        """Test that data types are preserved."""
        cache_to_parquet(sample_data, 'test', cache_dir=str(temp_cache_dir))
        loaded = load_from_parquet('test', cache_dir=str(temp_cache_dir))
        
        for col in sample_data.columns:
            assert loaded[col].dtype == sample_data[col].dtype
