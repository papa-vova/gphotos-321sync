"""Tests for configuration system."""

import pytest
from pathlib import Path
from gphotos_321sync.config import ConfigLoader
from gphotos_321sync.errors import ConfigurationError


def test_config_loader_loads_defaults():
    """Test that config loader can load default configuration."""
    loader = ConfigLoader()
    config = loader.load()

    assert config.app.name == "gphotos-sync"
    assert config.deployment.mode in ["local", "hybrid", "cloud_only"]
    assert config.resources.max_cpu_percent > 0
    assert config.resources.max_workers >= 2


def test_path_expansion():
    """Test that path variables are expanded correctly."""
    loader = ConfigLoader()
    config = loader.load()

    # Paths should not contain variables after loading
    assert "${USER_DATA}" not in config.paths.working_directory
    assert "${USER_HOME}" not in config.paths.takeout_archives

    # Paths should be valid
    assert Path(config.paths.working_directory).is_absolute()


def test_resource_auto_detection():
    """Test that resource limits are auto-detected when set to 0."""
    loader = ConfigLoader()
    config = loader.load()

    # Auto-detected values should be positive
    assert config.resources.max_workers > 0
    assert config.resources.io_workers > 0


@pytest.mark.asyncio
async def test_config_validation():
    """Test that invalid configuration raises validation errors."""
    from gphotos_321sync.config.schema import ResourcesConfig

    # Invalid CPU percent
    with pytest.raises(Exception):  # Pydantic validation error
        ResourcesConfig(
            max_cpu_percent=150.0,  # Invalid: > 100
            max_workers=4,
            io_workers=8,
            max_memory_percent=50.0,
            max_memory_mb=0,
            max_concurrent_reads=10,
            max_disk_io_mbps=100.0,
            resource_check_interval_seconds=5.0,
            enable_adaptive_throttling=True,
        )
