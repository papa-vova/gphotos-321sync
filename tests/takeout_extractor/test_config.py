"""Tests for extractor-specific configuration."""

import pytest
from gphotos_321sync.takeout_extractor.config import (
    ExtractionConfig,
    TakeoutExtractorConfig,
)
from gphotos_321sync.common import LoggingConfig


class TestExtractionConfig:
    """Tests for ExtractionConfig (extractor-specific parameters only)."""
    
    def test_extraction_config_defaults(self):
        """Test extractor-specific default values."""
        config = ExtractionConfig()
        
        # Extractor-specific defaults
        assert config.source_dir == "."
        assert config.target_media_path == "./extracted"
        assert config.verify_checksums is True
        assert config.max_retry_attempts == 10
    
    def test_extraction_config_custom_values(self):
        """Test extractor-specific parameter overrides."""
        config = ExtractionConfig(
            source_dir="/path/to/archives",
            target_media_path="/path/to/output",
            verify_checksums=False,
            max_retry_attempts=5
        )
        
        assert config.source_dir == "/path/to/archives"
        assert config.target_media_path == "/path/to/output"
        assert config.verify_checksums is False
        assert config.max_retry_attempts == 5
    
    def test_extraction_config_validation(self):
        """Test configuration validation."""
        # Test invalid retry attempts
        with pytest.raises(ValueError):
            ExtractionConfig(max_retry_attempts=-1)
        
        with pytest.raises(ValueError):
            ExtractionConfig(max_retry_attempts=0)
        
        # Test valid retry attempts
        config = ExtractionConfig(max_retry_attempts=1)
        assert config.max_retry_attempts == 1
        
        config = ExtractionConfig(max_retry_attempts=100)
        assert config.max_retry_attempts == 100


class TestTakeoutExtractorConfig:
    """Tests for TakeoutExtractorConfig (complete configuration)."""
    
    def test_takeout_extractor_config_defaults(self):
        """Test complete configuration with defaults."""
        config = TakeoutExtractorConfig()
        
        # Common defaults
        assert config.logging.level == "INFO"
        assert config.logging.format == "json"
        
        # Extractor-specific defaults
        assert config.extraction.source_dir == "."
        assert config.extraction.target_media_path == "./extracted"
        assert config.extraction.verify_checksums is True
        assert config.extraction.max_retry_attempts == 10
    
    def test_takeout_extractor_config_custom_values(self):
        """Test complete configuration with custom values."""
        config = TakeoutExtractorConfig(
            logging=LoggingConfig(level="DEBUG", format="simple"),
            extraction=ExtractionConfig(
                source_dir="/custom/source",
                target_media_path="/custom/target",
                verify_checksums=False,
                max_retry_attempts=3
            )
        )
        
        # Common values
        assert config.logging.level == "DEBUG"
        assert config.logging.format == "simple"
        
        # Extractor-specific values
        assert config.extraction.source_dir == "/custom/source"
        assert config.extraction.target_media_path == "/custom/target"
        assert config.extraction.verify_checksums is False
        assert config.extraction.max_retry_attempts == 3
    
    def test_takeout_extractor_config_inheritance(self):
        """Test that TakeoutExtractorConfig contains nested configs."""
        config = TakeoutExtractorConfig()
        
        # Should have nested configs
        assert hasattr(config, 'logging')
        assert hasattr(config, 'extraction')
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.extraction, ExtractionConfig)
        
        # Should have all ExtractionConfig attributes through extraction
        assert hasattr(config.extraction, 'source_dir')
        assert hasattr(config.extraction, 'target_media_path')
        assert hasattr(config.extraction, 'verify_checksums')
        assert hasattr(config.extraction, 'max_retry_attempts')
        
        # Should have common config attributes through logging
        assert hasattr(config.logging, 'level')
        assert hasattr(config.logging, 'format')
    
    def test_takeout_extractor_config_validation(self):
        """Test complete configuration validation."""
        # Test invalid log level
        with pytest.raises(ValueError):
            TakeoutExtractorConfig(logging=LoggingConfig(level="INVALID"))
        
        # Test invalid log format
        with pytest.raises(ValueError):
            TakeoutExtractorConfig(logging=LoggingConfig(format="INVALID"))
        
        # Test invalid retry attempts
        with pytest.raises(ValueError):
            TakeoutExtractorConfig(extraction=ExtractionConfig(max_retry_attempts=-1))
        
        # Test valid configuration
        config = TakeoutExtractorConfig(
            logging=LoggingConfig(level="WARNING", format="json"),
            extraction=ExtractionConfig(max_retry_attempts=5)
        )
        assert config.logging.level == "WARNING"
        assert config.logging.format == "json"
        assert config.extraction.max_retry_attempts == 5
