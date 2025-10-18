"""File fingerprinting utilities for change detection."""

import hashlib
from pathlib import Path
from gphotos_321sync.common import compute_crc32

# Re-export compute_crc32 from common for backward compatibility
__all__ = ['compute_content_fingerprint', 'compute_crc32']

# Fingerprint configuration
FINGERPRINT_HEAD_SIZE = 65536  # 64 KB from start
FINGERPRINT_TAIL_SIZE = 65536  # 64 KB from end


def compute_content_fingerprint(file_path: Path, file_size: int) -> str:
    """
    Compute a SHA-256 fingerprint of file head and tail.
    
    This is a fast approximation for change detection that reads only
    the first and last 64KB of the file, rather than the entire content.
    
    For files smaller than 128KB, reads the entire file.
    
    Args:
        file_path: Path to the file
        file_size: Size of the file in bytes
        
    Returns:
        Hexadecimal SHA-256 hash string
        
    Raises:
        OSError: If file cannot be read
    """
    hasher = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        if file_size <= FINGERPRINT_HEAD_SIZE + FINGERPRINT_TAIL_SIZE:
            # Small file: read entire content
            hasher.update(f.read())
        else:
            # Large file: read head and tail
            # Read head
            head = f.read(FINGERPRINT_HEAD_SIZE)
            hasher.update(head)
            
            # Seek to tail position
            f.seek(file_size - FINGERPRINT_TAIL_SIZE)
            tail = f.read(FINGERPRINT_TAIL_SIZE)
            hasher.update(tail)
    
    return hasher.hexdigest()
