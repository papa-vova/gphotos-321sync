"""Tests for fingerprint utilities."""

import pytest
from pathlib import Path
import tempfile
import os
from gphotos_321sync.media_scanner.fingerprint import (
    compute_content_fingerprint,
    compute_crc32,
    compute_crc32_hex,
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
    
    def test_small_file_fingerprint(self):
        """Test fingerprint calculation for small files (< 128KB)."""
        content = b"Small file content"
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            f.flush()
            file_path = Path(f.name)
        
        try:
            file_size = file_path.stat().st_size
            fingerprint = compute_content_fingerprint(file_path, file_size)
            
            # Should be a 64-character hex string (SHA-256)
            assert isinstance(fingerprint, str)
            assert len(fingerprint) == 64
            assert all(c in '0123456789abcdef' for c in fingerprint)
        finally:
            os.unlink(file_path)
    
    def test_large_file_fingerprint(self):
        """Test fingerprint calculation for large files (> 128KB)."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # Create ~1MB file
            content = b"X" * (1024 * 1024)
            f.write(content)
            f.flush()
            file_path = Path(f.name)
        
        try:
            file_size = file_path.stat().st_size
            fingerprint = compute_content_fingerprint(file_path, file_size)
            
            # Should be a 64-character hex string (SHA-256)
            assert isinstance(fingerprint, str)
            assert len(fingerprint) == 64
            assert all(c in '0123456789abcdef' for c in fingerprint)
        finally:
            os.unlink(file_path)
    
    def test_fingerprint_head_tail_consistency(self):
        """Test that fingerprint is consistent for head+tail sampling."""
        # Create a large file (>128KB) with distinct head and tail
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # Write distinct head (exactly 64KB)
            f.write(b"HEAD_CONTENT" * 5461)  # Exactly 65532 bytes
            f.write(b"XX")  # Add 4 more bytes to make exactly 65536 bytes
            # Write middle content (large enough to make file >128KB)
            f.write(b"MIDDLE" * 20000)  # ~120KB middle
            # Write distinct tail (exactly 64KB)
            f.write(b"TAIL_CONTENT" * 5461)  # Exactly 65532 bytes
            f.write(b"YY")  # Add 4 more bytes to make exactly 65536 bytes
            f.flush()
            file_path = Path(f.name)
        
        try:
            file_size = file_path.stat().st_size
            # Ensure file is >128KB so it uses head+tail sampling
            assert file_size > 131072  # 128KB
            
            fingerprint1 = compute_content_fingerprint(file_path, file_size)
            
            # Modify only the middle content (should not affect fingerprint)
            # Make sure we don't overwrite the tail
            with open(file_path, 'r+b') as f:
                f.seek(65536)  # Skip head (exactly 64KB)
                f.write(b"DIFFERENT_MIDDLE" * 5000)  # Only modify middle part
            
            fingerprint2 = compute_content_fingerprint(file_path, file_size)
            
            # Fingerprints should be the same (only head+tail matter for large files)
            assert fingerprint1 == fingerprint2
        finally:
            os.unlink(file_path)
    
    def test_fingerprint_small_file_reads_entire_content(self):
        """Test that small files (≤128KB) read entire content."""
        # Create a small file (<128KB)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"SMALL_FILE_CONTENT" * 1000)  # ~18KB
            f.flush()
            file_path = Path(f.name)
        
        try:
            file_size = file_path.stat().st_size
            # Ensure file is ≤128KB so it reads entire content
            assert file_size <= 131072  # 128KB
            
            fingerprint1 = compute_content_fingerprint(file_path, file_size)
            
            # Modify any part of the file (should affect fingerprint)
            with open(file_path, 'r+b') as f:
                f.seek(1000)  # Modify middle
                f.write(b"MODIFIED")
            
            fingerprint2 = compute_content_fingerprint(file_path, file_size)
            
            # Fingerprints should be different (entire file is read for small files)
            assert fingerprint1 != fingerprint2
        finally:
            os.unlink(file_path)
    
    def test_nonexistent_file(self):
        """Test fingerprint calculation for nonexistent file."""
        nonexistent_path = Path("/nonexistent/file.txt")
        
        with pytest.raises(OSError):
            compute_content_fingerprint(nonexistent_path, 1000)


class TestComputeCrc32:
    """Tests for compute_crc32 function."""
    
    def test_small_file_crc32(self):
        """Test CRC32 on a small file."""
        content = b"Hello, World!"
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            f.flush()
            file_path = Path(f.name)
        
        try:
            crc = compute_crc32(file_path)
            assert isinstance(crc, int)
            assert 0 <= crc <= 0xFFFFFFFF
        finally:
            os.unlink(file_path)
    
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
    
    def test_identical_files_same_crc32(self):
        """Test that identical files produce the same CRC32."""
        content = b"Test content for CRC32"
        
        with tempfile.NamedTemporaryFile(delete=False) as f1:
            f1.write(content)
            f1.flush()
            file1 = Path(f1.name)
        
        with tempfile.NamedTemporaryFile(delete=False) as f2:
            f2.write(content)
            f2.flush()
            file2 = Path(f2.name)
        
        try:
            crc1 = compute_crc32(file1)
            crc2 = compute_crc32(file2)
            
            assert crc1 == crc2
        finally:
            os.unlink(file1)
            os.unlink(file2)
    
    def test_different_files_different_crc32(self):
        """Test that different files produce different CRC32."""
        content1 = b"First file content"
        content2 = b"Second file content"
        
        with tempfile.NamedTemporaryFile(delete=False) as f1:
            f1.write(content1)
            f1.flush()
            file1 = Path(f1.name)
        
        with tempfile.NamedTemporaryFile(delete=False) as f2:
            f2.write(content2)
            f2.flush()
            file2 = Path(f2.name)
        
        try:
            crc1 = compute_crc32(file1)
            crc2 = compute_crc32(file2)
            
            assert crc1 != crc2
        finally:
            os.unlink(file1)
            os.unlink(file2)
    
    def test_nonexistent_file_crc32(self):
        """Test CRC32 calculation for nonexistent file."""
        nonexistent_path = Path("/nonexistent/file.txt")
        
        with pytest.raises(OSError):
            compute_crc32(nonexistent_path)


class TestComputeCrc32Hex:
    """Tests for compute_crc32_hex function."""
    
    def test_crc32_hex_format(self):
        """Test that CRC32 hex returns proper format."""
        content = b"Test content for hex CRC32"
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            f.flush()
            file_path = Path(f.name)
        
        try:
            crc_hex = compute_crc32_hex(file_path)
            
            # Should be an 8-character hex string
            assert isinstance(crc_hex, str)
            assert len(crc_hex) == 8
            assert all(c in '0123456789abcdef' for c in crc_hex)
        finally:
            os.unlink(file_path)
    
    def test_crc32_hex_consistency(self):
        """Test that CRC32 hex is consistent with integer CRC32."""
        content = b"Consistency test content"
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            f.flush()
            file_path = Path(f.name)
        
        try:
            crc_int = compute_crc32(file_path)
            crc_hex = compute_crc32_hex(file_path)
            
            # Hex should match integer representation
            expected_hex = f"{crc_int:08x}"
            assert crc_hex == expected_hex
        finally:
            os.unlink(file_path)
    
    def test_crc32_hex_identical_files(self):
        """Test that identical files produce the same CRC32 hex."""
        content = b"Identical content test"
        
        with tempfile.NamedTemporaryFile(delete=False) as f1:
            f1.write(content)
            f1.flush()
            file1 = Path(f1.name)
        
        with tempfile.NamedTemporaryFile(delete=False) as f2:
            f2.write(content)
            f2.flush()
            file2 = Path(f2.name)
        
        try:
            crc_hex1 = compute_crc32_hex(file1)
            crc_hex2 = compute_crc32_hex(file2)
            
            assert crc_hex1 == crc_hex2
        finally:
            os.unlink(file1)
            os.unlink(file2)
    
    def test_nonexistent_file_crc32_hex(self):
        """Test CRC32 hex calculation for nonexistent file."""
        nonexistent_path = Path("/nonexistent/file.txt")
        
        with pytest.raises(OSError):
            compute_crc32_hex(nonexistent_path)


class TestFingerprintIntegration:
    """Integration tests for fingerprint functions."""
    
    def test_fingerprint_vs_crc32_different_purposes(self):
        """Test that fingerprint and CRC32 serve different purposes."""
        # Create a file with distinct head/tail but same overall content
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"HEAD" + b"MIDDLE" * 1000 + b"TAIL")
            f.flush()
            file_path = Path(f.name)
        
        try:
            file_size = file_path.stat().st_size
            fingerprint = compute_content_fingerprint(file_path, file_size)
            crc32 = compute_crc32(file_path)
            
            # Both should be valid but different
            assert isinstance(fingerprint, str)
            assert len(fingerprint) == 64
            assert isinstance(crc32, int)
            assert 0 <= crc32 <= 0xFFFFFFFF
            
            # They should be different (different algorithms)
            assert fingerprint != f"{crc32:064x}"
        finally:
            os.unlink(file_path)
    
    def test_empty_file_handling(self):
        """Test handling of empty files."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"")
            f.flush()
            file_path = Path(f.name)
        
        try:
            file_size = file_path.stat().st_size
            assert file_size == 0
            
            # All functions should handle empty files gracefully
            fingerprint = compute_content_fingerprint(file_path, file_size)
            crc32 = compute_crc32(file_path)
            crc32_hex = compute_crc32_hex(file_path)
            
            assert isinstance(fingerprint, str)
            assert len(fingerprint) == 64
            assert isinstance(crc32, int)
            assert isinstance(crc32_hex, str)
            assert len(crc32_hex) == 8
        finally:
            os.unlink(file_path)
