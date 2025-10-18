"""Tests for extractor-specific configuration."""

import pytest
from gphotos_321sync.takeout_extractor.config import (
    ExtractionConfig,
    TakeoutExtractorConfig,
)


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


class TestTakeoutExtractorConfig:
    """Tests for TakeoutExtractorConfig (root configuration)."""
    
    def test_takeout_extractor_config_defaults(self):
        """Test root configuration with all defaults."""
        config = TakeoutExtractorConfig()
        
        assert config.logging.level == "INFO"
        assert config.logging.format == "json"
        assert config.extraction.verify_checksums is True
