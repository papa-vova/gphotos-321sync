"""Tests for checksum utilities."""

import pytest
from pathlib import Path
from gphotos_321sync.common.checksums import compute_crc32, compute_crc32_hex


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


class TestComputeCRC32Hex:
    """Tests for compute_crc32_hex function."""
    
    def test_crc32_hex_different_files(self, tmp_path):
        """Test that different files have different CRC32 hex values."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_text("Content A", encoding='utf-8')
        file2.write_text("Content B", encoding='utf-8')
        
        hex1 = compute_crc32_hex(file1)
        hex2 = compute_crc32_hex(file2)
        
        assert hex1 != hex2
        assert isinstance(hex1, str)
        assert isinstance(hex2, str)
        assert len(hex1) == 8
        assert len(hex2) == 8
    
    def test_crc32_hex_same_content(self, tmp_path):
        """Test that same content produces same CRC32 hex."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        content = "Same content"
        file1.write_text(content, encoding='utf-8')
        file2.write_text(content, encoding='utf-8')
        
        hex1 = compute_crc32_hex(file1)
        hex2 = compute_crc32_hex(file2)
        
        assert hex1 == hex2
    
    def test_crc32_hex_large_file(self, tmp_path):
        """Test CRC32 hex calculation on large file."""
        large_file = tmp_path / "large.bin"
        # Create a file larger than chunk size (64KB)
        large_file.write_bytes(b'X' * (128 * 1024))
        
        hex_result = compute_crc32_hex(large_file)
        
        assert isinstance(hex_result, str)
        assert len(hex_result) == 8
        assert all(c in '0123456789abcdef' for c in hex_result)
    
    def test_crc32_hex_empty_file(self, tmp_path):
        """Test CRC32 hex calculation on empty file."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("", encoding='utf-8')
        
        hex_result = compute_crc32_hex(empty_file)
        
        assert isinstance(hex_result, str)
        # CRC32 of empty file should be 0, which is "00000000" in hex
        assert hex_result == "00000000"
    
    def test_crc32_hex_nonexistent_file(self, tmp_path):
        """Test CRC32 hex calculation on non-existent file raises OSError."""
        nonexistent = tmp_path / "does_not_exist.txt"
        
        with pytest.raises(OSError):
            compute_crc32_hex(nonexistent)
    
    def test_crc32_hex_consistency_with_int_version(self, tmp_path):
        """Test that hex version produces consistent results with int version."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World", encoding='utf-8')
        
        int_result = compute_crc32(test_file)
        hex_result = compute_crc32_hex(test_file)
        
        # Convert int to hex string for comparison
        int_as_hex = f"{int_result:08x}"
        assert int_as_hex == hex_result
