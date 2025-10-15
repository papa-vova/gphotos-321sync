"""Path utilities for media scanner."""

import os
from pathlib import Path
from gphotos_321sync.common import normalize_path

# Re-export normalize_path from common package for backward compatibility
__all__ = ['normalize_path', 'should_scan_file', 'is_hidden']

# System files to exclude (cross-platform)
SYSTEM_FILES = {
    'thumbs.db',      # Windows thumbnail cache
    'desktop.ini',    # Windows folder settings
    '.ds_store',      # macOS folder metadata
    'icon\r',         # macOS custom folder icon (has literal carriage return!)
}

# Temporary file extensions to exclude
TEMP_EXTENSIONS = {'.tmp', '.temp', '.cache', '.bak', '.swp'}


def is_hidden(path: Path) -> bool:
    """
    Cross-platform hidden file detection.
    
    Unix/Linux/macOS: Files starting with '.'
    Windows: Files with FILE_ATTRIBUTE_HIDDEN flag
    
    Args:
        path: Path to check
        
    Returns:
        True if file is hidden on the current platform
    """
    # Unix-style: starts with dot
    if path.name.startswith('.'):
        return True
    
    # Windows: check file attributes
    if os.name == 'nt' and path.exists():
        try:
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            # FILE_ATTRIBUTE_HIDDEN = 2
            return attrs != -1 and bool(attrs & 2)
        except (AttributeError, OSError):
            pass
    
    return False


def should_scan_file(path: Path) -> bool:
    """
    Determine if a file should be scanned by the media scanner.
    
    IMPORTANT: This does NOT check file content! It only excludes obvious
    system/temporary files to avoid wasting time on MIME detection.
    
    The actual media detection happens via MIME type checking (detect_mime_type).
    
    Excluded files:
    - Hidden files (Unix: starts with '.', Windows: FILE_ATTRIBUTE_HIDDEN)
    - System files (Thumbs.db, .DS_Store, desktop.ini, Icon\r)
    - Temporary files (.tmp, .temp, .cache, .bak, .swp)
    
    Args:
        path: Path to check
        
    Returns:
        True if the file should be scanned (MIME detection will determine if it's media)
    """
    filename = path.name.lower()
    
    # Skip hidden files (cross-platform)
    if is_hidden(path):
        return False
    
    # Skip known system files
    if filename in SYSTEM_FILES:
        return False
    
    # Skip temporary files by extension
    if path.suffix.lower() in TEMP_EXTENSIONS:
        return False
    
    # Everything else should be scanned - MIME detection will determine if it's media
    return True
