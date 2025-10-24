"""Tests for fingerprint utilities."""

import pytest
from pathlib import Path
import tempfile
import os
from gphotos_321sync.media_scanner.fingerprint import (
    compute_content_fingerprint,
    compute_crc32,
)


class TestComputeContentFingerprint:
    """Tests for compute_content_fingerprint function."""
    
    def test_change_detection(self):
        """Test that fingerprint changes when file content changes."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Original content" * 1000)
            f.flush()
            file_path = Path(f.name)
        
        try:
            file_size = file_path.stat().st_size
            fingerprint1 = compute_content_fingerprint(file_path, file_size)
            
            # Modify the file
            with open(file_path, 'wb') as f:
                f.write(b"Modified content" * 1000)
            
            file_size = file_path.stat().st_size
            fingerprint2 = compute_content_fingerprint(file_path, file_size)
            
            # Fingerprints should be different
            assert fingerprint1 != fingerprint2
        finally:
            os.unlink(file_path)
    
    def test_identical_files_same_fingerprint(self):
        """Test that identical files produce the same fingerprint."""
        content = b"Test content" * 2000
        
        with tempfile.NamedTemporaryFile(delete=False) as f1:
            f1.write(content)
            f1.flush()
            file1 = Path(f1.name)
        
        with tempfile.NamedTemporaryFile(delete=False) as f2:
            f2.write(content)
            f2.flush()
            file2 = Path(f2.name)
        
        try:
            size1 = file1.stat().st_size
            size2 = file2.stat().st_size
            
            fp1 = compute_content_fingerprint(file1, size1)
            fp2 = compute_content_fingerprint(file2, size2)
            
            assert fp1 == fp2
        finally:
            os.unlink(file1)
            os.unlink(file2)


class TestComputeCrc32:
    """Tests for compute_crc32 function."""
    
    def test_large_file_crc32(self):
        """Test CRC32 on a larger file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # Create ~1MB file
            content = b"X" * (1024 * 1024)
            f.write(content)
            f.flush()
            file_path = Path(f.name)
        
        try:
            crc = compute_crc32(file_path)
            assert isinstance(crc, int)
            assert 0 <= crc <= 0xFFFFFFFF
        finally:
            os.unlink(file_path)
