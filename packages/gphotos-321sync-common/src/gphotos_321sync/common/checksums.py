"""Checksum utilities for file integrity verification."""

import zlib
from pathlib import Path


def compute_crc32(file_path: Path) -> int:
    """
    Compute CRC32 checksum of entire file.
    
    Used for:
    - File integrity verification (extractor)
    - Duplicate detection (scanner)
    
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
        while chunk := f.read(chunk_size):
            crc = zlib.crc32(chunk, crc)
    
    # Return as unsigned 32-bit integer
    return crc & 0xFFFFFFFF
