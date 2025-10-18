"""Tests for file processor module."""

import pytest
from pathlib import Path
from gphotos_321sync.media_scanner.file_processor import (
    process_file_cpu_work,
    calculate_crc32
)


@pytest.fixture
def test_image(tmp_path):
    """Create a test image file."""
    # Create a simple test file
    image_path = tmp_path / "test.jpg"
    # Write some fake JPEG data (just for testing, not a real JPEG)
    image_path.write_bytes(b'\xFF\xD8\xFF\xE0' + b'fake jpeg data' * 100)
    return image_path


@pytest.fixture
def test_text_file(tmp_path):
    """Create a test text file."""
    text_path = tmp_path / "test.txt"
    text_path.write_text("This is a test file for CRC32 calculation.")
    return text_path


def test_calculate_crc32_different_files(tmp_path):
    """Test that different files have different CRC32 values."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    
    file1.write_text("Content A")
    file2.write_text("Content B")
    
    crc1 = calculate_crc32(file1)
    crc2 = calculate_crc32(file2)
    
    assert crc1 != crc2


def test_calculate_crc32_large_file(tmp_path):
    """Test CRC32 calculation on large file (>64KB)."""
    large_file = tmp_path / "large.bin"
    # Create a file larger than chunk size (64KB)
    large_file.write_bytes(b'X' * (128 * 1024))
    
    crc = calculate_crc32(large_file)
    
    assert len(crc) == 8
    assert all(c in '0123456789abcdef' for c in crc)


def test_process_file_cpu_work_success(test_image):
    """Test successful file processing."""
    file_size = test_image.stat().st_size
    
    result = process_file_cpu_work(test_image, file_size)
    
    assert result['success'] is True
    assert result['error'] is None
    assert result['mime_type'] is not None
    assert result['crc32'] is not None
    assert len(result['crc32']) == 8
    assert result['content_fingerprint'] is not None
    assert len(result['content_fingerprint']) == 64


def test_process_file_cpu_work_mime_type(test_image):
    """Test that MIME type is detected."""
    file_size = test_image.stat().st_size
    
    result = process_file_cpu_work(test_image, file_size)
    
    # Should detect MIME type (might be image/jpeg or application/octet-stream)
    assert result['mime_type'] is not None


def test_process_file_cpu_work_crc32(test_text_file):
    """Test that CRC32 is calculated."""
    file_size = test_text_file.stat().st_size
    
    result = process_file_cpu_work(test_text_file, file_size)
    
    assert result['crc32'] is not None
    assert len(result['crc32']) == 8
    
    # Verify it matches direct calculation
    expected_crc = calculate_crc32(test_text_file)
    assert result['crc32'] == expected_crc


def test_process_file_cpu_work_fingerprint(test_text_file):
    """Test that content fingerprint is calculated."""
    file_size = test_text_file.stat().st_size
    
    result = process_file_cpu_work(test_text_file, file_size)
    
    assert result['content_fingerprint'] is not None
    assert len(result['content_fingerprint']) == 64
    assert all(c in '0123456789abcdef' for c in result['content_fingerprint'])


def test_process_file_cpu_work_exif_data(test_image):
    """Test that EXIF data extraction is attempted."""
    file_size = test_image.stat().st_size
    
    result = process_file_cpu_work(test_image, file_size)
    
    # EXIF data should be present (might be empty dict if extraction fails)
    assert 'exif_data' in result
    assert isinstance(result['exif_data'], dict)


def test_process_file_cpu_work_resolution(test_image):
    """Test that resolution extraction is attempted."""
    file_size = test_image.stat().st_size
    
    result = process_file_cpu_work(test_image, file_size)
    
    # Width and height should be present (might be None if extraction fails)
    assert 'width' in result
    assert 'height' in result


def test_process_file_cpu_work_video_data(test_image):
    """Test that video data is None for non-video files."""
    file_size = test_image.stat().st_size
    
    result = process_file_cpu_work(test_image, file_size)
    
    # Video data should be None for non-video files
    assert result['video_data'] is None


def test_process_file_cpu_work_nonexistent_file(tmp_path):
    """Test processing non-existent file returns error."""
    nonexistent = tmp_path / "does_not_exist.jpg"
    
    result = process_file_cpu_work(nonexistent, 0)
    
    assert result['success'] is False
    assert result['error'] is not None
    assert result['error_category'] is not None


def test_process_file_cpu_work_error_handling(tmp_path):
    """Test that errors are caught and returned in result."""
    # Create a file that will cause errors
    bad_file = tmp_path / "bad.jpg"
    bad_file.write_bytes(b'invalid data')
    
    file_size = bad_file.stat().st_size
    result = process_file_cpu_work(bad_file, file_size)
    
    # Processing might succeed or fail depending on what operations work
    # But it should never raise an exception
    assert 'success' in result
    assert 'error' in result


def test_process_file_cpu_work_small_file(tmp_path):
    """Test processing small file (<128KB)."""
    small_file = tmp_path / "small.txt"
    small_file.write_text("Small file content")
    
    file_size = small_file.stat().st_size
    result = process_file_cpu_work(small_file, file_size)
    
    assert result['success'] is True
    assert result['crc32'] is not None
    assert result['content_fingerprint'] is not None


def test_process_file_cpu_work_large_file(tmp_path):
    """Test processing large file (>128KB)."""
    large_file = tmp_path / "large.bin"
    # Create a file larger than fingerprint threshold
    large_file.write_bytes(b'X' * (256 * 1024))
    
    file_size = large_file.stat().st_size
    result = process_file_cpu_work(large_file, file_size)
    
    assert result['success'] is True
    assert result['crc32'] is not None
    assert result['content_fingerprint'] is not None


def test_process_file_cpu_work_empty_file(tmp_path):
    """Test processing empty file."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("")
    
    file_size = empty_file.stat().st_size
    result = process_file_cpu_work(empty_file, file_size)
    
    # Should handle empty file gracefully
    assert 'success' in result
    assert 'crc32' in result
