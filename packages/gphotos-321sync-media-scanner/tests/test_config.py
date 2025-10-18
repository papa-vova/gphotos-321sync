"""Tests for configuration module."""

import pytest
import os
from gphotos_321sync.media_scanner.config import (
    LoggingConfig,
    ScannerConfig,
    MediaScannerConfig,
)


class TestLoggingConfig:
    """Tests for LoggingConfig."""
    
    def test_default_values(self):
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.format == "json"
    
    def test_custom_values(self):
        """Test custom logging configuration."""
        config = LoggingConfig(
            level="DEBUG",
            format="simple"
        )
        assert config.level == "DEBUG"
        assert config.format == "simple"


class TestScannerConfig:
    """Tests for ScannerConfig."""
    
    def test_default_values_are_reasonable(self):
        """Test that default scanner configuration has reasonable values."""
        config = ScannerConfig()
        
        # Worker counts should be positive and based on CPU count
        assert config.worker_threads > 0
        assert config.worker_processes > 0
        assert config.batch_size > 0
        assert config.queue_maxsize > 0
        
        # Optional tools should be disabled by default (no external dependencies)
        assert config.use_ffprobe is False
        assert config.use_exiftool is False
    
    def test_custom_values_override_defaults(self):
        """Test that custom values properly override defaults."""
        custom_threads = 8
        custom_processes = 4
        custom_batch = 50
        custom_queue = 500
        
        config = ScannerConfig(
            worker_threads=custom_threads,
            worker_processes=custom_processes,
            batch_size=custom_batch,
            queue_maxsize=custom_queue,
            use_ffprobe=True,
            use_exiftool=True
        )
        
        assert config.worker_threads == custom_threads
        assert config.worker_processes == custom_processes
        assert config.batch_size == custom_batch
        assert config.queue_maxsize == custom_queue
        assert config.use_ffprobe is True
        assert config.use_exiftool is True


class TestMediaScannerConfig:
    """Tests for MediaScannerConfig."""
    
    def test_default_values(self):
        """Test default root configuration."""
        config = MediaScannerConfig()
        
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.scanner, ScannerConfig)
        assert config.logging.level == "INFO"
        assert config.scanner.batch_size == 100
    
    def test_nested_custom_values(self):
        """Test custom nested configuration."""
        config = MediaScannerConfig(
            logging=LoggingConfig(level="DEBUG", format="simple"),
            scanner=ScannerConfig(worker_threads=16, batch_size=500)
        )
        assert config.logging.level == "DEBUG"
        assert config.logging.format == "simple"
        assert config.scanner.worker_threads == 16
        assert config.scanner.batch_size == 500
    
    def test_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {
            "logging": {
                "level": "WARNING",
                "format": "detailed"
            },
            "scanner": {
                "worker_threads": 12,
                "batch_size": 250
            }
        }
        config = MediaScannerConfig(**config_dict)
        assert config.logging.level == "WARNING"
        assert config.scanner.worker_threads == 12
