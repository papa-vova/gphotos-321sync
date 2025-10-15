"""File fingerprinting utilities for change detection."""

import hashlib
import zlib
from pathlib import Path

# Fingerprint configuration
FINGERPRINT_HEAD_SIZE = 8192  # 8 KB from start
FINGERPRINT_TAIL_SIZE = 8192  # 8 KB from end


def compute_content_fingerprint(file_path: Path, file_size: int) -> str:
    """
    Compute a SHA-256 fingerprint of file head and tail.
    
    This is a fast approximation for change detection that reads only
    the first and last 8KB of the file, rather than the entire content.
    
    For files smaller than 16KB, reads the entire file.
    
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


def compute_crc32(file_path: Path) -> int:
    """
    Compute CRC32 checksum of entire file.
    
    This is used for duplicate detection. CRC32 is faster than full
    SHA-256 but still requires reading the entire file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        CRC32 checksum as unsigned 32-bit integer
        
    Raises:
        OSError: If file cannot be read
    """
    crc = 0
    chunk_size = 65536  # 64 KB chunks
    
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
    
    # Return as unsigned 32-bit integer
    return crc & 0xFFFFFFFF
