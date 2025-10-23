"""Tests for file discovery module."""

import pytest
from pathlib import Path
from gphotos_321sync.media_scanner.discovery import discover_files, FileInfo


@pytest.fixture
def test_tree(tmp_path):
    """Create a test directory tree with media files and sidecars."""
    # Create directory structure
    album1 = tmp_path / "Album 1"
    album1.mkdir()
    
    album2 = tmp_path / "Album 2"
    album2.mkdir()
    
    nested = tmp_path / "Year 2023" / "Vacation"
    nested.mkdir(parents=True)
    
    # Create media files
    (album1 / "photo1.jpg").write_text("fake jpeg")
    (album1 / "photo2.png").write_text("fake png")
    (album1 / "video1.mp4").write_text("fake video")
    
    (album2 / "photo3.jpg").write_text("fake jpeg")
    
    (nested / "photo4.heic").write_text("fake heic")
    (nested / "video2.mov").write_text("fake mov")
    
    # Create JSON sidecars (Google Takeout pattern: .supplemental-metadata.json)
    (album1 / "photo1.jpg.supplemental-metadata.json").write_text('{"title": "Photo 1"}')
    (album1 / "video1.mp4.supplemental-metadata.json").write_text('{"title": "Video 1"}')
    (nested / "photo4.heic.supplemental-metadata.json").write_text('{"title": "Photo 4"}')
    
    # Create album metadata (should be ignored)
    (album1 / "metadata.json").write_text('{"title": "Album 1"}')
    
    # Create hidden file (should be scanned - may be valid media)
    (album1 / ".hidden.jpg").write_text("hidden")
    (album1 / ".hidden.jpg.supplemental-metadata.json").write_text('{"title": "Hidden"}')
    
    # Create system file (should be ignored on Windows)
    thumbs = album2 / "Thumbs.db"
    thumbs.write_text("thumbs")
    
    return tmp_path


def test_discover_files_basic(test_tree):
    """Test basic file discovery."""
    files = list(discover_files(test_tree))
    
    # Should find 7 media files (including .hidden.jpg, excluding Thumbs.db)
    assert len(files) >= 7
    
    # Check that all returned items are FileInfo objects
    for file_info in files:
        assert isinstance(file_info, FileInfo)
        assert file_info.file_path.exists()
        assert file_info.file_size > 0


def test_discover_files_sidecar_pairing(test_tree):
    """Test that JSON sidecars are correctly paired with media files."""
    files = {f.file_path.name: f for f in discover_files(test_tree)}
    
    # Files with sidecars (Google Takeout pattern)
    assert files["photo1.jpg"].json_sidecar_path is not None
    assert files["photo1.jpg"].json_sidecar_path.name == "photo1.jpg.supplemental-metadata.json"
    
    assert files["video1.mp4"].json_sidecar_path is not None
    assert files["video1.mp4"].json_sidecar_path.name == "video1.mp4.supplemental-metadata.json"
    
    assert files["photo4.heic"].json_sidecar_path is not None
    assert files["photo4.heic"].json_sidecar_path.name == "photo4.heic.supplemental-metadata.json"
    
    # Files without sidecars
    assert files["photo2.png"].json_sidecar_path is None
    assert files["photo3.jpg"].json_sidecar_path is None
    assert files["video2.mov"].json_sidecar_path is None


def test_discover_files_relative_paths(test_tree):
    """Test that relative paths are calculated correctly."""
    files = list(discover_files(test_tree))
    
    for file_info in files:
        # Relative path should be relative to test_tree
        assert not file_info.relative_path.is_absolute()
        
        # Should be able to reconstruct absolute path
        reconstructed = test_tree / file_info.relative_path
        assert reconstructed == file_info.file_path


def test_discover_files_album_folder(test_tree):
    """Test that album folder path is correctly identified."""
    files = {f.file_path.name: f for f in discover_files(test_tree)}
    
    # Files in Album 1
    assert files["photo1.jpg"].album_folder_path == Path("Album 1")
    assert files["photo2.png"].album_folder_path == Path("Album 1")
    
    # Files in Album 2
    assert files["photo3.jpg"].album_folder_path == Path("Album 2")
    
    # Files in nested folder
    assert files["photo4.heic"].album_folder_path == Path("Year 2023") / "Vacation"


def test_discover_files_excludes_json(test_tree):
    """Test that JSON files are not included in results."""
    files = list(discover_files(test_tree))
    
    # No JSON files should be in results
    for file_info in files:
        assert file_info.file_path.suffix.lower() != ".json"


def test_discover_files_includes_hidden(test_tree):
    """Test that hidden files are included (may be valid media)."""
    files = [f.file_path.name for f in discover_files(test_tree)]
    
    # Hidden file should be in results (may be valid media file)
    assert ".hidden.jpg" in files


def test_discover_files_empty_directory(tmp_path):
    """Test discovery in empty directory returns empty list."""
    files = list(discover_files(tmp_path))
    assert len(files) == 0


def test_discover_files_nonexistent_path(tmp_path):
    """Test discovery with non-existent path."""
    nonexistent = tmp_path / "does_not_exist"
    files = list(discover_files(nonexistent))
    assert len(files) == 0


def test_discover_files_file_not_directory(tmp_path):
    """Test discovery when path is a file, not directory."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("test")
    
    files = list(discover_files(file_path))
    assert len(files) == 0


def test_discover_files_no_extension(test_tree):
    """Test that files without extensions are discovered."""
    # Create file without extension
    no_ext = test_tree / "Album 1" / "photo_no_ext"
    no_ext.write_text("fake image")
    
    files = [f.file_path.name for f in discover_files(test_tree)]
    
    # File without extension should be discovered
    assert "photo_no_ext" in files


def test_discover_files_wrong_extension(test_tree):
    """Test that files with wrong extensions are discovered."""
    # Create JPEG with .txt extension (MIME detection will determine actual type)
    wrong_ext = test_tree / "Album 1" / "image.txt"
    wrong_ext.write_text("fake jpeg data")
    
    files = [f.file_path.name for f in discover_files(test_tree)]
    
    # File with wrong extension should be discovered
    assert "image.txt" in files


def test_discover_files_file_size(test_tree):
    """Test that file sizes are correctly captured."""
    files = {f.file_path.name: f for f in discover_files(test_tree)}
    
    # All files should have non-zero size
    for file_info in files.values():
        assert file_info.file_size > 0
    
    # Check specific file
    photo1_size = (test_tree / "Album 1" / "photo1.jpg").stat().st_size
    assert files["photo1.jpg"].file_size == photo1_size


def test_discover_files_large_tree(tmp_path):
    """Test discovery with larger directory tree."""
    # Create multiple albums with files
    for i in range(10):
        album = tmp_path / f"Album {i}"
        album.mkdir()
        
        for j in range(5):
            (album / f"photo{j}.jpg").write_text(f"photo {i}-{j}")
            if j % 2 == 0:
                (album / f"photo{j}.jpg.supplemental-metadata.json").write_text(f'{{"title": "Photo {i}-{j}"}}')
    
    files = list(discover_files(tmp_path))
    
    # Should find 50 files (10 albums × 5 photos)
    assert len(files) == 50
    
    # Should find 30 sidecars (10 albums × 3 sidecars, for even-numbered photos)
    files_with_sidecars = sum(1 for f in files if f.json_sidecar_path is not None)
    assert files_with_sidecars == 30


def test_discover_files_truncated_sidecar_patterns(tmp_path):
    """Test discovery of truncated sidecar filename patterns."""
    album = tmp_path / "Album"
    album.mkdir()
    
    # Create media files with various truncated sidecar patterns
    (album / "photo1.jpg").write_text("fake jpeg")
    (album / "photo1.jpg.supplemen.json").write_text('{"title": "Photo 1"}')
    
    (album / "photo2.jpg").write_text("fake jpeg")
    (album / "photo2.jpg.suppl.json").write_text('{"title": "Photo 2"}')
    
    (album / "photo3.jpg").write_text("fake jpeg")
    (album / "photo3.jpg.supplemental-metadat.json").write_text('{"title": "Photo 3"}')
    
    (album / "photo4.jpg").write_text("fake jpeg")
    (album / "photo4.jpg.supplemental-metad.json").write_text('{"title": "Photo 4"}')
    
    (album / "photo5.jpg").write_text("fake jpeg")
    (album / "photo5.jpg.supplemental-me.json").write_text('{"title": "Photo 5"}')
    
    files = {f.file_path.name: f for f in discover_files(tmp_path)}
    
    # All photos should be paired with their truncated sidecars
    assert files["photo1.jpg"].json_sidecar_path is not None
    assert files["photo1.jpg"].json_sidecar_path.name == "photo1.jpg.supplemen.json"
    
    assert files["photo2.jpg"].json_sidecar_path is not None
    assert files["photo2.jpg"].json_sidecar_path.name == "photo2.jpg.suppl.json"
    
    assert files["photo3.jpg"].json_sidecar_path is not None
    assert files["photo3.jpg"].json_sidecar_path.name == "photo3.jpg.supplemental-metadat.json"
    
    assert files["photo4.jpg"].json_sidecar_path is not None
    assert files["photo4.jpg"].json_sidecar_path.name == "photo4.jpg.supplemental-metad.json"
    
    assert files["photo5.jpg"].json_sidecar_path is not None
    assert files["photo5.jpg"].json_sidecar_path.name == "photo5.jpg.supplemental-me.json"


def test_discover_files_tilde_duplicates(tmp_path):
    """Test discovery of files with tilde suffix duplicates."""
    album = tmp_path / "Album"
    album.mkdir()
    
    # Create original file with sidecar
    (album / "IMG20240221145914.jpg").write_text("fake jpeg")
    (album / "IMG20240221145914.jpg.supplemental-metadata.json").write_text('{"title": "Original"}')
    
    # Create tilde duplicates (may or may not have their own sidecars)
    (album / "IMG20240221145914~2.jpg").write_text("fake jpeg duplicate")
    (album / "IMG20240221145914~3.jpg").write_text("fake jpeg duplicate")
    
    # Create another file with tilde duplicate that has its own sidecar
    (album / "VID20240523214231.mp4").write_text("fake video")
    (album / "VID20240523214231.mp4.supplemental-metadata.json").write_text('{"title": "Video Original"}')
    (album / "VID20240523214231~2.mp4").write_text("fake video duplicate")
    (album / "VID20240523214231~2.mp4.supplemental-metadata.json").write_text('{"title": "Video Duplicate"}')
    
    files = {f.file_path.name: f for f in discover_files(tmp_path)}
    
    # Original should have sidecar
    assert files["IMG20240221145914.jpg"].json_sidecar_path is not None
    assert files["IMG20240221145914.jpg"].json_sidecar_path.name == "IMG20240221145914.jpg.supplemental-metadata.json"
    
    # Tilde duplicates should fall back to original's sidecar
    assert files["IMG20240221145914~2.jpg"].json_sidecar_path is not None
    assert files["IMG20240221145914~2.jpg"].json_sidecar_path.name == "IMG20240221145914.jpg.supplemental-metadata.json"
    
    assert files["IMG20240221145914~3.jpg"].json_sidecar_path is not None
    assert files["IMG20240221145914~3.jpg"].json_sidecar_path.name == "IMG20240221145914.jpg.supplemental-metadata.json"
    
    # Video duplicate with its own sidecar should use that
    assert files["VID20240523214231~2.mp4"].json_sidecar_path is not None
    assert files["VID20240523214231~2.mp4"].json_sidecar_path.name == "VID20240523214231~2.mp4.supplemental-metadata.json"


def test_discover_files_alternative_json_pattern(tmp_path):
    """Test discovery of .json pattern with truncated sidecar filenames."""
    album = tmp_path / "Album"
    album.mkdir()
    
    # Create files with alternative .json pattern (used for long filenames)
    # When full path exceeds MAX_PATH, Windows truncates the sidecar filename itself
    # Pattern: photo_with_very_long_name.jpg → photo_with_very_long.json (truncated)
    (album / "Screenshot_2024-01-14-14-13-33-16_948cd9899890cbd5c2798760b2b95377.jpg").write_text("fake screenshot")
    (album / "Screenshot_2024-01-14-14-13-33-16_948cd9899890.json").write_text('{"title": "Screenshot"}')
    
    (album / "original_0eb58adf-59c4-46d2-9420-73d42f7c8e88_FB_IMG_1713377637724.jpg").write_text("fake image")
    (album / "original_0eb58adf-59c4-46d2-9420-73d42f7c8e88_.json").write_text('{"title": "FB Image"}')
    
    files = {f.file_path.name: f for f in discover_files(tmp_path)}
    
    # Files should be paired with truncated .json sidecars (prefix match)
    assert files["Screenshot_2024-01-14-14-13-33-16_948cd9899890cbd5c2798760b2b95377.jpg"].json_sidecar_path is not None
    assert files["Screenshot_2024-01-14-14-13-33-16_948cd9899890cbd5c2798760b2b95377.jpg"].json_sidecar_path.name == "Screenshot_2024-01-14-14-13-33-16_948cd9899890.json"
    
    assert files["original_0eb58adf-59c4-46d2-9420-73d42f7c8e88_FB_IMG_1713377637724.jpg"].json_sidecar_path is not None
    assert files["original_0eb58adf-59c4-46d2-9420-73d42f7c8e88_FB_IMG_1713377637724.jpg"].json_sidecar_path.name == "original_0eb58adf-59c4-46d2-9420-73d42f7c8e88_.json"


def test_discover_files_duplicate_numbered_suffix(tmp_path):
    """Test discovery of files with duplicate numbered suffix (N) pattern.
    
    Google Takeout exports may contain files with (1), (2), etc. suffixes
    for duplicate files.
    For sidecars: filename.ext.supplemental-metadata(1).json
    For media: filename(1).ext
    """
    album = tmp_path / "Album"
    album.mkdir()
    
    # Create original files
    (album / "image.png").write_text("fake png")
    (album / "image.png.supplemental-metadata.json").write_text('{"title": "Image"}')
    
    # Create duplicate files with (1) suffix
    (album / "image(1).png").write_text("fake png duplicate")
    (album / "image.png.supplemental-metadata(1).json").write_text('{"title": "Image Duplicate"}')
    
    # Create files with (2) suffix
    (album / "photo(2).jpg").write_text("fake jpeg")
    (album / "photo.jpg.supplemental-metadata(2).json").write_text('{"title": "Photo 2"}')
    
    # Create files with truncated sidecar and duplicate suffix
    (album / "Screenshot_20211104-110347(1).jpg").write_text("fake screenshot")
    (album / "Screenshot_20211104-110347.jpg.supplemental-me(1).json").write_text('{"title": "Screenshot"}')
    
    files = {f.file_path.name: f for f in discover_files(tmp_path)}
    
    # Original files should be paired
    assert files["image.png"].json_sidecar_path is not None
    assert files["image.png"].json_sidecar_path.name == "image.png.supplemental-metadata.json"
    
    # Duplicate files with (1) suffix should be paired with their (1) sidecars
    assert files["image(1).png"].json_sidecar_path is not None
    assert files["image(1).png"].json_sidecar_path.name == "image.png.supplemental-metadata(1).json"
    
    # Files with (2) suffix should be paired
    assert files["photo(2).jpg"].json_sidecar_path is not None
    assert files["photo(2).jpg"].json_sidecar_path.name == "photo.jpg.supplemental-metadata(2).json"
    
    # Truncated sidecar with duplicate suffix should be paired
    assert files["Screenshot_20211104-110347(1).jpg"].json_sidecar_path is not None
    assert files["Screenshot_20211104-110347(1).jpg"].json_sidecar_path.name == "Screenshot_20211104-110347.jpg.supplemental-me(1).json"


def test_discover_files_no_extension_with_duplicate_suffix(tmp_path):
    """Test that sidecars with no extension in base name are correctly paired with numbered media files."""
    # Create media files with various base names without extensions
    # [UNSET] is one example, but this works for any filename pattern
    (tmp_path / "[UNSET](1).jpg").write_text("fake jpeg 1")
    (tmp_path / "[UNSET](2).jpg").write_text("fake jpeg 2")
    (tmp_path / "[Some Name](1).png").write_text("fake png")
    
    # Create corresponding sidecars (base name has no extension)
    (tmp_path / "[UNSET].supplemental-metadata(1).json").write_text('{"title": "UNSET 1"}')
    (tmp_path / "[UNSET].supplemental-metadata(2).json").write_text('{"title": "UNSET 2"}')
    (tmp_path / "[Some Name].supplemental-metadata(1).json").write_text('{"title": "Some Name"}')
    
    files = {f.file_path.name: f for f in discover_files(tmp_path)}
    
    # All files should be paired with their sidecars via extension guessing
    assert files["[UNSET](1).jpg"].json_sidecar_path is not None
    assert files["[UNSET](1).jpg"].json_sidecar_path.name == "[UNSET].supplemental-metadata(1).json"
    
    assert files["[UNSET](2).jpg"].json_sidecar_path is not None
    assert files["[UNSET](2).jpg"].json_sidecar_path.name == "[UNSET].supplemental-metadata(2).json"
    
    assert files["[Some Name](1).png"].json_sidecar_path is not None
    assert files["[Some Name](1).png"].json_sidecar_path.name == "[Some Name].supplemental-metadata(1).json"


def test_discover_files_numbered_without_extension(tmp_path):
    """Test that sidecars for numbered files without extensions are matched via heuristic."""
    # Create media files with extensions
    (tmp_path / "04.03.12 - 10.jpg").write_text("fake jpeg")
    (tmp_path / "18.03.12 - 1.jpg").write_text("fake jpeg")
    
    # Create sidecars that don't include the extension in the name
    (tmp_path / "04.03.12 - 10.supplemental-metadata.json").write_text('{"title": "Photo 10"}')
    (tmp_path / "18.03.12 - 1.supplemental-metadata.json").write_text('{"title": "Photo 1"}')
    
    files = {f.file_path.name: f for f in discover_files(tmp_path)}
    
    # Files should be paired via extension guessing heuristic
    assert files["04.03.12 - 10.jpg"].json_sidecar_path is not None
    assert files["04.03.12 - 10.jpg"].json_sidecar_path.name == "04.03.12 - 10.supplemental-metadata.json"
    
    assert files["18.03.12 - 1.jpg"].json_sidecar_path is not None
    assert files["18.03.12 - 1.jpg"].json_sidecar_path.name == "18.03.12 - 1.supplemental-metadata.json"


def test_discover_files_duplicate_without_supplemental(tmp_path):
    """Test that duplicate sidecars without supplemental-metadata pattern are matched."""
    # Create media files
    (tmp_path / "Screenshot_2022-04-21.jpg").write_text("fake screenshot")
    
    # Create duplicate sidecar without supplemental-metadata pattern
    (tmp_path / "Screenshot_2022-04-21(1).json").write_text('{"title": "Screenshot"}')
    
    files = {f.file_path.name: f for f in discover_files(tmp_path)}
    
    # File should be paired via duplicate_without_supplemental heuristic
    assert files["Screenshot_2022-04-21.jpg"].json_sidecar_path is not None
    assert files["Screenshot_2022-04-21.jpg"].json_sidecar_path.name == "Screenshot_2022-04-21(1).json"


def test_discover_files_hidden_media(tmp_path):
    """Test that hidden media files (starting with .) are discovered."""
    # Create hidden media file (e.g., from Google Takeout)
    (tmp_path / ".facebook_865716343.jpg").write_text("fake jpeg")
    (tmp_path / ".facebook_865716343.jpg.supplemental-metadata.json").write_text('{"title": "Facebook"}')
    
    files = {f.file_path.name: f for f in discover_files(tmp_path)}
    
    # Hidden file should be discovered and paired
    assert ".facebook_865716343.jpg" in files
    assert files[".facebook_865716343.jpg"].json_sidecar_path is not None
    assert files[".facebook_865716343.jpg"].json_sidecar_path.name == ".facebook_865716343.jpg.supplemental-metadata.json"
