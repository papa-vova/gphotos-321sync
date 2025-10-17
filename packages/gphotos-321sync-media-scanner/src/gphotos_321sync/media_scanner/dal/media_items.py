"""Data Access Layer for media_items table."""

import logging
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..database import DatabaseConnection

logger = logging.getLogger(__name__)


class MediaItemDAL:
    """
    Data access layer for media_items table.
    
    Manages media item lifecycle, change detection, and status tracking.
    """
    
    def __init__(self, db: DatabaseConnection):
        """
        Initialize media item DAL.
        
        Args:
            db: Database connection
        """
        self.db = db
    
    def insert_media_item(self, item: Dict[str, Any]) -> str:
        """
        Insert a new media item.
        
        Args:
            item: Dictionary with media item data
                Required: media_item_id, relative_path, album_id, file_size, scan_run_id
                Optional: All other fields
                
        Returns:
            media_item_id (UUID5 string from item dict)
        """
        media_item_id = item['media_item_id']
        
        cursor = self.db.execute(
            """
            INSERT INTO media_items (
                media_item_id, relative_path, album_id, title, mime_type,
                file_size, crc32, content_fingerprint,
                width, height, duration_seconds, frame_rate,
                capture_timestamp, scan_run_id, status,
                original_media_item_id, live_photo_pair_id,
                exif_datetime_original, exif_datetime_digitized,
                exif_gps_latitude, exif_gps_longitude, exif_gps_altitude,
                exif_camera_make, exif_camera_model,
                exif_lens_make, exif_lens_model,
                exif_focal_length, exif_f_number, exif_exposure_time,
                exif_iso, exif_orientation, exif_flash, exif_white_balance,
                google_description,
                google_geo_data_latitude, google_geo_data_longitude,
                google_geo_data_altitude, google_geo_data_latitude_span,
                google_geo_data_longitude_span
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
            """,
            (
                media_item_id,
                item['relative_path'],
                item['album_id'],
                item.get('title'),
                item.get('mime_type'),
                item['file_size'],
                item.get('crc32'),
                item.get('content_fingerprint'),
                item.get('width'),
                item.get('height'),
                item.get('duration_seconds'),
                item.get('frame_rate'),
                item.get('capture_timestamp'),
                item['scan_run_id'],
                item.get('status', 'present'),
                item.get('original_media_item_id'),
                item.get('live_photo_pair_id'),
                item.get('exif_datetime_original'),
                item.get('exif_datetime_digitized'),
                item.get('exif_gps_latitude'),
                item.get('exif_gps_longitude'),
                item.get('exif_gps_altitude'),
                item.get('exif_camera_make'),
                item.get('exif_camera_model'),
                item.get('exif_lens_make'),
                item.get('exif_lens_model'),
                item.get('exif_focal_length'),
                item.get('exif_f_number'),
                item.get('exif_exposure_time'),
                item.get('exif_iso'),
                item.get('exif_orientation'),
                item.get('exif_flash'),
                item.get('exif_white_balance'),
                item.get('google_description'),
                item.get('google_geo_data_latitude'),
                item.get('google_geo_data_longitude'),
                item.get('google_geo_data_altitude'),
                item.get('google_geo_data_latitude_span'),
                item.get('google_geo_data_longitude_span'),
            )
        )
        cursor.close()
        self.db.commit()
        
        logger.debug(f"Inserted media item: {media_item_id} ({item['relative_path']})")
        return media_item_id
    
    def update_media_item(self, media_item_id: str, **fields):
        """
        Update media item fields.
        
        Args:
            media_item_id: Media item ID
            **fields: Fields to update
        """
        if not fields:
            return
        
        # Filter out None values
        fields = {k: v for k, v in fields.items() if v is not None}
        
        if not fields:
            return
        
        # Build SET clause
        set_clause = ", ".join(f"{key} = ?" for key in fields.keys())
        values = list(fields.values())
        values.append(media_item_id)
        
        cursor = self.db.execute(
            f"UPDATE media_items SET {set_clause} WHERE media_item_id = ?",
            values
        )
        cursor.close()
        
        logger.debug(f"Updated media item {media_item_id}: {list(fields.keys())}")
    
    def get_media_item_by_path(self, relative_path: str) -> Optional[Dict[str, Any]]:
        """
        Get media item by relative path.
        
        Args:
            relative_path: Relative path to file
            
        Returns:
            Dictionary with media item data, or None if not found
        """
        cursor = self.db.execute(
            "SELECT * FROM media_items WHERE relative_path = ?",
            (relative_path,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return dict(row)
        return None
    
    def get_media_item_by_id(self, media_item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get media item by ID.
        
        Args:
            media_item_id: Media item ID
            
        Returns:
            Dictionary with media item data, or None if not found
        """
        cursor = self.db.execute(
            "SELECT * FROM media_items WHERE media_item_id = ?",
            (media_item_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return dict(row)
        return None
    
    def mark_seen(self, media_item_id: str, scan_run_id: str):
        """
        Mark media item as seen in current scan (update scan_run_id and timestamp).
        
        Args:
            media_item_id: Media item ID
            scan_run_id: Current scan run ID
        """
        cursor = self.db.execute(
            """
            UPDATE media_items
            SET scan_run_id = ?,
                last_seen_timestamp = CURRENT_TIMESTAMP,
                status = 'present'
            WHERE media_item_id = ?
            """,
            (scan_run_id, media_item_id)
        )
        cursor.close()
    
    def mark_files_missing(self, scan_run_id: str) -> int:
        """
        Mark files as missing if they weren't seen in current scan.
        
        Args:
            scan_run_id: Current scan run ID
            
        Returns:
            Number of files marked as missing
        """
        cursor = self.db.execute(
            """
            UPDATE media_items
            SET status = 'missing'
            WHERE scan_run_id != ? AND status = 'present'
            """,
            (scan_run_id,)
        )
        count = cursor.rowcount
        cursor.close()
        self.db.commit()
        
        if count > 0:
            logger.info(f"Marked {count} file(s) as missing")
        
        return count
    
    def mark_files_inconsistent(self, scan_run_id: str, scan_start_time: datetime) -> int:
        """
        Mark files as inconsistent if they have current scan_run_id but old timestamp.
        
        This detects data anomalies (timing issues, incomplete transactions, bugs).
        
        Args:
            scan_run_id: Current scan run ID
            scan_start_time: When current scan started
            
        Returns:
            Number of files marked as inconsistent
        """
        cursor = self.db.execute(
            """
            UPDATE media_items
            SET status = 'inconsistent'
            WHERE scan_run_id = ?
              AND last_seen_timestamp < ?
              AND status = 'present'
            """,
            (scan_run_id, scan_start_time.isoformat())
        )
        count = cursor.rowcount
        cursor.close()
        self.db.commit()
        
        if count > 0:
            logger.warning(f"Marked {count} file(s) as inconsistent")
        
        return count
    
    def find_duplicates(self, file_size: int, crc32: str) -> List[Dict[str, Any]]:
        """
        Find potential duplicate files by size and CRC32.
        
        Args:
            file_size: File size in bytes
            crc32: CRC32 checksum
            
        Returns:
            List of media items with matching size and CRC32
        """
        cursor = self.db.execute(
            """
            SELECT * FROM media_items
            WHERE file_size = ? AND crc32 = ?
            ORDER BY first_seen_timestamp
            """,
            (file_size, crc32)
        )
        rows = cursor.fetchall()
        cursor.close()
        
        return [dict(row) for row in rows]
    
    def get_media_item_count(self, status: Optional[str] = None) -> int:
        """
        Get count of media items.
        
        Args:
            status: Optional status filter ('present', 'missing', 'error', 'inconsistent')
            
        Returns:
            Count of media items
        """
        if status:
            cursor = self.db.execute(
                "SELECT COUNT(*) as count FROM media_items WHERE status = ?",
                (status,)
            )
        else:
            cursor = self.db.execute(
                "SELECT COUNT(*) as count FROM media_items"
            )
        
        row = cursor.fetchone()
        cursor.close()
        
        return row['count'] if row else 0
    
    def batch_insert_media_items(self, items: List[Dict[str, Any]]) -> int:
        """
        Insert multiple media items in a batch.
        
        Args:
            items: List of media item dictionaries
            
        Returns:
            Number of items inserted
        """
        if not items:
            return 0
        
        # Generate UUIDs for all items
        for item in items:
            if 'media_item_id' not in item:
                item['media_item_id'] = str(uuid.uuid4())
        
        # Prepare data tuples
        data = [
            (
                item['media_item_id'],
                item['relative_path'],
                item['album_id'],
                item.get('title'),
                item.get('mime_type'),
                item['file_size'],
                item.get('crc32'),
                item.get('content_fingerprint'),
                item.get('width'),
                item.get('height'),
                item.get('duration_seconds'),
                item.get('frame_rate'),
                item.get('capture_timestamp'),
                item['scan_run_id'],
                item.get('status', 'present'),
                item.get('original_media_item_id'),
                item.get('live_photo_pair_id'),
                item.get('exif_datetime_original'),
                item.get('exif_datetime_digitized'),
                item.get('exif_gps_latitude'),
                item.get('exif_gps_longitude'),
                item.get('exif_gps_altitude'),
                item.get('exif_camera_make'),
                item.get('exif_camera_model'),
                item.get('exif_lens_make'),
                item.get('exif_lens_model'),
                item.get('exif_focal_length'),
                item.get('exif_f_number'),
                item.get('exif_exposure_time'),
                item.get('exif_iso'),
                item.get('exif_orientation'),
                item.get('exif_flash'),
                item.get('exif_white_balance'),
                item.get('google_description'),
                item.get('google_geo_data_latitude'),
                item.get('google_geo_data_longitude'),
                item.get('google_geo_data_altitude'),
                item.get('google_geo_data_latitude_span'),
                item.get('google_geo_data_longitude_span'),
            )
            for item in items
        ]
        
        cursor = self.db.executemany(
            """
            INSERT INTO media_items (
                media_item_id, relative_path, album_id, title, mime_type,
                file_size, crc32, content_fingerprint,
                width, height, duration_seconds, frame_rate,
                capture_timestamp, scan_run_id, status,
                original_media_item_id, live_photo_pair_id,
                exif_datetime_original, exif_datetime_digitized,
                exif_gps_latitude, exif_gps_longitude, exif_gps_altitude,
                exif_camera_make, exif_camera_model,
                exif_lens_make, exif_lens_model,
                exif_focal_length, exif_f_number, exif_exposure_time,
                exif_iso, exif_orientation, exif_flash, exif_white_balance,
                google_description,
                google_geo_data_latitude, google_geo_data_longitude,
                google_geo_data_altitude, google_geo_data_latitude_span,
                google_geo_data_longitude_span
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?)
            """,
            data
        )
        count = cursor.rowcount
        cursor.close()
        
        logger.debug(f"Batch inserted {count} media items")
        return count
