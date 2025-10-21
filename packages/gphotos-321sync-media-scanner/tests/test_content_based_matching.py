"""Tests for content-based sidecar matching."""

import json
import pytest
from pathlib import Path

from gphotos_321sync.media_scanner.discovery import FileInfo
from gphotos_321sync.media_scanner.parallel_scanner_helpers import (
    match_orphaned_sidecars,
    report_unmatched_files
)


def test_match_orphaned_sidecars_google_takeout_bug(tmp_path):
    """Test content-based matching for Google Takeout duplicate numbering bug.
    
    Bug: Sidecar has (1) suffix, but media file has 1(1) pattern.
    Example: Screenshot_...(1).json → Screenshot_...1(1).jpg
    """
    album = tmp_path / "Album"
    album.mkdir()
    
    # Create media file with Google Takeout bug pattern
    media_file = album / "Screenshot_2022-04-21-19-27-07-44_abb9c8060a0a1(1).jpg"
    media_file.write_text("fake screenshot")
    
    # Create sidecar with (1) suffix that doesn't match directly
    sidecar_file = album / "Screenshot_2022-04-21-19-27-07-44_abb9c8060a0a(1).json"
    sidecar_content = json.dumps({
        "title": "Screenshot_2022-04-21-19-27-07-44_abb9c8060a0a12c5ac89e934e52a2f4f.jpg",
        "photoTakenTime": {"timestamp": 1650558427}
    })
    sidecar_file.write_text(sidecar_content)
    
    # Create FileInfo for media file (without sidecar)
    file_info = FileInfo(
        file_path=media_file,
        relative_path=Path("Album") / media_file.name,
        album_folder_path=Path("Album"),
        json_sidecar_path=None,
        file_size=len("fake screenshot")
    )
    
    # Test content-based matching
    orphan_matches = match_orphaned_sidecars(
        target_media_path=tmp_path,
        paired_sidecars=set(),
        all_sidecars={sidecar_file},
        all_media_files=[file_info]
    )
    
    # Should find a match
    assert len(orphan_matches) == 1
    assert orphan_matches[0].file_path == media_file
    assert orphan_matches[0].json_sidecar_path == sidecar_file


def test_match_orphaned_sidecars_high_similarity(tmp_path):
    """Test content-based matching with high similarity threshold."""
    album = tmp_path / "Album"
    album.mkdir()
    
    # Create media file
    media_file = album / "photo_with_long_uuid_12345678.jpg"
    media_file.write_text("fake photo")
    
    # Create sidecar with similar but truncated name
    sidecar_file = album / "photo_with_long_uuid_1234.json"
    sidecar_content = json.dumps({
        "title": "photo_with_long_uuid_12345678_full_name.jpg",
        "photoTakenTime": {"timestamp": 1650558427}
    })
    sidecar_file.write_text(sidecar_content)
    
    file_info = FileInfo(
        file_path=media_file,
        relative_path=Path("Album") / media_file.name,
        album_folder_path=Path("Album"),
        json_sidecar_path=None,
        file_size=len("fake photo")
    )
    
    orphan_matches = match_orphaned_sidecars(
        target_media_path=tmp_path,
        paired_sidecars=set(),
        all_sidecars={sidecar_file},
        all_media_files=[file_info]
    )
    
    # Should match (similarity > 80%)
    assert len(orphan_matches) == 1
    assert orphan_matches[0].json_sidecar_path == sidecar_file


def test_match_orphaned_sidecars_low_similarity(tmp_path):
    """Test that low similarity files are not matched."""
    album = tmp_path / "Album"
    album.mkdir()
    
    # Create media file
    media_file = album / "completely_different_name.jpg"
    media_file.write_text("fake photo")
    
    # Create sidecar with very different name
    sidecar_file = album / "another_file.json"
    sidecar_content = json.dumps({
        "title": "another_file_original.jpg",
        "photoTakenTime": {"timestamp": 1650558427}
    })
    sidecar_file.write_text(sidecar_content)
    
    file_info = FileInfo(
        file_path=media_file,
        relative_path=Path("Album") / media_file.name,
        album_folder_path=Path("Album"),
        json_sidecar_path=None,
        file_size=len("fake photo")
    )
    
    orphan_matches = match_orphaned_sidecars(
        target_media_path=tmp_path,
        paired_sidecars=set(),
        all_sidecars={sidecar_file},
        all_media_files=[file_info]
    )
    
    # Should NOT match (similarity < 80%)
    assert len(orphan_matches) == 0


def test_match_orphaned_sidecars_skips_already_paired(tmp_path):
    """Test that files with existing sidecars are not re-paired."""
    album = tmp_path / "Album"
    album.mkdir()
    
    # Create media file with existing sidecar
    media_file = album / "photo.jpg"
    media_file.write_text("fake photo")
    existing_sidecar = album / "photo.jpg.supplemental-metadata.json"
    existing_sidecar.write_text('{"title": "photo.jpg"}')
    
    # Create orphaned sidecar
    orphan_sidecar = album / "photo(1).json"
    orphan_sidecar.write_text(json.dumps({"title": "photo_original.jpg"}))
    
    file_info = FileInfo(
        file_path=media_file,
        relative_path=Path("Album") / media_file.name,
        album_folder_path=Path("Album"),
        json_sidecar_path=existing_sidecar,  # Already has sidecar
        file_size=len("fake photo")
    )
    
    orphan_matches = match_orphaned_sidecars(
        target_media_path=tmp_path,
        paired_sidecars={existing_sidecar},
        all_sidecars={existing_sidecar, orphan_sidecar},
        all_media_files=[file_info]
    )
    
    # Should NOT match (file already has sidecar)
    assert len(orphan_matches) == 0


def test_match_orphaned_sidecars_skips_system_files(tmp_path):
    """Test that system JSON files are skipped."""
    # Create system files
    (tmp_path / "print-subscriptions.json").write_text('{}')
    (tmp_path / "shared_album_comments.json").write_text('{}')
    (tmp_path / "user-generated-memory-titles.json").write_text('{}')
    
    system_files = {
        tmp_path / "print-subscriptions.json",
        tmp_path / "shared_album_comments.json",
        tmp_path / "user-generated-memory-titles.json"
    }
    
    orphan_matches = match_orphaned_sidecars(
        target_media_path=tmp_path,
        paired_sidecars=set(),
        all_sidecars=system_files,
        all_media_files=[]
    )
    
    # Should skip all system files
    assert len(orphan_matches) == 0


def test_report_unmatched_files_orphaned_sidecars(tmp_path, caplog):
    """Test reporting of orphaned media sidecars."""
    import logging
    caplog.set_level(logging.WARNING)
    
    album = tmp_path / "Album"
    album.mkdir()
    
    # Create orphaned sidecar (no matching media)
    orphan_sidecar = album / "orphaned.jpg.json"
    orphan_sidecar.write_text(json.dumps({"title": "orphaned.jpg"}))
    
    report_unmatched_files(
        scan_root=tmp_path,
        all_sidecars={orphan_sidecar},
        paired_sidecars=set(),
        all_media_files=[]
    )
    
    # Check that orphan was logged with structured data
    assert any("Orphaned media sidecars" in record.message for record in caplog.records)
    # Check structured logging extra fields
    orphan_records = [r for r in caplog.records if "Orphaned media sidecars" in r.message]
    assert len(orphan_records) == 1
    assert orphan_records[0].count == 1
    assert "orphaned.jpg.json" in orphan_records[0].sample_files[0]


def test_report_unmatched_files_system_files(tmp_path, caplog):
    """Test reporting of system JSON files."""
    import logging
    caplog.set_level(logging.INFO)
    
    # Create system file
    system_file = tmp_path / "print-subscriptions.json"
    system_file.write_text('{}')
    
    report_unmatched_files(
        scan_root=tmp_path,
        all_sidecars={system_file},
        paired_sidecars=set(),
        all_media_files=[]
    )
    
    # Check that system file was logged with structured data
    assert any("System JSON files" in record.message for record in caplog.records)
    # Check structured logging extra fields
    system_records = [r for r in caplog.records if "System JSON files" in r.message]
    assert len(system_records) == 1
    assert system_records[0].count == 1
    assert "print-subscriptions.json" in system_records[0].files


def test_report_unmatched_files_media_without_sidecars(tmp_path, caplog):
    """Test reporting of media files without sidecars."""
    import logging
    caplog.set_level(logging.INFO)
    
    album = tmp_path / "Album"
    album.mkdir()
    
    # Create media file without sidecar
    media_file = album / "no_sidecar.jpg"
    media_file.write_text("fake photo")
    
    file_info = FileInfo(
        file_path=media_file,
        relative_path=Path("Album") / media_file.name,
        album_folder_path=Path("Album"),
        json_sidecar_path=None,
        file_size=len("fake photo")
    )
    
    report_unmatched_files(
        scan_root=tmp_path,
        all_sidecars=set(),
        paired_sidecars=set(),
        all_media_files=[file_info]
    )
    
    # Check that media without sidecar was logged
    assert any("Media files without sidecars" in record.message for record in caplog.records)


def test_report_unmatched_files_all_matched(tmp_path, caplog):
    """Test that no warnings are logged when all files are matched."""
    import logging
    caplog.set_level(logging.INFO)
    
    album = tmp_path / "Album"
    album.mkdir()
    
    # Create matched pair
    media_file = album / "photo.jpg"
    media_file.write_text("fake photo")
    sidecar_file = album / "photo.jpg.json"
    sidecar_file.write_text('{"title": "photo.jpg"}')
    
    file_info = FileInfo(
        file_path=media_file,
        relative_path=Path("Album") / media_file.name,
        album_folder_path=Path("Album"),
        json_sidecar_path=sidecar_file,
        file_size=len("fake photo")
    )
    
    report_unmatched_files(
        scan_root=tmp_path,
        all_sidecars={sidecar_file},
        paired_sidecars={sidecar_file},
        all_media_files=[file_info]
    )
    
    # Check that success message was logged
    assert any("All files successfully matched" in record.message for record in caplog.records)
