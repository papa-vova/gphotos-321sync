"""Basic import tests to verify dependencies are installed."""

import pytest


def test_common_import():
    """Test that gphotos-321sync-common imports successfully."""
    from gphotos_321sync.common import GPSyncError, ConfigLoader, setup_logging
    assert GPSyncError is not None
    assert ConfigLoader is not None
    assert setup_logging is not None


def test_pillow_import():
    """Test that Pillow imports successfully."""
    from PIL import Image
    assert Image is not None


def test_filetype_import():
    """Test that filetype imports successfully."""
    import filetype
    assert filetype is not None


def test_platformdirs_import():
    """Test that platformdirs imports successfully."""
    import platformdirs
    assert platformdirs is not None


def test_media_scanner_import():
    """Test that media_scanner package imports successfully."""
    import gphotos_321sync.media_scanner
    assert gphotos_321sync.media_scanner is not None
