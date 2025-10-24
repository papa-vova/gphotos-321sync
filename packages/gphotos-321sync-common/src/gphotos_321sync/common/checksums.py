"""Checksum utilities for file integrity verification."""

import zlib
from pathlib import Path

# Constants for checksum calculation
CRC32_CHUNK_SIZE = 65536  # 64 KB chunks


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
    chunk_size = CRC32_CHUNK_SIZE
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            crc = zlib.crc32(chunk, crc)
    
    # Return as unsigned 32-bit integer
    return crc & 0xFFFFFFFF


def compute_crc32_hex(file_path: Path) -> str:
    """
    Compute CRC32 checksum of entire file as hex string.
    
    Used for:
    - Duplicate detection (scanner) - hex format for database storage
    
    Args:
        file_path: Path to the file
        
    Returns:
        CRC32 checksum as 8-character hex string (e.g., "a1b2c3d4")
        
    Raises:
        OSError: If file cannot be read
    """
    crc_int = compute_crc32(file_path)
    return f"{crc_int:08x}"
