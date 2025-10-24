"""Tests for scanner-specific configuration."""

import pytest
from gphotos_321sync.media_scanner.config import (
    LoggingConfig,
    ScannerConfig,
    MediaScannerConfig,
)


class TestScannerConfig:
    """Tests for ScannerConfig (scanner-specific parameters only)."""
    
    def test_scanner_config_defaults(self):
        """Test scanner-specific default values."""
        config = ScannerConfig()
        
        # Scanner-specific defaults
        assert config.target_media_path == ""
        assert config.batch_size == 100
        assert config.worker_threads > 0
        assert config.worker_processes > 0
        assert config.queue_maxsize > 0
        assert config.use_ffprobe is False
        assert config.use_exiftool is False
    
    def test_scanner_config_custom_values(self):
        """Test scanner-specific parameter overrides."""
        config = ScannerConfig(
            target_media_path="/path/to/media",
            worker_threads=8,
            worker_processes=4,
            batch_size=50,
            queue_maxsize=500,
            use_ffprobe=True,
            use_exiftool=True
        )
        
        assert config.target_media_path == "/path/to/media"
        assert config.worker_threads == 8
        assert config.worker_processes == 4
        assert config.batch_size == 50
        assert config.queue_maxsize == 500
        assert config.use_ffprobe is True
        assert config.use_exiftool is True


class TestMediaScannerConfig:
    """Tests for MediaScannerConfig (root configuration)."""
    
    def test_media_scanner_config_defaults(self):
        """Test root configuration with all defaults."""
        config = MediaScannerConfig()
        
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.scanner, ScannerConfig)
        assert config.logging.level == "INFO"
        assert config.scanner.batch_size == 100
