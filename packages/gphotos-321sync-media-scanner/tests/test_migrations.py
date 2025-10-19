"""Tests for database migration system.

Focus: Ensuring migrations don't break existing databases or lose data.
"""

import pytest
import sqlite3
from pathlib import Path

from gphotos_321sync.media_scanner.database import DatabaseConnection
from gphotos_321sync.media_scanner.migrations import MigrationRunner
from gphotos_321sync.media_scanner.dal import ScanRunDAL, AlbumDAL, MediaItemDAL
from tests.test_helpers import create_media_item_record


@pytest.fixture
def schema_dir():
    """Get the schema directory path."""
    return Path(__file__).parent.parent / "src" / "gphotos_321sync" / "media_scanner" / "schema"


@pytest.fixture
def empty_db(tmp_path):
    """Create an empty database connection."""
    db_path = tmp_path / "test.db"
    return DatabaseConnection(db_path)


@pytest.fixture
def populated_db(tmp_path, schema_dir):
    """Create a database with schema and some test data."""
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(db_path)
    
    # Apply migrations
    runner = MigrationRunner(db, schema_dir)
    runner.apply_migrations()
    
    # Add test data
    scan_dal = ScanRunDAL(db)
    album_dal = AlbumDAL(db)
    media_dal = MediaItemDAL(db)
    
    # Create scan run
    scan_id = scan_dal.create_scan_run()
    
    # Create album
    album_id = album_dal.insert_album({
        'scan_run_id': scan_id,
        'title': 'Test Album',
        'album_folder_path': 'Photos/Test Album'
    })
    
    # Create media items
    for i in range(5):
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=f'media-{i}',
            scan_run_id=scan_id,
            album_id=album_id,
            relative_path=f'Photos/Test Album/photo{i}.jpg',
            file_size=1024 * (i + 1),
            mime_type='image/jpeg',
            status='present'
        ))
    
    return db, scan_id, album_id


class TestMigrationBasics:
    """Test basic migration functionality."""
    
    def test_initial_migration_creates_schema_version_table(self, empty_db, schema_dir):
        """Test that migration creates schema_version table."""
        runner = MigrationRunner(empty_db, schema_dir)
        runner.apply_migrations()
        
        # Check schema_version table exists
        cursor = empty_db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
        assert cursor.fetchone() is not None
    
    def test_initial_migration_creates_all_tables(self, empty_db, schema_dir):
        """Test that initial migration creates all required tables."""
        runner = MigrationRunner(empty_db, schema_dir)
        runner.apply_migrations()
        
        expected_tables = {
            'schema_version',
            'scan_runs',
            'media_items',
            'albums',
            'people',
            'people_tags',
            'processing_errors'
        }
        
        cursor = empty_db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        actual_tables = {row[0] for row in cursor.fetchall()}
        
        assert expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}"
    
    def test_get_current_version_on_empty_db(self, empty_db, schema_dir):
        """Test getting version on database without migrations."""
        runner = MigrationRunner(empty_db, schema_dir)
        version = runner.get_current_version()
        assert version == 0
    
    def test_get_current_version_after_migration(self, empty_db, schema_dir):
        """Test getting version after applying migrations."""
        runner = MigrationRunner(empty_db, schema_dir)
        runner.apply_migrations()
        version = runner.get_current_version()
        assert version == 1  # Should be at version 1 after initial schema
    
    def test_migration_idempotency(self, empty_db, schema_dir):
        """Test that running migrations multiple times is safe."""
        runner = MigrationRunner(empty_db, schema_dir)
        
        # Apply migrations twice
        runner.apply_migrations()
        version1 = runner.get_current_version()
        
        runner.apply_migrations()
        version2 = runner.get_current_version()
        
        assert version1 == version2 == 1
        
        # Verify tables still exist and are intact
        cursor = empty_db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert 'media_items' in tables


class TestDataPreservation:
    """Test that migrations preserve existing data."""
    
    def test_reapplying_migration_preserves_scan_runs(self, populated_db, schema_dir):
        """Test that re-running migrations doesn't delete scan runs."""
        db, scan_id, _ = populated_db
        
        # Get initial scan run count
        cursor = db.execute("SELECT COUNT(*) FROM scan_runs")
        initial_count = cursor.fetchone()[0]
        assert initial_count == 1
        
        # Re-apply migrations
        runner = MigrationRunner(db, schema_dir)
        runner.apply_migrations()
        
        # Verify scan run still exists
        cursor = db.execute("SELECT COUNT(*) FROM scan_runs WHERE scan_run_id = ?", (scan_id,))
        assert cursor.fetchone()[0] == 1
    
    def test_reapplying_migration_preserves_albums(self, populated_db, schema_dir):
        """Test that re-running migrations doesn't delete albums."""
        db, _, album_id = populated_db
        
        # Get initial album
        cursor = db.execute("SELECT title FROM albums WHERE album_id = ?", (album_id,))
        initial_title = cursor.fetchone()[0]
        assert initial_title == "Test Album"
        
        # Re-apply migrations
        runner = MigrationRunner(db, schema_dir)
        runner.apply_migrations()
        
        # Verify album still exists with same data
        cursor = db.execute("SELECT title FROM albums WHERE album_id = ?", (album_id,))
        final_title = cursor.fetchone()[0]
        assert final_title == initial_title
    
    def test_reapplying_migration_preserves_media_items(self, populated_db, schema_dir):
        """Test that re-running migrations doesn't delete media items."""
        db, scan_id, album_id = populated_db
        
        # Get initial media item count
        cursor = db.execute("SELECT COUNT(*) FROM media_items WHERE album_id = ?", (album_id,))
        initial_count = cursor.fetchone()[0]
        assert initial_count == 5
        
        # Get specific media item data
        cursor = db.execute(
            "SELECT relative_path, file_size FROM media_items WHERE media_item_id = ?",
            ('media-0',)
        )
        initial_data = cursor.fetchone()
        
        # Re-apply migrations
        runner = MigrationRunner(db, schema_dir)
        runner.apply_migrations()
        
        # Verify all media items still exist
        cursor = db.execute("SELECT COUNT(*) FROM media_items WHERE album_id = ?", (album_id,))
        final_count = cursor.fetchone()[0]
        assert final_count == initial_count
        
        # Verify specific media item data unchanged
        cursor = db.execute(
            "SELECT relative_path, file_size FROM media_items WHERE media_item_id = ?",
            ('media-0',)
        )
        final_data = cursor.fetchone()
        assert final_data == initial_data


class TestSchemaIntegrity:
    """Test that migrations maintain schema integrity."""
    
    def test_all_required_columns_exist_in_media_items(self, empty_db, schema_dir):
        """Test that media_items table has all required columns."""
        runner = MigrationRunner(empty_db, schema_dir)
        runner.apply_migrations()
        
        cursor = empty_db.execute("PRAGMA table_info(media_items)")
        columns = {row[1] for row in cursor.fetchall()}
        
        required_columns = {
            'media_item_id',
            'scan_run_id',
            'album_id',
            'relative_path',
            'file_size',
            'mime_type',
            'status',
            'crc32',
            'content_fingerprint',
            'last_seen_timestamp'
        }
        
        assert required_columns.issubset(columns), f"Missing columns: {required_columns - columns}"
    
    def test_all_required_columns_exist_in_albums(self, empty_db, schema_dir):
        """Test that albums table has all required columns."""
        runner = MigrationRunner(empty_db, schema_dir)
        runner.apply_migrations()
        
        cursor = empty_db.execute("PRAGMA table_info(albums)")
        columns = {row[1] for row in cursor.fetchall()}
        
        required_columns = {
            'album_id',
            'scan_run_id',
            'title',
            'album_folder_path',
            'description',
            'creation_timestamp',
            'access_level',
            'status'
        }
        
        assert required_columns.issubset(columns), f"Missing columns: {required_columns - columns}"
    
    def test_all_required_columns_exist_in_scan_runs(self, empty_db, schema_dir):
        """Test that scan_runs table has all required columns."""
        runner = MigrationRunner(empty_db, schema_dir)
        runner.apply_migrations()
        
        cursor = empty_db.execute("PRAGMA table_info(scan_runs)")
        columns = {row[1] for row in cursor.fetchall()}
        
        required_columns = {
            'scan_run_id',
            'start_timestamp',
            'end_timestamp',
            'status',
            'total_files_discovered',
            'media_files_discovered',
            'metadata_files_discovered',
            'files_processed'
        }
        
        assert required_columns.issubset(columns), f"Missing columns: {required_columns - columns}"
    
    def test_indexes_created(self, empty_db, schema_dir):
        """Test that required indexes are created."""
        runner = MigrationRunner(empty_db, schema_dir)
        runner.apply_migrations()
        
        cursor = empty_db.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        
        # Check for key indexes (excluding auto-created primary key indexes)
        expected_indexes = {
            'idx_media_items_scan_run',
            'idx_media_items_album',
            'idx_media_items_path',
            'idx_media_items_fingerprint',
            'idx_albums_scan_run'
        }
        
        assert expected_indexes.issubset(indexes), f"Missing indexes: {expected_indexes - indexes}"


class TestMigrationOrdering:
    """Test that migrations are applied in correct order."""
    
    def test_migration_files_are_numbered(self, schema_dir):
        """Test that all migration files follow naming convention."""
        migration_files = sorted(schema_dir.glob("*.sql"))
        assert len(migration_files) > 0, "No migration files found"
        
        for i, migration_file in enumerate(migration_files, start=1):
            # Check filename starts with zero-padded number
            assert migration_file.name.startswith(f"{i:03d}_"), \
                f"Migration file {migration_file.name} doesn't follow naming convention"
    
    def test_migrations_applied_in_order(self, empty_db, schema_dir):
        """Test that migrations are applied sequentially."""
        runner = MigrationRunner(empty_db, schema_dir)
        
        # Apply migrations one by one
        migration_files = sorted(schema_dir.glob("*.sql"))
        
        for i, _ in enumerate(migration_files, start=1):
            runner.apply_migrations(target_version=i)
            version = runner.get_current_version()
            assert version == i, f"Expected version {i}, got {version}"


class TestDatabaseRecovery:
    """Test recovery scenarios."""
    
    def test_can_query_data_after_migration(self, populated_db, schema_dir):
        """Test that DAL operations work after migration."""
        db, scan_id, album_id = populated_db
        
        # Re-apply migrations
        runner = MigrationRunner(db, schema_dir)
        runner.apply_migrations()
        
        # Test DAL operations still work - query media items directly
        cursor = db.execute("SELECT * FROM media_items WHERE album_id = ?", (album_id,))
        items = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        
        assert len(items) == 5
        assert all(item['album_id'] == album_id for item in items)
    
    def test_can_insert_data_after_migration(self, populated_db, schema_dir):
        """Test that we can insert new data after migration."""
        db, scan_id, album_id = populated_db
        
        # Re-apply migrations
        runner = MigrationRunner(db, schema_dir)
        runner.apply_migrations()
        
        # Insert new media item
        media_dal = MediaItemDAL(db)
        media_dal.insert_media_item(create_media_item_record(
            media_item_id='new-media-item',
            scan_run_id=scan_id,
            album_id=album_id,
            relative_path='Photos/Test Album/new_photo.jpg',
            file_size=2048,
            mime_type='image/jpeg',
            status='present'
        ))
        
        # Verify insertion
        cursor = db.execute("SELECT COUNT(*) FROM media_items WHERE album_id = ?", (album_id,))
        assert cursor.fetchone()[0] == 6  # 5 original + 1 new


class TestCorruptionDetection:
    """Test detection of database issues."""
    
    def test_missing_schema_version_table_handled(self, tmp_path, schema_dir):
        """Test handling of database without schema_version table."""
        db_path = tmp_path / "test.db"
        
        # Create database with a table but no schema_version
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE dummy (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        
        # Try to run migrations
        db = DatabaseConnection(db_path)
        runner = MigrationRunner(db, schema_dir)
        
        # Should detect version 0 and apply migrations
        version = runner.get_current_version()
        assert version == 0
        
        runner.apply_migrations()
        
        # Verify schema_version table now exists
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
        assert cursor.fetchone() is not None
