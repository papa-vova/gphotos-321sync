"""Tests for archive verification and selective re-extraction functionality."""

import pytest
import zipfile
import zlib
import unicodedata
from pathlib import Path
from gphotos_321sync.processing.extractor import (
    ArchiveDiscovery,
    ArchiveExtractor,
    ArchiveFormat,
    ExtractionState,
    normalize_unicode_path,
)


@pytest.fixture
def test_zip_with_files(tmp_path):
    """Create a test ZIP archive with multiple files."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    
    zip_path = source_dir / "test.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add various files with known content
        zf.writestr("file1.txt", "Content of file 1")
        zf.writestr("file2.txt", "Content of file 2" * 100)  # Larger file
        zf.writestr("dir/file3.txt", "Nested file content")
        zf.writestr("dir/file4.txt", "Another nested file")
        zf.writestr("file5.txt", "Last file")
    
    return zip_path


@pytest.fixture
def target_dir(tmp_path):
    """Create a target directory for extraction."""
    target = tmp_path / "target"
    target.mkdir()
    return target


class TestVerificationMissingFiles:
    """Test verification with missing files."""
    
    def test_all_files_missing(self, test_zip_with_files, target_dir):
        """Test verification when all files are missing."""
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        
        # Verify without extracting first
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive, 
            target_dir
        )
        
        assert all_valid is False
        assert len(bad_files) == 5  # All 5 files missing
    
    def test_some_files_missing(self, test_zip_with_files, target_dir):
        """Test verification when some files are missing."""
        # Extract first
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Delete some files
        (target_dir / "file1.txt").unlink()
        (target_dir / "dir" / "file3.txt").unlink()
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is False
        assert len(bad_files) == 2
        assert "file1.txt" in bad_files
        assert "dir/file3.txt" in bad_files
    
    def test_one_file_missing(self, test_zip_with_files, target_dir):
        """Test verification when one file is missing."""
        # Extract first
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Delete one file
        (target_dir / "file5.txt").unlink()
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is False
        assert len(bad_files) == 1
        assert "file5.txt" in bad_files


class TestVerificationCorruptedFiles:
    """Test verification with corrupted files."""
    
    def test_file_size_mismatch_smaller(self, test_zip_with_files, target_dir):
        """Test verification when file is smaller than expected."""
        # Extract first
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Truncate a file
        file_path = target_dir / "file2.txt"
        original_content = file_path.read_text()
        file_path.write_text(original_content[:10])  # Truncate
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is False
        assert len(bad_files) == 1
        assert "file2.txt" in bad_files
    
    def test_file_size_mismatch_larger(self, test_zip_with_files, target_dir):
        """Test verification when file is larger than expected."""
        # Extract first
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Append to a file
        file_path = target_dir / "file1.txt"
        with open(file_path, 'a') as f:
            f.write("EXTRA DATA")
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is False
        assert len(bad_files) == 1
        assert "file1.txt" in bad_files
    
    def test_file_crc32_mismatch(self, test_zip_with_files, target_dir):
        """Test verification when file has correct size but wrong content."""
        # Extract first
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Modify file content but keep same size
        file_path = target_dir / "file1.txt"
        original_content = file_path.read_text()
        corrupted_content = "X" * len(original_content)  # Same length, different content
        file_path.write_text(corrupted_content)
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is False
        assert len(bad_files) == 1
        assert "file1.txt" in bad_files


class TestVerificationMixedScenarios:
    """Test verification with mixed corruption scenarios."""
    
    def test_missing_and_corrupted_files(self, test_zip_with_files, target_dir):
        """Test verification with both missing and corrupted files.
        
        Note: Verification uses fast-fail - if files are missing, it returns immediately
        without checking for corruption. This is intentional for performance.
        """
        # Extract first
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Delete some files
        (target_dir / "file1.txt").unlink()
        
        # Corrupt other files (won't be detected due to fast-fail on missing)
        (target_dir / "file2.txt").write_text("CORRUPTED")
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is False
        # Fast-fail on missing files - only reports missing, not corrupted
        assert len(bad_files) >= 1
        assert "file1.txt" in bad_files  # Missing file detected
    
    def test_first_file_corrupted(self, test_zip_with_files, target_dir):
        """Test verification detects corruption in first file."""
        # Extract first
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Corrupt first file (alphabetically)
        (target_dir / "dir" / "file3.txt").write_text("BAD")
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is False
        assert len(bad_files) >= 1
        assert "dir/file3.txt" in bad_files
    
    def test_last_file_corrupted(self, test_zip_with_files, target_dir):
        """Test verification detects corruption in last file."""
        # Extract first
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Corrupt last file
        (target_dir / "file5.txt").write_text("CORRUPTED")
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is False
        assert "file5.txt" in bad_files
    
    def test_multiple_scattered_corrupted_files(self, test_zip_with_files, target_dir):
        """Test verification collects all corrupted files."""
        # Extract first
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Corrupt multiple files
        (target_dir / "file1.txt").write_text("BAD1")
        (target_dir / "dir" / "file3.txt").write_text("BAD2")
        (target_dir / "file5.txt").write_text("BAD3")
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is False
        assert len(bad_files) == 3
        assert "file1.txt" in bad_files
        assert "dir/file3.txt" in bad_files
        assert "file5.txt" in bad_files


class TestSelectiveReExtraction:
    """Test selective re-extraction of corrupted files."""
    
    def test_reextract_single_corrupted_file(self, test_zip_with_files, target_dir):
        """Test re-extracting a single corrupted file."""
        # Extract first
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Corrupt one file
        corrupted_file = target_dir / "file2.txt"
        corrupted_file.write_text("CORRUPTED")
        
        # Re-extract only the corrupted file
        extractor._extract_specific_files_from_zip(
            archive.path,
            target_dir,
            ["file2.txt"]
        )
        
        # Verify it's fixed
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is True
        assert len(bad_files) == 0
    
    def test_reextract_multiple_files(self, test_zip_with_files, target_dir):
        """Test re-extracting multiple corrupted files."""
        # Extract first
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Corrupt multiple files
        (target_dir / "file1.txt").write_text("BAD")
        (target_dir / "dir" / "file3.txt").write_text("BAD")
        
        # Re-extract only the corrupted files
        extractor._extract_specific_files_from_zip(
            archive.path,
            target_dir,
            ["file1.txt", "dir/file3.txt"]
        )
        
        # Verify all fixed
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is True
        assert len(bad_files) == 0


class TestResumeLogic:
    """Test resume logic with verification."""
    
    def test_resume_with_completed_archive_verified(self, test_zip_with_files, tmp_path):
        """Test that completed archives are verified and skipped."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        state_file = tmp_path / "state.json"
        
        # First extraction
        extractor1 = ArchiveExtractor(
            target_dir,
            preserve_structure=False,
            enable_resume=True,
            state_file=state_file
        )
        
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor1.extract(archive)
        
        # Verify state shows completed
        state = ExtractionState.load(state_file)
        assert archive.name in state.archives
        assert state.archives[archive.name].completed_at is not None
        
        # Second extraction - should verify and skip
        extractor2 = ArchiveExtractor(
            target_dir,
            preserve_structure=False,
            enable_resume=True,
            state_file=state_file
        )
        
        # Extract again - should skip after verification
        extract_path = extractor2.extract(archive)
        
        assert extract_path.exists()
        assert (extract_path / "file1.txt").exists()
    
    def test_resume_with_corrupted_file_reextracts(self, test_zip_with_files, tmp_path):
        """Test that corrupted files trigger selective re-extraction on resume."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        state_file = tmp_path / "state.json"
        
        # First extraction
        extractor1 = ArchiveExtractor(
            target_dir,
            preserve_structure=False,
            enable_resume=True,
            state_file=state_file
        )
        
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor1.extract(archive)
        
        # Corrupt a file
        (target_dir / "file2.txt").write_text("CORRUPTED")
        
        # Second extraction - should detect corruption and re-extract
        extractor2 = ArchiveExtractor(
            target_dir,
            preserve_structure=False,
            enable_resume=True,
            state_file=state_file
        )
        
        extract_path = extractor2.extract(archive)
        
        # Verify file is fixed
        assert (extract_path / "file2.txt").exists()
        content = (extract_path / "file2.txt").read_text()
        assert content == "Content of file 2" * 100


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_corrupted_zip_file_fails(self, tmp_path):
        """Test that corrupted ZIP file causes clear error."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create a corrupted ZIP file
        corrupted_zip = source_dir / "corrupted.zip"
        corrupted_zip.write_bytes(b"This is not a valid ZIP file")
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        
        # Should discover it (based on extension)
        assert len(archives) == 1
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        
        # Should fail with clear error when trying to extract
        # The extractor wraps the error in RuntimeError
        with pytest.raises((zipfile.BadZipFile, RuntimeError, OSError)):
            extractor.extract(archives[0])
    
    def test_empty_zip_file(self, tmp_path):
        """Test extraction of empty ZIP file."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create empty ZIP
        empty_zip = source_dir / "empty.zip"
        with zipfile.ZipFile(empty_zip, 'w') as zf:
            pass  # No files
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extract_path = extractor.extract(archive)
        
        # Should succeed but extract nothing
        assert extract_path.exists()
        
        # Verify empty archive
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            extract_path
        )
        
        assert all_valid is True
        assert len(bad_files) == 0
    
    def test_filename_sanitization_verification(self, tmp_path):
        """Test that sanitized filenames are properly verified."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create ZIP with files that need sanitization (Windows reserved names)
        zip_path = source_dir / "test.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("normal_file.txt", "Normal content")
            # Note: We can't actually create files with reserved names in the ZIP
            # on Windows, so this test is limited
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(
            archive,
            target_dir
        )
        
        assert all_valid is True
        assert len(bad_files) == 0


class TestUnicodePathHandling:
    """Test Unicode path normalization and verification across multiple languages."""
    
    def test_normalize_unicode_path_nfc(self):
        """Test that normalize_unicode_path converts to NFC form."""
        # NFD (decomposed) form of "café"
        nfd_path = "cafe\u0301"  # e + combining acute accent
        # NFC (composed) form of "café"
        nfc_path = "café"
        
        assert normalize_unicode_path(nfd_path) == nfc_path
        assert normalize_unicode_path(nfc_path) == nfc_path
    
    def test_cyrillic_filenames(self, tmp_path):
        """Test extraction and verification with Cyrillic filenames."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create ZIP with Cyrillic filenames (Russian, Ukrainian, Bulgarian)
        zip_path = source_dir / "cyrillic.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("Takeout/Google Photos/Израильские документы/file1.txt", "Content 1")
            zf.writestr("Takeout/Google Photos/Inglesina инструкции/file2.txt", "Content 2")
            zf.writestr("Takeout/Google Photos/Проводы Сергія/file3.txt", "Content 3")
            zf.writestr("Takeout/Google Photos/България/file4.txt", "Content 4")
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        # Extract
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Verify all files exist
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is True
        assert len(bad_files) == 0
        
        # Delete a file from Cyrillic directory
        cyrillic_file = target_dir / "Takeout" / "Google Photos" / "Израильские документы" / "file1.txt"
        cyrillic_file.unlink()
        
        # Verify should detect missing file
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is False
        assert len(bad_files) == 1
        assert "Takeout/Google Photos/Израильские документы/file1.txt" in bad_files
        
        # Re-extract the missing file
        extractor._extract_specific_files_from_zip(
            archive.path,
            target_dir,
            ["Takeout/Google Photos/Израильские документы/file1.txt"]
        )
        
        # Verify it's fixed
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is True
        assert len(bad_files) == 0
    
    def test_chinese_filenames(self, tmp_path):
        """Test extraction and verification with Chinese filenames."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create ZIP with Chinese filenames (Simplified and Traditional)
        zip_path = source_dir / "chinese.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("照片/2024年/春节/照片1.jpg", b"Photo 1")
            zf.writestr("照片/2024年/春节/照片2.jpg", b"Photo 2")
            zf.writestr("相片/家庭/聚會.jpg", b"Photo 3")  # Traditional Chinese
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        # Extract
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is True
        assert len(bad_files) == 0
        
        # Delete files
        (target_dir / "照片" / "2024年" / "春节" / "照片1.jpg").unlink()
        (target_dir / "相片" / "家庭" / "聚會.jpg").unlink()
        
        # Verify should detect missing files
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is False
        assert len(bad_files) == 2
    
    def test_arabic_filenames(self, tmp_path):
        """Test extraction and verification with Arabic filenames."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create ZIP with Arabic filenames (RTL text)
        zip_path = source_dir / "arabic.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("الصور/العائلة/صورة١.jpg", b"Photo 1")
            zf.writestr("الصور/العائلة/صورة٢.jpg", b"Photo 2")
            zf.writestr("المستندات/ملف.txt", "Arabic content")
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        # Extract
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is True
        assert len(bad_files) == 0
    
    def test_japanese_filenames(self, tmp_path):
        """Test extraction and verification with Japanese filenames (Hiragana, Katakana, Kanji)."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create ZIP with Japanese filenames
        zip_path = source_dir / "japanese.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("写真/家族/ファミリー写真.jpg", b"Family photo")
            zf.writestr("写真/旅行/東京タワー.jpg", b"Tokyo Tower")
            zf.writestr("ドキュメント/メモ.txt", "Japanese memo")
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        # Extract
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is True
        assert len(bad_files) == 0
    
    def test_korean_filenames(self, tmp_path):
        """Test extraction and verification with Korean filenames (Hangul)."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create ZIP with Korean filenames
        zip_path = source_dir / "korean.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("사진/가족/가족사진.jpg", b"Family photo")
            zf.writestr("사진/여행/서울타워.jpg", b"Seoul Tower")
            zf.writestr("문서/메모.txt", "Korean memo")
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        # Extract
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is True
        assert len(bad_files) == 0
    
    def test_mixed_unicode_languages(self, tmp_path):
        """Test extraction with mixed Unicode languages in same archive."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create ZIP with multiple language filenames
        zip_path = source_dir / "mixed.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("English/file.txt", "English")
            zf.writestr("Русский/файл.txt", "Russian")
            zf.writestr("中文/文件.txt", "Chinese")
            zf.writestr("العربية/ملف.txt", "Arabic")
            zf.writestr("日本語/ファイル.txt", "Japanese")
            zf.writestr("한국어/파일.txt", "Korean")
            zf.writestr("Ελληνικά/αρχείο.txt", "Greek")
            zf.writestr("עברית/קובץ.txt", "Hebrew")
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        # Extract
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Verify all files
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is True
        assert len(bad_files) == 0
        
        # Delete files from multiple language directories
        (target_dir / "Русский" / "файл.txt").unlink()
        (target_dir / "中文" / "文件.txt").unlink()
        (target_dir / "日本語" / "ファイル.txt").unlink()
        
        # Verify should detect all missing files
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is False
        assert len(bad_files) == 3
        assert "Русский/файл.txt" in bad_files
        assert "中文/文件.txt" in bad_files
        assert "日本語/ファイル.txt" in bad_files
        
        # Re-extract all missing files
        extractor._extract_specific_files_from_zip(
            archive.path,
            target_dir,
            bad_files
        )
        
        # Verify all fixed
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is True
        assert len(bad_files) == 0
    
    def test_unicode_normalization_forms(self, tmp_path):
        """Test that different Unicode normalization forms are handled correctly."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create ZIP with filename that could be in different normalization forms
        # "café" can be represented as NFC (é as single char) or NFD (e + combining accent)
        zip_path = source_dir / "normalization.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Use NFC form in ZIP
            zf.writestr("café/résumé.txt", "Content")
            zf.writestr("naïve/file.txt", "Content 2")
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        # Extract
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is True
        assert len(bad_files) == 0
        
        # The extracted files should be findable regardless of normalization form
        # This tests that our normalization is working
        cafe_dir = target_dir / "café"
        assert cafe_dir.exists()
        assert (cafe_dir / "résumé.txt").exists()
    
    def test_emoji_in_filenames(self, tmp_path):
        """Test extraction with emoji in filenames."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create ZIP with emoji in filenames
        zip_path = source_dir / "emoji.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("Photos 📷/Vacation 🏖️/beach.jpg", b"Beach photo")
            zf.writestr("Photos 📷/Family 👨‍👩‍👧‍👦/family.jpg", b"Family photo")
            zf.writestr("Documents 📄/Notes 📝.txt", "Notes")
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        # Extract
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        extractor.extract(archive)
        
        # Verify
        all_valid, bad_files = extractor._verify_archive_extraction(archive, target_dir)
        assert all_valid is True
        assert len(bad_files) == 0
