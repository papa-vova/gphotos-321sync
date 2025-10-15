"""Path utilities for consistent path handling across packages."""

import unicodedata
from pathlib import Path


def normalize_path(path: Path | str) -> str:
    """
    Normalize a path for consistent storage and comparison across all packages.
    
    Applies:
    - Unicode NFC normalization (canonical composition) for consistent Unicode handling
    - Forward slash conversion for cross-platform consistency
    
    This ensures paths with Unicode characters (Cyrillic, Chinese, Arabic, accented
    characters, etc.) are handled consistently regardless of filesystem encoding.
    
    Args:
        path: Path object or string to normalize
        
    Returns:
        Normalized path string with forward slashes and NFC Unicode normalization
        
    Examples:
        >>> normalize_path(Path("café/résumé.txt"))
        'café/résumé.txt'
        >>> normalize_path(r"C:\\Users\\test\\photos")
        'C:/Users/test/photos'
    """
    # Convert to string if Path object
    path_str = str(path)
    
    # Normalize Unicode to NFC (Canonical Composition)
    normalized = unicodedata.normalize('NFC', path_str)
    
    # Convert backslashes to forward slashes for cross-platform consistency
    normalized = normalized.replace('\\', '/')
    
    return normalized
