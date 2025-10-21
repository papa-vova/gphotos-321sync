"""Tests for changed file detection and tracking."""

import hashlib
import pytest
from pathlib import Path
from datetime import datetime, timezone

from gphotos_321sync.media_scanner.database import DatabaseConnection
from gphotos_321sync.media_scanner.dal.scan_runs import ScanRunDAL
from gphotos_321sync.media_scanner.dal.media_items import MediaItemDAL
from gphotos_321sync.media_scanner.dal.albums import AlbumDAL
from gphotos_321sync.media_scanner.metadata_coordinator import MediaItemRecord
from gphotos_321sync.media_scanner.fingerprint import compute_content_fingerprint


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with schema."""
    from gphotos_321sync.media_scanner.migrations import MigrationRunner
    
    db_path = tmp_path / "test.db"
    db_conn = DatabaseConnection(db_path)
    
    # Apply migrations to create schema
    schema_dir = Path(__file__).parent.parent / "src" / "gphotos_321sync" / "media_scanner" / "schema"
    runner = MigrationRunner(db_conn, schema_dir)
    runner.apply_migrations()
    
    conn = db_conn.connect()
    yield conn, db_path
    conn.close()


def create_test_file(path: Path, content: str):
    """Create a test file with given content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_media_item_record(
    media_item_id: str,
    relative_path: str,
    album_id: str,
    file_size: int,
    content_fingerprint: str,
    scan_run_id: str,
    sidecar_fingerprint: str = None,
) -> MediaItemRecord:
    """Create a MediaItemRecord for testing."""
    return MediaItemRecord(
        media_item_id=media_item_id,
        relative_path=relative_path,
        album_id=album_id,
        title=None,
        mime_type="image/jpeg",
        file_size=file_size,
        crc32=None,
        content_fingerprint=content_fingerprint,
        sidecar_fingerprint=sidecar_fingerprint,
        width=None,
        height=None,
        duration_seconds=None,
        frame_rate=None,
        capture_timestamp=None,
        scan_run_id=scan_run_id,
        status="present",
        exif_datetime_original=None,
        exif_datetime_digitized=None,
        exif_gps_latitude=None,
        exif_gps_longitude=None,
        exif_gps_altitude=None,
        exif_camera_make=None,
        exif_camera_model=None,
        exif_lens_make=None,
        exif_lens_model=None,
        exif_focal_length=None,
        exif_f_number=None,
        exif_exposure_time=None,
        exif_iso=None,
        exif_orientation=None,
        google_description=None,
        google_geo_latitude=None,
        google_geo_longitude=None,
        google_geo_altitude=None,
    )


def test_unchanged_file_detection(test_db, tmp_path):
    """Test that unchanged files are correctly detected."""
    conn, db_path = test_db
    
    # Create DALs
    scan_run_dal = ScanRunDAL(conn)
    media_dal = MediaItemDAL(conn)
    album_dal = AlbumDAL(conn)
    
    # Create album
    album_id = "test-album-id"
    album_dal.upsert_album({
        'album_id': album_id,
        'album_folder_path': "Test Album",
        'scan_run_id': "scan1",
    })
    
    # Create test file
    test_file = create_test_file(tmp_path / "photo.jpg", "original content")
    fingerprint = compute_content_fingerprint(test_file, test_file.stat().st_size)
    
    # First scan - insert file
    scan_run_id_1 = scan_run_dal.create_scan_run()
    record = create_media_item_record(
        media_item_id="item1",
        relative_path="Test Album/photo.jpg",
        album_id=album_id,
        file_size=test_file.stat().st_size,
        content_fingerprint=fingerprint,
        scan_run_id=scan_run_id_1,
    )
    media_dal.insert_media_item(record)
    conn.commit()
    
    # Second scan - check if unchanged
    is_unchanged = media_dal.check_file_unchanged(
        "Test Album/photo.jpg",
        fingerprint,
        None
    )
    
    assert is_unchanged is True


def test_changed_file_detection(test_db, tmp_path):
    """Test that changed files are correctly detected."""
    conn, db_path = test_db
    
    # Create DALs
    scan_run_dal = ScanRunDAL(conn)
    media_dal = MediaItemDAL(conn)
    album_dal = AlbumDAL(conn)
    
    # Create album
    album_id = "test-album-id"
    album_dal.upsert_album({
        'album_id': album_id,
        'album_folder_path': "Test Album",
        'scan_run_id': "scan1",
    })
    
    # Create test file
    test_file = create_test_file(tmp_path / "photo.jpg", "original content")
    fingerprint_1 = compute_content_fingerprint(test_file, test_file.stat().st_size)
    
    # First scan - insert file
    scan_run_id_1 = scan_run_dal.create_scan_run()
    record = create_media_item_record(
        media_item_id="item1",
        relative_path="Test Album/photo.jpg",
        album_id=album_id,
        file_size=test_file.stat().st_size,
        content_fingerprint=fingerprint_1,
        scan_run_id=scan_run_id_1,
    )
    media_dal.insert_media_item(record)
    conn.commit()
    
    # Modify file
    test_file.write_text("modified content")
    fingerprint_2 = compute_content_fingerprint(test_file, test_file.stat().st_size)
    
    # Second scan - check if changed
    is_unchanged = media_dal.check_file_unchanged(
        "Test Album/photo.jpg",
        fingerprint_2,
        None
    )
    
    assert is_unchanged is False
    assert fingerprint_1 != fingerprint_2


def test_changed_file_with_sidecar(test_db, tmp_path):
    """Test that changes to sidecar are detected."""
    conn, db_path = test_db
    
    # Create DALs
    scan_run_dal = ScanRunDAL(conn)
    media_dal = MediaItemDAL(conn)
    album_dal = AlbumDAL(conn)
    
    # Create album
    album_id = "test-album-id"
    album_dal.upsert_album({
        'album_id': album_id,
        'album_folder_path': "Test Album",
        'scan_run_id': "scan1",
    })
    
    # Create test file and sidecar
    test_file = create_test_file(tmp_path / "photo.jpg", "photo content")
    sidecar_file = create_test_file(tmp_path / "photo.jpg.json", '{"title": "Original"}')
    
    content_fp = compute_content_fingerprint(test_file, test_file.stat().st_size)
    with open(sidecar_file, 'rb') as f:
        sidecar_fp_1 = hashlib.sha256(f.read()).hexdigest()
    
    # First scan - insert file
    scan_run_id_1 = scan_run_dal.create_scan_run()
    record = create_media_item_record(
        media_item_id="item1",
        relative_path="Test Album/photo.jpg",
        album_id=album_id,
        file_size=test_file.stat().st_size,
        content_fingerprint=content_fp,
        sidecar_fingerprint=sidecar_fp_1,
        scan_run_id=scan_run_id_1,
    )
    media_dal.insert_media_item(record)
    conn.commit()
    
    # Modify sidecar only
    sidecar_file.write_text('{"title": "Modified"}')
    with open(sidecar_file, 'rb') as f:
        sidecar_fp_2 = hashlib.sha256(f.read()).hexdigest()
    
    # Second scan - should detect change
    is_unchanged = media_dal.check_file_unchanged(
        "Test Album/photo.jpg",
        content_fp,  # Content unchanged
        sidecar_fp_2  # Sidecar changed
    )
    
    assert is_unchanged is False
    assert sidecar_fp_1 != sidecar_fp_2


def test_changed_file_update(test_db, tmp_path):
    """Test that changed files can be updated in database."""
    conn, db_path = test_db
    
    # Create DALs
    scan_run_dal = ScanRunDAL(conn)
    media_dal = MediaItemDAL(conn)
    album_dal = AlbumDAL(conn)
    
    # Create album
    album_id = "test-album-id"
    album_dal.upsert_album({
        'album_id': album_id,
        'album_folder_path': "Test Album",
        'scan_run_id': "scan1",
    })
    
    # Create test file
    test_file = create_test_file(tmp_path / "photo.jpg", "original content")
    fingerprint_1 = compute_content_fingerprint(test_file, test_file.stat().st_size)
    
    # First scan - insert file
    scan_run_id_1 = scan_run_dal.create_scan_run()
    record_1 = create_media_item_record(
        media_item_id="item1",
        relative_path="Test Album/photo.jpg",
        album_id=album_id,
        file_size=test_file.stat().st_size,
        content_fingerprint=fingerprint_1,
        scan_run_id=scan_run_id_1,
    )
    media_dal.insert_media_item(record_1)
    conn.commit()
    
    # Verify initial state
    item = media_dal.get_media_item_by_path("Test Album/photo.jpg")
    assert item['content_fingerprint'] == fingerprint_1
    assert item['scan_run_id'] == scan_run_id_1
    
    # Modify file
    test_file.write_text("modified content - much longer")
    fingerprint_2 = compute_content_fingerprint(test_file, test_file.stat().st_size)
    
    # Second scan - update file
    scan_run_id_2 = scan_run_dal.create_scan_run()
    
    # Simulate what writer_thread does for changed files
    conn.execute("DELETE FROM media_items WHERE relative_path = ?", ("Test Album/photo.jpg",))
    record_2 = create_media_item_record(
        media_item_id="item1",
        relative_path="Test Album/photo.jpg",
        album_id=album_id,
        file_size=test_file.stat().st_size,
        content_fingerprint=fingerprint_2,
        scan_run_id=scan_run_id_2,
    )
    media_dal.insert_media_item(record_2)
    conn.commit()
    
    # Verify updated state
    item = media_dal.get_media_item_by_path("Test Album/photo.jpg")
    assert item['content_fingerprint'] == fingerprint_2
    assert item['scan_run_id'] == scan_run_id_2
    assert item['file_size'] == test_file.stat().st_size


def test_new_file_detection(test_db):
    """Test that new files are correctly identified."""
    conn, db_path = test_db
    
    media_dal = MediaItemDAL(conn)
    
    # Check non-existent file
    existing_item = media_dal.get_media_item_by_path("Test Album/new_photo.jpg")
    
    assert existing_item is None
