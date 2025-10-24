"""Tests for scan summary generation."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest

from gphotos_321sync.media_scanner.summary import (
    generate_summary,
    format_summary_human_readable,
)
from gphotos_321sync.media_scanner.database import DatabaseConnection
from gphotos_321sync.media_scanner.migrations import MigrationRunner
from gphotos_321sync.media_scanner.dal.scan_runs import ScanRunDAL
from gphotos_321sync.media_scanner.dal.media_items import MediaItemDAL
from gphotos_321sync.media_scanner.dal.albums import AlbumDAL
from gphotos_321sync.media_scanner.dal.processing_errors import ProcessingErrorDAL
from tests.test_helpers import create_media_item_record


@pytest.fixture
def test_db(tmp_path):
    """Create a test database."""
    db_path = tmp_path / "test.db"
    
    # Initialize database
    db_conn = DatabaseConnection(db_path)
    
    # Get schema directory
    schema_dir = Path(__file__).parent.parent / "src" / "gphotos_321sync" / "media_scanner" / "schema"
    
    # Run migrations
    runner = MigrationRunner(db_conn, schema_dir)
    runner.apply_migrations()
    
    db_conn.close()
    
    return db_path


@pytest.fixture
def populated_db(test_db):
    """Create a database with sample data."""
    db_conn = DatabaseConnection(test_db)
    conn = db_conn.connect()
    
    scan_run_dal = ScanRunDAL(conn)
    media_dal = MediaItemDAL(conn)
    album_dal = AlbumDAL(conn)
    error_dal = ProcessingErrorDAL(conn)
    
    # Create scan run
    scan_run_id = scan_run_dal.create_scan_run()
    
    # Update scan run with statistics
    scan_run_dal.update_scan_run(
        scan_run_id,
        total_files_discovered=100,
        media_files_discovered=80,
        metadata_files_discovered=20,
        media_files_processed=80,
        metadata_files_processed=60,
        media_new_files=50,
        media_unchanged_files=20,
        media_changed_files=5,
        missing_files=3,
        media_error_files=2,
        inconsistent_files=0,
        albums_total=5,
    )
    
    # Create albums
    album_ids = []
    for i in range(5):
        album_id = str(uuid.uuid4())
        album_ids.append(album_id)
        album_dal.upsert_album({
            'album_id': album_id,
            'album_folder_path': f"Photos/Album {i}",
            'scan_run_id': scan_run_id,
        })
    
    # Create media items with various statuses
    for i in range(75):
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=str(uuid.uuid4()),
            relative_path=f"Photos/Album {i % 5}/photo{i}.jpg",
            album_id=album_ids[i % 5],
            file_size=1000 + i,
            scan_run_id=scan_run_id,
        ))
    conn.commit()  # Tests must commit manually
    
    # Create missing files
    now_utc = datetime.now(timezone.utc).isoformat()
    for i in range(3):
        media_item_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO media_items (
                media_item_id, relative_path, album_id, file_size,
                scan_run_id, status, first_seen_timestamp, last_seen_timestamp
            ) VALUES (?, ?, ?, ?, ?, 'missing', ?, ?)
            """,
            (media_item_id, f"Photos/Album 0/missing{i}.jpg", album_ids[0], 1000, scan_run_id, now_utc, now_utc)
        )
    
    # Create error files
    for i in range(2):
        media_item_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO media_items (
                media_item_id, relative_path, album_id, file_size,
                scan_run_id, status, first_seen_timestamp, last_seen_timestamp
            ) VALUES (?, ?, ?, ?, ?, 'error', ?, ?)
            """,
            (media_item_id, f"Photos/Album 0/error{i}.jpg", album_ids[0], 1000, scan_run_id, now_utc, now_utc)
        )
    
    # Create processing errors
    error_dal.insert_error(
        scan_run_id=scan_run_id,
        relative_path="Photos/Album 0/corrupt1.jpg",
        error_type="media_file",
        error_category="corrupted",
        error_message="File is corrupted",
    )
    
    error_dal.insert_error(
        scan_run_id=scan_run_id,
        relative_path="Photos/Album 0/corrupt2.jpg",
        error_type="media_file",
        error_category="corrupted",
        error_message="File is corrupted",
    )
    
    error_dal.insert_error(
        scan_run_id=scan_run_id,
        relative_path="Photos/Album 0/bad.json",
        error_type="json_sidecar",
        error_category="parse_error",
        error_message="Invalid JSON",
    )
    
    # Complete scan run
    scan_run_dal.complete_scan_run(scan_run_id, 'completed')
    
    conn.commit()
    conn.close()
    
    return test_db, scan_run_id


class TestGenerateSummary:
    """Tests for generate_summary function."""
    
    def test_basic_summary_structure(self, populated_db):
        """Test that summary has all required fields."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        
        # Verify top-level keys
        assert 'scan_run_id' in summary
        assert 'status' in summary
        assert 'timestamps' in summary
        assert 'discovery' in summary
        assert 'processing' in summary
        assert 'albums' in summary
        assert 'file_status' in summary
        assert 'errors' in summary
        assert 'performance' in summary
    
    def test_scan_run_metadata(self, populated_db):
        """Test scan run metadata in summary."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        
        assert summary['scan_run_id'] == scan_run_id
        assert summary['status'] == 'completed'
        assert summary['timestamps']['start'] is not None
        assert summary['timestamps']['end'] is not None
        assert summary['timestamps']['duration_seconds'] is not None
    
    def test_discovery_statistics(self, populated_db):
        """Test discovery statistics in summary."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        
        disc = summary['discovery']
        assert disc['total_files_discovered'] == 100
        assert disc['media_files_discovered'] == 80
        assert disc['metadata_files_discovered'] == 20
    
    def test_processing_statistics(self, populated_db):
        """Test processing statistics in summary."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        
        proc = summary['processing']
        assert proc['media_files_processed'] == 80
        assert proc['metadata_files_processed'] == 60
        assert proc['media_new_files'] == 50
        assert proc['media_unchanged_files'] == 20
        assert proc['media_changed_files'] == 5
        assert proc['missing_files'] == 3
        assert proc['media_error_files'] == 2
        assert proc['inconsistent_files'] == 0
    
    def test_album_statistics(self, populated_db):
        """Test album statistics in summary."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        
        albums = summary['albums']
        assert albums['total'] == 5
        assert albums['present'] == 5
        assert albums['missing'] == 0
        assert albums['error'] == 0
    
    def test_file_status_breakdown(self, populated_db):
        """Test file status breakdown in summary."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        
        file_status = summary['file_status']
        assert file_status['present'] == 75
        assert file_status['missing'] == 3
        assert file_status['error'] == 2
    
    def test_error_breakdown(self, populated_db):
        """Test error breakdown in summary."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        
        errors = summary['errors']
        assert errors['total'] == 3
        
        # By type
        assert errors['by_type']['media_file'] == 2
        assert errors['by_type']['json_sidecar'] == 1
        
        # By category
        assert errors['by_category']['corrupted'] == 2
        assert errors['by_category']['parse_error'] == 1
        
        # By type and category
        assert len(errors['by_type_and_category']) == 2
    
    def test_performance_metrics(self, populated_db):
        """Test performance metrics in summary."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        
        perf = summary['performance']
        assert 'duration_seconds' in perf
        assert 'files_per_second' in perf
    
    def test_nonexistent_scan_run(self, test_db):
        """Test that ValueError is raised for nonexistent scan run."""
        with pytest.raises(ValueError, match="Scan run not found"):
            generate_summary(str(test_db), "nonexistent-scan-id")
    
    def test_empty_scan_run(self, test_db):
        """Test summary for scan run with no files."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        scan_run_id = scan_run_dal.create_scan_run()
        scan_run_dal.complete_scan_run(scan_run_id, 'completed')
        
        conn.close()
        
        summary = generate_summary(str(test_db), scan_run_id)
        
        assert summary['scan_run_id'] == scan_run_id
        assert summary['discovery']['total_files_discovered'] == 0
        assert summary['processing']['media_files_processed'] == 0
        assert summary['errors']['total'] == 0


class TestFormatSummaryHumanReadable:
    """Tests for format_summary_human_readable function."""
    
    def test_formats_basic_summary(self, populated_db):
        """Test that summary is formatted as readable text."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        formatted = format_summary_human_readable(summary)
        
        # Verify it's a string
        assert isinstance(formatted, str)
        
        # Verify key sections are present
        assert "SCAN SUMMARY REPORT" in formatted
        assert "TIMING" in formatted
        assert "DISCOVERY" in formatted
        assert "PROCESSING" in formatted
        assert "ALBUMS" in formatted
        assert "FILE STATUS" in formatted
        assert "ERRORS" in formatted
        assert "PERFORMANCE" in formatted
    
    def test_includes_scan_run_id(self, populated_db):
        """Test that formatted summary includes scan run ID."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        formatted = format_summary_human_readable(summary)
        
        assert scan_run_id in formatted
    
    def test_includes_statistics(self, populated_db):
        """Test that formatted summary includes key statistics."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        formatted = format_summary_human_readable(summary)
        
        # Check for some key numbers
        assert "100" in formatted  # total_files_discovered
        assert "80" in formatted   # media_files_discovered
        assert "5" in formatted    # albums_total
    
    def test_formats_errors_section(self, populated_db):
        """Test that errors are formatted correctly."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        formatted = format_summary_human_readable(summary)
        
        # Verify error details
        assert "Total errors: 3" in formatted
        assert "media_file" in formatted
        assert "json_sidecar" in formatted
        assert "corrupted" in formatted
        assert "parse_error" in formatted
    
    def test_formats_empty_summary(self, test_db):
        """Test formatting of empty scan summary."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        scan_run_id = scan_run_dal.create_scan_run()
        scan_run_dal.complete_scan_run(scan_run_id, 'completed')
        
        conn.close()
        
        summary = generate_summary(str(test_db), scan_run_id)
        formatted = format_summary_human_readable(summary)
        
        # Should still have all sections
        assert "SCAN SUMMARY REPORT" in formatted
        assert "DISCOVERY" in formatted
        assert "PROCESSING" in formatted
        
        # Should show zeros
        assert "0" in formatted
    
    def test_readable_formatting(self, populated_db):
        """Test that output uses readable formatting."""
        test_db, scan_run_id = populated_db
        
        summary = generate_summary(str(test_db), scan_run_id)
        formatted = format_summary_human_readable(summary)
        
        # Should have separators
        assert "=" * 70 in formatted
        assert "-" * 70 in formatted
        
        # Should have proper line breaks
        lines = formatted.split('\n')
        assert len(lines) > 10  # Should be multi-line
