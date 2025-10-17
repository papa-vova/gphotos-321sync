"""Tests for configuration validation."""

import pytest
from pydantic import ValidationError
from gphotos_321sync.takeout_extractor.config import (
    ExtractionConfig,
    TakeoutExtractorConfig,
)


class TestExtractionConfigValidation:
    """Test ExtractionConfig validation."""
    
    def test_valid_config(self):
        """Test valid extraction configuration."""
        config = ExtractionConfig(
            source_dir="/path/to/archives",
            target_media_path="/path/to/output"
        )
        assert config.source_dir == "/path/to/archives"
        assert config.target_media_path == "/path/to/output"
    
    def test_rejects_unknown_field(self):
        """Test that unknown fields are rejected."""
        with pytest.raises(ValidationError):
            ExtractionConfig(
                source_dir="/path",
                target_media_path="/path",
                unknown_parameter="value"
            )


class TestTakeoutExtractorConfigValidation:
    """Test TakeoutExtractorConfig validation."""
    
    def test_valid_config(self):
        """Test valid full configuration."""
        config = TakeoutExtractorConfig(
            logging={"level": "INFO", "format": "json"},
            extraction={
                "source_dir": "/archives",
                "target_media_path": "/output"
            }
        )
        assert config.logging.level == "INFO"
        assert config.extraction.target_media_path == "/output"
    
    def test_rejects_unknown_top_level_section(self):
        """Test that unknown top-level sections are rejected."""
        with pytest.raises(ValidationError):
            TakeoutExtractorConfig(
                logging={"level": "INFO"},
                extraction={"source_dir": ".", "target_media_path": "."},
                unknown_section={"key": "value"}
            )
    


class TestConfigDefaults:
    """Test that defaults work correctly with validation."""
    
    def test_extraction_config_with_defaults(self):
        """Test that default values work with validation."""
        config = ExtractionConfig()
        assert config.source_dir == "."
        assert config.target_media_path == "./extracted"
        assert config.verify_checksums is True
        assert config.max_retry_attempts == 10
    
    def test_full_config_with_defaults(self):
        """Test full config with all defaults."""
        config = TakeoutExtractorConfig()
        assert config.logging.level == "INFO"
        assert config.logging.format == "json"
        assert config.extraction.verify_checksums is True
