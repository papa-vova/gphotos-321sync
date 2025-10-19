"""Tests for Live Photos detection and linking."""

import uuid
from pathlib import Path
import pytest

from gphotos_321sync.media_scanner.edge_cases.live_photos import (
    FileInfo,
    detect_live_photo_pairs,
    link_live_photo_pairs,
    detect_and_link_live_photos,
)
from gphotos_321sync.media_scanner.database import DatabaseConnection
from gphotos_321sync.media_scanner.migrations import MigrationRunner
from gphotos_321sync.media_scanner.dal.scan_runs import ScanRunDAL
from gphotos_321sync.media_scanner.dal.media_items import MediaItemDAL
from gphotos_321sync.media_scanner.dal.albums import AlbumDAL
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


class TestDetectLivePhotoPairs:
    """Tests for detect_live_photo_pairs function."""
    
    def test_detects_heic_mov_pair(self):
        """Test detection of HEIC + MOV Live Photo pair."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234.HEIC"),
            FileInfo(relative_path="Photos/IMG_1234.MOV"),
        ]
        
        pairs = detect_live_photo_pairs(files)
        
        assert len(pairs) == 1
        assert pairs[0][0].relative_path == "Photos/IMG_1234.HEIC"
        assert pairs[0][1].relative_path == "Photos/IMG_1234.MOV"
    
    def test_detects_jpg_mov_pair(self):
        """Test detection of JPG + MOV Live Photo pair."""
        files = [
            FileInfo(relative_path="Photos/IMG_5678.JPG"),
            FileInfo(relative_path="Photos/IMG_5678.MOV"),
        ]
        
        pairs = detect_live_photo_pairs(files)
        
        assert len(pairs) == 1
        assert pairs[0][0].relative_path == "Photos/IMG_5678.JPG"
        assert pairs[0][1].relative_path == "Photos/IMG_5678.MOV"
    
    def test_detects_jpeg_mov_pair(self):
        """Test detection of JPEG + MOV Live Photo pair."""
        files = [
            FileInfo(relative_path="Photos/IMG_9999.jpeg"),
            FileInfo(relative_path="Photos/IMG_9999.mov"),
        ]
        
        pairs = detect_live_photo_pairs(files)
        
        assert len(pairs) == 1
    
    def test_ignores_unpaired_files(self):
        """Test that unpaired files are ignored."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234.HEIC"),
            FileInfo(relative_path="Photos/IMG_5678.MOV"),
        ]
        
        pairs = detect_live_photo_pairs(files)
        
        assert len(pairs) == 0
    
    def test_detects_multiple_pairs(self):
        """Test detection of multiple Live Photo pairs."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234.HEIC"),
            FileInfo(relative_path="Photos/IMG_1234.MOV"),
            FileInfo(relative_path="Photos/IMG_5678.JPG"),
            FileInfo(relative_path="Photos/IMG_5678.MOV"),
            FileInfo(relative_path="Photos/IMG_9999.HEIC"),
            FileInfo(relative_path="Photos/IMG_9999.MOV"),
        ]
        
        pairs = detect_live_photo_pairs(files)
        
        assert len(pairs) == 3
    
    def test_requires_same_directory(self):
        """Test that files must be in same directory to pair."""
        files = [
            FileInfo(relative_path="Photos/Album1/IMG_1234.HEIC"),
            FileInfo(relative_path="Photos/Album2/IMG_1234.MOV"),
        ]
        
        pairs = detect_live_photo_pairs(files)
        
        assert len(pairs) == 0
    
    def test_requires_same_base_name(self):
        """Test that files must have same base name to pair."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234.HEIC"),
            FileInfo(relative_path="Photos/IMG_5678.MOV"),
        ]
        
        pairs = detect_live_photo_pairs(files)
        
        assert len(pairs) == 0
    
    def test_ignores_non_media_files(self):
        """Test that non-media files are ignored."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234.HEIC"),
            FileInfo(relative_path="Photos/IMG_1234.MOV"),
            FileInfo(relative_path="Photos/IMG_1234.json"),
            FileInfo(relative_path="Photos/document.pdf"),
        ]
        
        pairs = detect_live_photo_pairs(files)
        
        assert len(pairs) == 1
    
    def test_case_insensitive_extensions(self):
        """Test that extension matching is case-insensitive."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234.heic"),
            FileInfo(relative_path="Photos/IMG_1234.mov"),
        ]
        
        pairs = detect_live_photo_pairs(files)
        
        assert len(pairs) == 1
    
    def test_empty_file_list(self):
        """Test with empty file list."""
        pairs = detect_live_photo_pairs([])
        
        assert len(pairs) == 0
    
class TestLinkLivePhotoPairs:
    """Tests for link_live_photo_pairs function."""
    
    def test_links_pair_in_database(self, test_db):
        """Test linking a Live Photo pair in database."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        media_dal = MediaItemDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create scan run and album
        scan_run_id = scan_run_dal.create_scan_run()
        album_id = str(uuid.uuid4())
        album_dal.insert_album({
            'album_id': album_id,
            'album_folder_path': "Photos/Test Album",
            'scan_run_id': scan_run_id,
        })
        
        # Create media items
        image_id = str(uuid.uuid4())
        video_id = str(uuid.uuid4())
        
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=image_id,
            relative_path="Photos/Test Album/IMG_1234.HEIC",
            album_id=album_id,
            file_size=1000,
            scan_run_id=scan_run_id,
        ))
        
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=video_id,
            relative_path="Photos/Test Album/IMG_1234.MOV",
            album_id=album_id,
            file_size=2000,
            scan_run_id=scan_run_id,
        ))
        conn.commit()  # Tests must commit manually
        
        # Create pair
        pairs = [
            (
                FileInfo(relative_path="Photos/Test Album/IMG_1234.HEIC", media_item_id=image_id),
                FileInfo(relative_path="Photos/Test Album/IMG_1234.MOV", media_item_id=video_id),
            )
        ]
        
        # Link pairs
        stats = link_live_photo_pairs(conn, pairs)
        
        assert stats['pairs_linked'] == 1
        assert stats['files_updated'] == 2
        
        # Verify both files have same pair ID
        cursor = conn.execute(
            "SELECT live_photo_pair_id FROM media_items WHERE media_item_id = ?",
            (image_id,)
        )
        image_pair_id = cursor.fetchone()[0]
        cursor.close()
        
        cursor = conn.execute(
            "SELECT live_photo_pair_id FROM media_items WHERE media_item_id = ?",
            (video_id,)
        )
        video_pair_id = cursor.fetchone()[0]
        cursor.close()
        
        assert image_pair_id is not None
        assert image_pair_id == video_pair_id
        
        conn.close()
    
    def test_links_multiple_pairs(self, test_db):
        """Test linking multiple Live Photo pairs."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        media_dal = MediaItemDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create scan run and album
        scan_run_id = scan_run_dal.create_scan_run()
        album_id = str(uuid.uuid4())
        album_dal.insert_album({
            'album_id': album_id,
            'album_folder_path': "Photos/Test Album",
            'scan_run_id': scan_run_id,
        })
        
        # Create multiple pairs
        pairs = []
        for i in range(3):
            image_id = str(uuid.uuid4())
            video_id = str(uuid.uuid4())
            
            media_dal.insert_media_item(create_media_item_record(
                media_item_id=image_id,
                relative_path=f"Photos/Test Album/IMG_{i}.HEIC",
                album_id=album_id,
                file_size=1000,
                scan_run_id=scan_run_id,
            ))
            
            media_dal.insert_media_item(create_media_item_record(
                media_item_id=video_id,
                relative_path=f"Photos/Test Album/IMG_{i}.MOV",
                album_id=album_id,
                file_size=2000,
                scan_run_id=scan_run_id,
            ))
            
            pairs.append((
                FileInfo(relative_path=f"Photos/Test Album/IMG_{i}.HEIC", media_item_id=image_id),
                FileInfo(relative_path=f"Photos/Test Album/IMG_{i}.MOV", media_item_id=video_id),
            ))
        
        conn.commit()  # Tests must commit manually
        
        # Link pairs
        stats = link_live_photo_pairs(conn, pairs)
        
        assert stats['pairs_linked'] == 3
        assert stats['files_updated'] == 6
        
        conn.close()
    
    def test_links_by_path_when_no_media_item_id(self, test_db):
        """Test linking when media_item_id is not provided."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        media_dal = MediaItemDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create scan run and album
        scan_run_id = scan_run_dal.create_scan_run()
        album_id = str(uuid.uuid4())
        album_dal.insert_album({
            'album_id': album_id,
            'album_folder_path': "Photos/Test Album",
            'scan_run_id': scan_run_id,
        })
        
        # Create media items
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=str(uuid.uuid4()),
            relative_path="Photos/Test Album/IMG_1234.HEIC",
            album_id=album_id,
            file_size=1000,
            scan_run_id=scan_run_id,
        ))
        
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=str(uuid.uuid4()),
            relative_path="Photos/Test Album/IMG_1234.MOV",
            album_id=album_id,
            file_size=2000,
            scan_run_id=scan_run_id,
        ))
        conn.commit()  # Tests must commit manually
        
        # Create pair without media_item_id
        pairs = [
            (
                FileInfo(relative_path="Photos/Test Album/IMG_1234.HEIC"),
                FileInfo(relative_path="Photos/Test Album/IMG_1234.MOV"),
            )
        ]
        
        # Link pairs
        stats = link_live_photo_pairs(conn, pairs)
        
        assert stats['pairs_linked'] == 1
        assert stats['files_updated'] == 2
        
        conn.close()


class TestDetectAndLinkLivePhotos:
    """Tests for detect_and_link_live_photos function."""
    
    def test_end_to_end_detection_and_linking(self, test_db):
        """Test complete Live Photo detection and linking workflow."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        media_dal = MediaItemDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create scan run and album
        scan_run_id = scan_run_dal.create_scan_run()
        album_id = str(uuid.uuid4())
        album_dal.insert_album({
            'album_id': album_id,
            'album_folder_path': "Photos/Test Album",
            'scan_run_id': scan_run_id,
        })
        
        # Create Live Photo pair
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=str(uuid.uuid4()),
            relative_path="Photos/Test Album/IMG_1234.HEIC",
            album_id=album_id,
            file_size=1000,
            scan_run_id=scan_run_id,
        ))
        
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=str(uuid.uuid4()),
            relative_path="Photos/Test Album/IMG_1234.MOV",
            album_id=album_id,
            file_size=2000,
            scan_run_id=scan_run_id,
        ))
        
        # Create unpaired file
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=str(uuid.uuid4()),
            relative_path="Photos/Test Album/IMG_5678.JPG",
            album_id=album_id,
            file_size=1500,
            scan_run_id=scan_run_id,
        ))
        conn.commit()  # Tests must commit manually
        
        conn.close()
        
        # Run detection and linking
        stats = detect_and_link_live_photos(str(test_db), scan_run_id)
        
        assert stats['pairs_linked'] == 1
        assert stats['files_updated'] == 2
        
        # Verify in database
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        cursor = conn.execute(
            """
            SELECT COUNT(DISTINCT live_photo_pair_id)
            FROM media_items
            WHERE scan_run_id = ?
              AND live_photo_pair_id IS NOT NULL
            """,
            (scan_run_id,)
        )
        unique_pairs = cursor.fetchone()[0]
        cursor.close()
        
        assert unique_pairs == 1
        
        conn.close()
    
    def test_no_pairs_found(self, test_db):
        """Test when no Live Photo pairs exist."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        media_dal = MediaItemDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create scan run and album
        scan_run_id = scan_run_dal.create_scan_run()
        album_id = str(uuid.uuid4())
        album_dal.insert_album({
            'album_id': album_id,
            'album_folder_path': "Photos/Test Album",
            'scan_run_id': scan_run_id,
        })
        
        # Create unpaired files
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=str(uuid.uuid4()),
            relative_path="Photos/Test Album/IMG_1234.JPG",
            album_id=album_id,
            file_size=1000,
            scan_run_id=scan_run_id,
        ))
        
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=str(uuid.uuid4()),
            relative_path="Photos/Test Album/IMG_5678.JPG",
            album_id=album_id,
            file_size=1500,
            scan_run_id=scan_run_id,
        ))
        conn.commit()  # Tests must commit manually
        
        conn.close()
        
        # Run detection and linking
        stats = detect_and_link_live_photos(str(test_db), scan_run_id)
        
        assert stats['pairs_linked'] == 0
        assert stats['files_updated'] == 0
