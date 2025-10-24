"""Tests for checksum utilities."""

import pytest
from pathlib import Path
from gphotos_321sync.common.checksums import compute_crc32


class TestComputeCRC32:
    """Tests for compute_crc32 function."""
    
    def test_crc32_different_files(self, tmp_path):
        """Test that different files have different CRC32 values."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_text("Content A", encoding='utf-8')
        file2.write_text("Content B", encoding='utf-8')
        
        crc1 = compute_crc32(file1)
        crc2 = compute_crc32(file2)
        
        assert crc1 != crc2
        assert isinstance(crc1, int)
        assert isinstance(crc2, int)
    
    def test_crc32_same_content(self, tmp_path):
        """Test that same content produces same CRC32."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        content = "Same content"
        file1.write_text(content, encoding='utf-8')
        file2.write_text(content, encoding='utf-8')
        
        crc1 = compute_crc32(file1)
        crc2 = compute_crc32(file2)
        
        assert crc1 == crc2
    
    def test_crc32_large_file(self, tmp_path):
        """Test CRC32 calculation on large file."""
        large_file = tmp_path / "large.bin"
        # Create a file larger than chunk size (64KB)
        large_file.write_bytes(b'X' * (128 * 1024))
        
        crc = compute_crc32(large_file)
        
        assert isinstance(crc, int)
        assert crc != 0
    
    def test_crc32_empty_file(self, tmp_path):
        """Test CRC32 calculation on empty file."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("", encoding='utf-8')
        
        crc = compute_crc32(empty_file)
        
        assert isinstance(crc, int)
        # CRC32 of empty file should be 0
        assert crc == 0
    
    def test_crc32_nonexistent_file(self, tmp_path):
        """Test CRC32 calculation on non-existent file raises OSError."""
        nonexistent = tmp_path / "does_not_exist.txt"
        
        with pytest.raises(OSError):
            compute_crc32(nonexistent)
