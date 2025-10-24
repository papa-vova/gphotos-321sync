"""Tests for logging configuration."""

import pytest
from pydantic import ValidationError
from gphotos_321sync.common.logging_config import LoggingConfig


class TestLoggingConfig:
    """Test LoggingConfig validation."""
    
    def test_valid_config(self):
        """Test valid logging configuration."""
        config = LoggingConfig(level="INFO", format="json")
        assert config.level == "INFO"
        assert config.format == "json"
    
    def test_default_values(self):
        """Test default values."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "json"
    
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
    
    def test_case_insensitive_log_level(self):
        """Test that log level is case-insensitive."""
        # Lowercase should be normalized to uppercase
        config = LoggingConfig(level="info")
        assert config.level == "INFO"
        
        # Mixed case should also work
        config = LoggingConfig(level="Debug")
        assert config.level == "DEBUG"
    
    def test_case_insensitive_format(self):
        """Test that format is case-insensitive."""
        # Uppercase should be normalized to lowercase
        config = LoggingConfig(format="JSON")
        assert config.format == "json"
        
        # Mixed case should also work
        config = LoggingConfig(format="Simple")
        assert config.format == "simple"
    
    def test_serialization(self):
        """Test that config can be serialized."""
        config = LoggingConfig(level="DEBUG", format="detailed")
        data = config.model_dump()
        
        assert data == {
            "level": "DEBUG",
            "format": "detailed"
        }
    
    def test_deserialization(self):
        """Test that config can be deserialized from dict."""
        data = {
            "level": "WARNING",
            "format": "simple"
        }
        config = LoggingConfig(**data)
        
        assert config.level == "WARNING"
        assert config.format == "simple"
