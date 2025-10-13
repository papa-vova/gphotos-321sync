"""Configuration utilities."""

import os
import tempfile
import platformdirs
from pathlib import Path


def expand_path_variables(path: str) -> str:
    """Expand ${VAR} variables in paths.

    Supported variables:
        ${USER_HOME}: User's home directory
        ${USER_DATA}: User data directory
        ${USER_CONFIG}: User config directory
        ${USER_CACHE}: User cache directory
        ${USER_LOGS}: User log directory
        ${TEMP}: Temporary directory

    Args:
        path: Path string with variables

    Returns:
        Expanded path string
    """
    if not isinstance(path, str):
        return path

    replacements = {
        "${USER_HOME}": str(Path.home()),
        "${USER_DATA}": platformdirs.user_data_dir(),
        "${USER_CONFIG}": platformdirs.user_config_dir(),
        "${USER_CACHE}": platformdirs.user_cache_dir(),
        "${USER_LOGS}": platformdirs.user_log_dir(),
        "${TEMP}": tempfile.gettempdir(),
    }

    for var, value in replacements.items():
        path = path.replace(var, value)

    return path


def get_cpu_count() -> int:
    """Get number of CPU cores, with fallback."""
    return os.cpu_count() or 4


def auto_detect_workers(multiplier: float = 1.0, min_workers: int = 2) -> int:
    """Auto-detect number of worker processes.

    Args:
        multiplier: Multiplier for CPU count (e.g., 0.5 for half cores)
        min_workers: Minimum number of workers

    Returns:
        Number of workers
    """
    cpu_count = get_cpu_count()
    workers = max(min_workers, int(cpu_count * multiplier))
    return workers


def auto_detect_io_workers(multiplier: float = 3.0, min_workers: int = 4) -> int:
    """Auto-detect number of I/O worker threads.

    Args:
        multiplier: Multiplier for CPU count (e.g., 3.0 for 3x cores)
        min_workers: Minimum number of workers

    Returns:
        Number of I/O workers
    """
    cpu_count = get_cpu_count()
    workers = max(min_workers, int(cpu_count * multiplier))
    return workers
