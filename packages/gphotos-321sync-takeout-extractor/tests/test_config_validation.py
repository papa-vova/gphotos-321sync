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
    
    def test_rejects_old_target_dir_parameter(self):
        """Test that old 'target_dir' parameter is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractionConfig(
                source_dir="/path/to/archives",
                target_dir="/path/to/output"  # Old parameter name
            )
        
        error_msg = str(exc_info.value).lower()
        assert "extra_forbidden" in error_msg or "extra fields not permitted" in error_msg
    
    def test_rejects_unknown_field(self):
        """Test that unknown fields are rejected."""
        with pytest.raises(ValidationError):
            ExtractionConfig(
                source_dir="/path",
                target_media_path="/path",
                unknown_parameter="value"
            )
    
    def test_rejects_typo_in_target_media_path(self):
        """Test that typos are caught."""
        with pytest.raises(ValidationError):
            ExtractionConfig(
                source_dir="/path",
                target_media_pth="/path"  # Typo
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
    
    def test_rejects_unknown_field_in_nested_config(self):
        """Test that unknown fields in nested configs are rejected."""
        with pytest.raises(ValidationError):
            TakeoutExtractorConfig(
                logging={"level": "INFO"},
                extraction={
                    "source_dir": "/archives",
                    "target_dir": "/output"  # Old parameter name
                }
            )
    
    def test_helpful_error_message_for_old_parameter(self):
        """Test that error message is clear when using old parameter names."""
        with pytest.raises(ValidationError) as exc_info:
            TakeoutExtractorConfig(
                extraction={"target_dir": "/path"}
            )
        
        error_msg = str(exc_info.value)
        # Should mention the field name that was rejected
        assert "target_dir" in error_msg


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
