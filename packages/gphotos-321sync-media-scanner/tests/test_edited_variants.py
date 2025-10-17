"""Tests for edited variant detection and linking."""

import uuid
from pathlib import Path
import pytest

from gphotos_321sync.media_scanner.edge_cases.edited_variants import (
    FileInfo,
    detect_edited_variants,
    link_edited_variants,
    detect_and_link_edited_variants,
)
from gphotos_321sync.media_scanner.database import DatabaseConnection
from gphotos_321sync.media_scanner.migrations import MigrationRunner
from gphotos_321sync.media_scanner.dal.scan_runs import ScanRunDAL
from gphotos_321sync.media_scanner.dal.media_items import MediaItemDAL
from gphotos_321sync.media_scanner.dal.albums import AlbumDAL


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


class TestDetectEditedVariants:
    """Tests for detect_edited_variants function."""
    
    def test_detects_edited_variant(self):
        """Test detection of basic edited variant."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234.JPG"),
            FileInfo(relative_path="Photos/IMG_1234-edited.JPG"),
        ]
        
        edited_to_original = detect_edited_variants(files)
        
        assert len(edited_to_original) == 1
        assert edited_to_original["Photos/IMG_1234-edited.JPG"] == "Photos/IMG_1234.JPG"
    
    def test_detects_multiple_variants(self):
        """Test detection of multiple edited variants."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234.JPG"),
            FileInfo(relative_path="Photos/IMG_1234-edited.JPG"),
            FileInfo(relative_path="Photos/IMG_5678.HEIC"),
            FileInfo(relative_path="Photos/IMG_5678-edited.HEIC"),
        ]
        
        edited_to_original = detect_edited_variants(files)
        
        assert len(edited_to_original) == 2
        assert edited_to_original["Photos/IMG_1234-edited.JPG"] == "Photos/IMG_1234.JPG"
        assert edited_to_original["Photos/IMG_5678-edited.HEIC"] == "Photos/IMG_5678.HEIC"
    
    def test_requires_original_to_exist(self):
        """Test that edited variant without original is not detected."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234-edited.JPG"),
        ]
        
        edited_to_original = detect_edited_variants(files)
        
        assert len(edited_to_original) == 0
    
    def test_requires_same_directory(self):
        """Test that original must be in same directory."""
        files = [
            FileInfo(relative_path="Photos/Album1/IMG_1234.JPG"),
            FileInfo(relative_path="Photos/Album2/IMG_1234-edited.JPG"),
        ]
        
        edited_to_original = detect_edited_variants(files)
        
        assert len(edited_to_original) == 0
    
    def test_requires_same_extension(self):
        """Test that original must have same extension."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234.JPG"),
            FileInfo(relative_path="Photos/IMG_1234-edited.PNG"),
        ]
        
        edited_to_original = detect_edited_variants(files)
        
        assert len(edited_to_original) == 0
    
    def test_ignores_non_edited_files(self):
        """Test that files without -edited suffix are ignored."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234.JPG"),
            FileInfo(relative_path="Photos/IMG_5678.JPG"),
            FileInfo(relative_path="Photos/IMG_9999.JPG"),
        ]
        
        edited_to_original = detect_edited_variants(files)
        
        assert len(edited_to_original) == 0
    
    def test_handles_nested_directories(self):
        """Test detection in nested directory structures."""
        files = [
            FileInfo(relative_path="Photos/2023/January/IMG_1234.JPG"),
            FileInfo(relative_path="Photos/2023/January/IMG_1234-edited.JPG"),
            FileInfo(relative_path="Photos/2023/February/IMG_5678.HEIC"),
            FileInfo(relative_path="Photos/2023/February/IMG_5678-edited.HEIC"),
        ]
        
        edited_to_original = detect_edited_variants(files)
        
        assert len(edited_to_original) == 2
    
    def test_empty_file_list(self):
        """Test with empty file list."""
        edited_to_original = detect_edited_variants([])
        
        assert len(edited_to_original) == 0
    
    def test_multiple_edits_of_same_original(self):
        """Test handling of multiple edited versions (edge case)."""
        files = [
            FileInfo(relative_path="Photos/IMG_1234.JPG"),
            FileInfo(relative_path="Photos/IMG_1234-edited.JPG"),
            FileInfo(relative_path="Photos/IMG_1234-edited-edited.JPG"),
        ]
        
        edited_to_original = detect_edited_variants(files)
        
        # Should detect both as edited variants
        assert len(edited_to_original) == 2
        assert edited_to_original["Photos/IMG_1234-edited.JPG"] == "Photos/IMG_1234.JPG"
        # The double-edited one should link to the single-edited version
        assert edited_to_original["Photos/IMG_1234-edited-edited.JPG"] == "Photos/IMG_1234-edited.JPG"


class TestLinkEditedVariants:
    """Tests for link_edited_variants function."""
    
    def test_links_variant_to_original(self, test_db):
        """Test linking edited variant to original in database."""
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
        
        # Create original and edited media items
        original_id = str(uuid.uuid4())
        edited_id = str(uuid.uuid4())
        
        media_dal.insert_media_item({
            'media_item_id': original_id,
            'relative_path': "Photos/Test Album/IMG_1234.JPG",
            'album_id': album_id,
            'file_size': 1000,
            'scan_run_id': scan_run_id,
        })
        
        media_dal.insert_media_item({
            'media_item_id': edited_id,
            'relative_path': "Photos/Test Album/IMG_1234-edited.JPG",
            'album_id': album_id,
            'file_size': 1100,
            'scan_run_id': scan_run_id,
        })
        
        # Link variants
        edited_to_original = {
            "Photos/Test Album/IMG_1234-edited.JPG": "Photos/Test Album/IMG_1234.JPG"
        }
        
        stats = link_edited_variants(conn, edited_to_original)
        
        assert stats['variants_linked'] == 1
        assert stats['originals_found'] == 1
        assert stats['originals_missing'] == 0
        
        # Verify link in database
        cursor = conn.execute(
            "SELECT original_media_item_id FROM media_items WHERE media_item_id = ?",
            (edited_id,)
        )
        linked_original_id = cursor.fetchone()[0]
        cursor.close()
        
        assert linked_original_id == original_id
        
        conn.close()
    
    def test_links_multiple_variants(self, test_db):
        """Test linking multiple edited variants."""
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
        
        # Create multiple original/edited pairs
        edited_to_original = {}
        
        for i in range(3):
            original_id = str(uuid.uuid4())
            edited_id = str(uuid.uuid4())
            
            media_dal.insert_media_item({
                'media_item_id': original_id,
                'relative_path': f"Photos/Test Album/IMG_{i}.JPG",
                'album_id': album_id,
                'file_size': 1000,
                'scan_run_id': scan_run_id,
            })
            
            media_dal.insert_media_item({
                'media_item_id': edited_id,
                'relative_path': f"Photos/Test Album/IMG_{i}-edited.JPG",
                'album_id': album_id,
                'file_size': 1100,
                'scan_run_id': scan_run_id,
            })
            
            edited_to_original[f"Photos/Test Album/IMG_{i}-edited.JPG"] = f"Photos/Test Album/IMG_{i}.JPG"
        
        # Link variants
        stats = link_edited_variants(conn, edited_to_original)
        
        assert stats['variants_linked'] == 3
        assert stats['originals_found'] == 3
        assert stats['originals_missing'] == 0
        
        conn.close()
    
    def test_handles_missing_original(self, test_db):
        """Test handling when original is not in database."""
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
        
        # Create only edited variant (no original)
        edited_id = str(uuid.uuid4())
        media_dal.insert_media_item({
            'media_item_id': edited_id,
            'relative_path': "Photos/Test Album/IMG_1234-edited.JPG",
            'album_id': album_id,
            'file_size': 1100,
            'scan_run_id': scan_run_id,
        })
        
        # Try to link
        edited_to_original = {
            "Photos/Test Album/IMG_1234-edited.JPG": "Photos/Test Album/IMG_1234.JPG"
        }
        
        stats = link_edited_variants(conn, edited_to_original)
        
        assert stats['variants_linked'] == 0
        assert stats['originals_found'] == 0
        assert stats['originals_missing'] == 1
        
        conn.close()
    
    def test_handles_missing_edited_variant(self, test_db):
        """Test handling when edited variant is not in database."""
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
        
        # Create only original (no edited variant)
        original_id = str(uuid.uuid4())
        media_dal.insert_media_item({
            'media_item_id': original_id,
            'relative_path': "Photos/Test Album/IMG_1234.JPG",
            'album_id': album_id,
            'file_size': 1000,
            'scan_run_id': scan_run_id,
        })
        
        # Try to link
        edited_to_original = {
            "Photos/Test Album/IMG_1234-edited.JPG": "Photos/Test Album/IMG_1234.JPG"
        }
        
        stats = link_edited_variants(conn, edited_to_original)
        
        # Original found but variant not updated (doesn't exist)
        assert stats['variants_linked'] == 0
        assert stats['originals_found'] == 1
        assert stats['originals_missing'] == 0
        
        conn.close()


class TestDetectAndLinkEditedVariants:
    """Tests for detect_and_link_edited_variants function."""
    
    def test_end_to_end_detection_and_linking(self, test_db):
        """Test complete edited variant detection and linking workflow."""
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
        
        # Create original and edited variant
        original_id = str(uuid.uuid4())
        edited_id = str(uuid.uuid4())
        
        media_dal.insert_media_item({
            'media_item_id': original_id,
            'relative_path': "Photos/Test Album/IMG_1234.JPG",
            'album_id': album_id,
            'file_size': 1000,
            'scan_run_id': scan_run_id,
        })
        
        media_dal.insert_media_item({
            'media_item_id': edited_id,
            'relative_path': "Photos/Test Album/IMG_1234-edited.JPG",
            'album_id': album_id,
            'file_size': 1100,
            'scan_run_id': scan_run_id,
        })
        
        # Create unrelated file
        media_dal.insert_media_item({
            'media_item_id': str(uuid.uuid4()),
            'relative_path': "Photos/Test Album/IMG_5678.JPG",
            'album_id': album_id,
            'file_size': 1500,
            'scan_run_id': scan_run_id,
        })
        
        conn.close()
        
        # Run detection and linking
        stats = detect_and_link_edited_variants(str(test_db), scan_run_id)
        
        assert stats['variants_linked'] == 1
        assert stats['originals_found'] == 1
        assert stats['originals_missing'] == 0
        
        # Verify in database
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        cursor = conn.execute(
            "SELECT original_media_item_id FROM media_items WHERE media_item_id = ?",
            (edited_id,)
        )
        linked_original_id = cursor.fetchone()[0]
        cursor.close()
        
        assert linked_original_id == original_id
        
        conn.close()
    
    def test_no_variants_found(self, test_db):
        """Test when no edited variants exist."""
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
        
        # Create only regular files
        media_dal.insert_media_item({
            'media_item_id': str(uuid.uuid4()),
            'relative_path': "Photos/Test Album/IMG_1234.JPG",
            'album_id': album_id,
            'file_size': 1000,
            'scan_run_id': scan_run_id,
        })
        
        media_dal.insert_media_item({
            'media_item_id': str(uuid.uuid4()),
            'relative_path': "Photos/Test Album/IMG_5678.JPG",
            'album_id': album_id,
            'file_size': 1500,
            'scan_run_id': scan_run_id,
        })
        
        conn.close()
        
        # Run detection and linking
        stats = detect_and_link_edited_variants(str(test_db), scan_run_id)
        
        assert stats['variants_linked'] == 0
        assert stats['originals_found'] == 0
        assert stats['originals_missing'] == 0
    
    def test_multiple_variants_in_different_albums(self, test_db):
        """Test detection across multiple albums."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        media_dal = MediaItemDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create scan run
        scan_run_id = scan_run_dal.create_scan_run()
        
        # Create two albums with edited variants
        for album_num in range(2):
            album_id = str(uuid.uuid4())
            album_dal.insert_album({
                'album_id': album_id,
                'album_folder_path': f"Photos/Album {album_num}",
                'scan_run_id': scan_run_id,
            })
            
            # Create original and edited in each album
            media_dal.insert_media_item({
                'media_item_id': str(uuid.uuid4()),
                'relative_path': f"Photos/Album {album_num}/IMG_1234.JPG",
                'album_id': album_id,
                'file_size': 1000,
                'scan_run_id': scan_run_id,
            })
            
            media_dal.insert_media_item({
                'media_item_id': str(uuid.uuid4()),
                'relative_path': f"Photos/Album {album_num}/IMG_1234-edited.JPG",
                'album_id': album_id,
                'file_size': 1100,
                'scan_run_id': scan_run_id,
            })
        
        conn.close()
        
        # Run detection and linking
        stats = detect_and_link_edited_variants(str(test_db), scan_run_id)
        
        assert stats['variants_linked'] == 2
        assert stats['originals_found'] == 2
        assert stats['originals_missing'] == 0
