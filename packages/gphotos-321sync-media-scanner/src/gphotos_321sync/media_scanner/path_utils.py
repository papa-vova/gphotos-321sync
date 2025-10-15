"""Path normalization and file type detection utilities."""

import unicodedata
from pathlib import Path

# Supported media file extensions
MEDIA_EXTENSIONS = {
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.heif', '.tiff', '.tif',
    # Videos
    '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.wmv', '.flv', '.webm',
}

# JSON sidecar extension
JSON_EXTENSION = '.json'


def normalize_path(path: Path) -> str:
    """
    Normalize a path for consistent storage and comparison.
    
    - Applies Unicode NFC normalization (canonical composition)
    - Converts to forward slashes for cross-platform consistency
    - Converts to string representation
    
    Args:
        path: Path object to normalize
        
    Returns:
        Normalized path string with forward slashes
    """
    # Convert to string and normalize Unicode
    path_str = str(path)
    normalized = unicodedata.normalize('NFC', path_str)
    
    # Convert backslashes to forward slashes
    normalized = normalized.replace('\\', '/')
    
    return normalized


def is_media_file(path: Path) -> bool:
    """
    Check if a file is a supported media file based on extension.
    
    Args:
        path: Path to check
        
    Returns:
        True if the file has a supported media extension
    """
    return path.suffix.lower() in MEDIA_EXTENSIONS


def is_json_sidecar(path: Path) -> bool:
    """
    Check if a file is a JSON sidecar file.
    
    JSON sidecars in Google Takeout have the pattern: <filename>.<ext>.json
    For example: IMG_1234.JPG.json
    
    Args:
        path: Path to check
        
    Returns:
        True if the file is a JSON sidecar
    """
    if path.suffix.lower() != JSON_EXTENSION:
        return False
    
    # Check if the stem (without .json) has a media extension
    stem_path = Path(path.stem)
    return stem_path.suffix.lower() in MEDIA_EXTENSIONS
