"""Tests for database connection and basic operations."""

import pytest
import tempfile
from pathlib import Path

from gphotos_321sync.media_scanner.database import DatabaseConnection
from gphotos_321sync.media_scanner.migrations import MigrationRunner
from gphotos_321sync.media_scanner.dal import ScanRunDAL, AlbumDAL, MediaItemDAL, ProcessingErrorDAL


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


@pytest.fixture
def db_connection(temp_db):
    """Create a database connection."""
    db = DatabaseConnection(temp_db)
    db.connect()
    yield db
    db.close()


@pytest.fixture
def migrated_db(db_connection):
    """Create a database with migrations applied."""
    schema_dir = Path(__file__).parent.parent / "src" / "gphotos_321sync" / "media_scanner" / "schema"
    runner = MigrationRunner(db_connection, schema_dir)
    runner.apply_migrations()
    return db_connection


def test_database_connection(temp_db):
    """Test database connection creation."""
    db = DatabaseConnection(temp_db)
    conn = db.connect()
    assert conn is not None
    assert temp_db.exists()
    db.close()


def test_database_pragmas(db_connection):
    """Test that PRAGMAs are applied correctly."""
    cursor = db_connection.execute("PRAGMA journal_mode")
    result = cursor.fetchone()
    cursor.close()
    assert result[0].upper() == "WAL"
    
    cursor = db_connection.execute("PRAGMA busy_timeout")
    result = cursor.fetchone()
    cursor.close()
    assert result[0] == 5000


def test_migration_initial_schema(migrated_db):
    """Test that initial schema migration works."""
    runner = MigrationRunner(migrated_db, Path(__file__).parent.parent / "src" / "gphotos_321sync" / "media_scanner" / "schema")
    version = runner.get_current_version()
    assert version == 1


def test_scan_run_dal(migrated_db):
    """Test scan run data access layer."""
    dal = ScanRunDAL(migrated_db)
    
    # Create scan run
    scan_run_id = dal.create_scan_run()
    assert scan_run_id is not None
    
    # Get scan run
    scan_run = dal.get_scan_run(scan_run_id)
    assert scan_run is not None
    assert scan_run['status'] == 'running'
    
    # Update scan run
    dal.update_scan_run(scan_run_id, files_processed=100)
    scan_run = dal.get_scan_run(scan_run_id)
    assert scan_run['files_processed'] == 100
    
    # Complete scan run
    dal.complete_scan_run(scan_run_id, 'completed')
    scan_run = dal.get_scan_run(scan_run_id)
    assert scan_run['status'] == 'completed'
    assert scan_run['end_timestamp'] is not None


def test_album_dal(migrated_db):
    """Test album data access layer."""
    dal = AlbumDAL(migrated_db)
    scan_run_dal = ScanRunDAL(migrated_db)
    
    scan_run_id = scan_run_dal.create_scan_run()
    
    # Insert album
    album_data = {
        'album_folder_path': 'Photos from 2023',
        'title': 'Photos from 2023',
        'scan_run_id': scan_run_id
    }
    album_id = dal.insert_album(album_data)
    assert album_id is not None
    
    # Get album by path
    album = dal.get_album_by_path('Photos from 2023')
    assert album is not None
    assert album['title'] == 'Photos from 2023'
    
    # Get album by ID
    album = dal.get_album_by_id(album_id)
    assert album is not None
    
    # Update album
    dal.update_album(album_id, description='Test description')
    album = dal.get_album_by_id(album_id)
    assert album['description'] == 'Test description'


def test_media_item_dal(migrated_db):
    """Test media item data access layer."""
    media_dal = MediaItemDAL(migrated_db)
    album_dal = AlbumDAL(migrated_db)
    scan_run_dal = ScanRunDAL(migrated_db)
    
    scan_run_id = scan_run_dal.create_scan_run()
    
    # Create album first
    album_id = album_dal.insert_album({
        'album_folder_path': 'Photos from 2023',
        'scan_run_id': scan_run_id
    })
    
    # Insert media item
    import uuid
    media_item_id = str(uuid.uuid4())  # Generate test UUID
    item_data = {
        'media_item_id': media_item_id,
        'relative_path': 'Photos from 2023/IMG_001.jpg',
        'album_id': album_id,
        'file_size': 1024000,
        'mime_type': 'image/jpeg',
        'scan_run_id': scan_run_id
    }
    returned_id = media_dal.insert_media_item(item_data)
    assert returned_id == media_item_id
    
    # Get media item by path
    item = media_dal.get_media_item_by_path('Photos from 2023/IMG_001.jpg')
    assert item is not None
    assert item['file_size'] == 1024000
    
    # Update media item
    media_dal.update_media_item(media_item_id, width=1920, height=1080)
    item = media_dal.get_media_item_by_id(media_item_id)
    assert item['width'] == 1920
    assert item['height'] == 1080


def test_processing_error_dal(migrated_db):
    """Test processing error data access layer."""
    dal = ProcessingErrorDAL(migrated_db)
    scan_run_dal = ScanRunDAL(migrated_db)
    
    scan_run_id = scan_run_dal.create_scan_run()
    
    # Insert error
    dal.insert_error(
        scan_run_id=scan_run_id,
        relative_path='Photos from 2023/corrupt.jpg',
        error_type='media_file',
        error_category='corrupted',
        error_message='File is corrupted'
    )
    
    # Get errors by scan
    errors = dal.get_errors_by_scan(scan_run_id)
    assert len(errors) == 1
    assert errors[0]['error_category'] == 'corrupted'
    
    # Get error count
    count = dal.get_error_count(scan_run_id)
    assert count == 1
    
    # Get error summary
    summary = dal.get_error_summary(scan_run_id)
    assert summary['corrupted'] == 1


def test_transaction_rollback(migrated_db):
    """Test that transactions rollback on error."""
    dal = ScanRunDAL(migrated_db)
    
    try:
        with migrated_db.transaction() as cursor:
            cursor.execute("INSERT INTO scan_runs (scan_run_id, status) VALUES (?, ?)", ('test-id', 'running'))
            # Force an error
            cursor.execute("INSERT INTO invalid_table (col) VALUES (?)", ('value',))
    except Exception:
        pass
    
    # Verify rollback - scan run should not exist
    scan_run = dal.get_scan_run('test-id')
    assert scan_run is None
