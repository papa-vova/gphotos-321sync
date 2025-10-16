"""Tests for shared LoggingConfig."""

import pytest
from pydantic import ValidationError
from gphotos_321sync.common import LoggingConfig


class TestLoggingConfig:
    """Test shared LoggingConfig validation."""
    
    def test_valid_config(self):
        """Test valid logging configuration."""
        config = LoggingConfig(level="INFO", format="json")
        assert config.level == "INFO"
        assert config.format == "json"
        assert config.file is None
    
    def test_default_values(self):
        """Test default values."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "json"
        assert config.file is None
    
    def test_all_valid_log_levels(self):
        """Test that all valid log levels are accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            config = LoggingConfig(level=level)
            assert config.level == level
    
    def test_all_valid_formats(self):
        """Test that all valid formats are accepted."""
        for fmt in ["simple", "detailed", "json"]:
            config = LoggingConfig(format=fmt)
            assert config.format == fmt
    
    def test_rejects_invalid_log_level(self):
        """Test that invalid log levels are rejected."""
        with pytest.raises(ValidationError):
            LoggingConfig(level="TRACE")
        
        with pytest.raises(ValidationError):
            LoggingConfig(level="CRITICAL")
    
    def test_rejects_invalid_format(self):
        """Test that invalid formats are rejected."""
        with pytest.raises(ValidationError):
            LoggingConfig(format="xml")
    
    def test_optional_file_parameter(self):
        """Test that file parameter is optional."""
        config = LoggingConfig(level="INFO")
        assert config.file is None
        
        config_with_file = LoggingConfig(level="INFO", file="/path/to/log.txt")
        assert config_with_file.file == "/path/to/log.txt"
    
    def test_rejects_unknown_fields(self):
        """Test that unknown fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LoggingConfig(level="INFO", unknown_field="value")
        
        error_msg = str(exc_info.value).lower()
        assert "extra_forbidden" in error_msg or "extra fields not permitted" in error_msg
    
    def test_rejects_typo_in_field_name(self):
        """Test that typos in field names are caught."""
        with pytest.raises(ValidationError):
            LoggingConfig(levl="INFO")  # Typo: levl instead of level
    
    def test_case_sensitive_log_level(self):
        """Test that log level is case-sensitive."""
        # Valid uppercase
        config = LoggingConfig(level="INFO")
        assert config.level == "INFO"
        
        # Invalid lowercase should be rejected
        with pytest.raises(ValidationError):
            LoggingConfig(level="info")
    
    def test_serialization(self):
        """Test that config can be serialized."""
        config = LoggingConfig(level="DEBUG", format="detailed", file="/tmp/log.txt")
        data = config.model_dump()
        
        assert data == {
            "level": "DEBUG",
            "format": "detailed",
            "file": "/tmp/log.txt"
        }
    
    def test_deserialization(self):
        """Test that config can be deserialized from dict."""
        data = {
            "level": "WARNING",
            "format": "simple",
            "file": "/var/log/app.log"
        }
        config = LoggingConfig(**data)
        
        assert config.level == "WARNING"
        assert config.format == "simple"
        assert config.file == "/var/log/app.log"
