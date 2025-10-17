"""Tests for configuration validation."""

import pytest
from pydantic import ValidationError
from gphotos_321sync.media_scanner.config import (
    ScannerConfig,
    MediaScannerConfig,
)


class TestScannerConfigValidation:
    """Test ScannerConfig validation."""
    
    def test_valid_config(self):
        """Test valid scanner configuration."""
        config = ScannerConfig(
            target_media_path="/path/to/media",
            batch_size=100
        )
        assert config.target_media_path == "/path/to/media"
        assert config.batch_size == 100
    
    def test_rejects_unknown_field(self):
        """Test that unknown fields are rejected."""
        with pytest.raises(ValidationError):
            ScannerConfig(
                target_media_path="/path/to/media",
                unknown_parameter="value"
            )


class TestMediaScannerConfigValidation:
    """Test MediaScannerConfig validation."""
    
    def test_valid_config(self):
        """Test valid full configuration."""
        config = MediaScannerConfig(
            logging={"level": "INFO", "format": "json"},
            scanner={"target_media_path": "/path/to/media"}
        )
        assert config.logging.level == "INFO"
        assert config.scanner.target_media_path == "/path/to/media"
    
    def test_rejects_unknown_top_level_section(self):
        """Test that unknown top-level sections are rejected."""
        with pytest.raises(ValidationError):
            MediaScannerConfig(
                logging={"level": "INFO"},
                scanner={"target_media_path": "/path"},
                unknown_section={"key": "value"}
            )
    


class TestConfigDefaults:
    """Test that defaults work correctly with validation."""
    
    def test_scanner_config_with_defaults(self):
        """Test that default values work with validation."""
        config = ScannerConfig()
        assert config.target_media_path == ""
        assert config.batch_size == 100
        assert config.use_ffprobe is False
    
    def test_full_config_with_defaults(self):
        """Test full config with all defaults."""
        config = MediaScannerConfig()
        assert config.logging.level == "INFO"
        assert config.logging.format == "json"
        assert config.scanner.batch_size == 100
