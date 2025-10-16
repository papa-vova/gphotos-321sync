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
    
    def test_rejects_old_scan_path_parameter(self):
        """Test that old 'scan_path' parameter is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ScannerConfig(scan_path="/path/to/media")
        
        error_msg = str(exc_info.value).lower()
        assert "extra_forbidden" in error_msg or "extra fields not permitted" in error_msg
    
    def test_rejects_unknown_field(self):
        """Test that unknown fields are rejected."""
        with pytest.raises(ValidationError):
            ScannerConfig(
                target_media_path="/path/to/media",
                unknown_parameter="value"
            )
    
    def test_rejects_typo_in_target_media_path(self):
        """Test that typos are caught."""
        with pytest.raises(ValidationError):
            ScannerConfig(target_media_pth="/path/to/media")  # Typo


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
    
    def test_rejects_unknown_field_in_nested_config(self):
        """Test that unknown fields in nested configs are rejected."""
        with pytest.raises(ValidationError):
            MediaScannerConfig(
                logging={"level": "INFO"},
                scanner={
                    "target_media_path": "/path",
                    "scan_path": "/old/path"  # Old parameter name
                }
            )
    
    def test_helpful_error_message_for_old_parameter(self):
        """Test that error message is clear when using old parameter names."""
        with pytest.raises(ValidationError) as exc_info:
            MediaScannerConfig(
                scanner={"scan_path": "/path"}
            )
        
        error_msg = str(exc_info.value)
        # Should mention the field name that was rejected
        assert "scan_path" in error_msg


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
