"""Data Access Layer for albums table."""

import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from ..database import DatabaseConnection

logger = logging.getLogger(__name__)

# UUID namespace for album IDs (deterministic UUID5 generation)
ALBUM_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # Standard DNS namespace


class AlbumDAL:
    """
    Data access layer for albums table.
    
    Every folder is an album. Album IDs are deterministic (UUID5 from path).
    """
    
    def __init__(self, db: DatabaseConnection):
        """
        Initialize album DAL.
        
        Args:
            db: Database connection
        """
        self.db = db
    
    def generate_album_id(self, album_folder_path: str) -> str:
        """
        Generate deterministic album ID from folder name.
        
        Uses UUID5 with a namespace to ensure same name always generates same ID.
        
        IMPORTANT: Pass ONLY the album folder name (e.g., "Photos from 2023"),
        NOT the full path. This ensures consistent IDs regardless of where
        the Takeout is extracted.
        
        Args:
            album_folder_path: Album folder name (NOT full path)
            
        Returns:
            Album ID (UUID5 string)
        """
        return str(uuid.uuid5(ALBUM_NAMESPACE, album_folder_path))
    
    def upsert_album(self, album: Dict[str, Any]) -> str:
        """
        Insert a new album or update if exists (upsert operation).
        
        Args:
            album: Dictionary with album data
                Required: album_folder_path, scan_run_id
                Optional: album_id, title, description, creation_timestamp, access_level, status
                
        Returns:
            album_id (UUID5 string)
        """
        album_folder_path = album['album_folder_path']
        # Use provided album_id if present, otherwise generate from path
        album_id = album.get('album_id') or self.generate_album_id(album_folder_path)
        
        # Check if album already exists
        existing = self.get_album_by_path(album_folder_path)
        
        if existing:
            # Check if album data actually changed
            fields_to_update = {}
            
            # Always update scan_run_id and last_seen_timestamp (like file_seen)
            fields_to_update['scan_run_id'] = album['scan_run_id']
            fields_to_update['last_seen_timestamp'] = datetime.now(timezone.utc).isoformat()
            
            # Check if metadata fields changed
            new_title = album.get('title')
            if new_title is not None and new_title != existing.get('title'):
                fields_to_update['title'] = new_title
            
            new_description = album.get('description')
            if new_description is not None and new_description != existing.get('description'):
                fields_to_update['description'] = new_description
            
            new_creation_timestamp = album.get('creation_timestamp')
            if new_creation_timestamp is not None and new_creation_timestamp != existing.get('creation_timestamp'):
                # Convert datetime to ISO format string for storage
                fields_to_update['creation_timestamp'] = new_creation_timestamp.isoformat() if isinstance(new_creation_timestamp, datetime) else new_creation_timestamp
            
            new_access_level = album.get('access_level')
            if new_access_level is not None and new_access_level != existing.get('access_level'):
                fields_to_update['access_level'] = new_access_level
            
            new_status = album.get('status', 'present')
            if new_status != existing.get('status'):
                fields_to_update['status'] = new_status
            
            # Only update if there are fields to change
            if fields_to_update:
                self.update_album(album_id, **fields_to_update)
                self.db.commit()
                logger.debug(f"Updated album {album_id}: {list(fields_to_update.keys())}")
        else:
            # Insert new album
            self._insert_album_internal(
                album_id,
                album_folder_path,
                album.get('title'),
                album.get('description'),
                album.get('creation_timestamp'),
                album.get('access_level'),
                album.get('status', 'present'),
                album['scan_run_id']
            )
            self.db.commit()
            logger.debug(f"Inserted album {album_id}: {{'title': {album.get('title')!r}}}")
        
        return album_id
    
    def _insert_album_internal(
        self,
        album_id: str,
        album_folder_path: str,
        title: Optional[str],
        description: Optional[str],
        creation_timestamp: Optional[datetime],
        access_level: Optional[str],
        status: str,
        scan_run_id: str
    ) -> None:
        """
        Internal method to insert a new album (does not check for existence).
        
        Args:
            album_id: Album ID (UUID5)
            album_folder_path: Normalized folder path
            title: Album title
            description: Album description
            creation_timestamp: Creation timestamp
            access_level: Access level
            status: Album status
            scan_run_id: Scan run ID
        """
        # Convert datetime to ISO format string for storage
        creation_timestamp_str = creation_timestamp.isoformat() if isinstance(creation_timestamp, datetime) else creation_timestamp
        
        # Set first_seen and last_seen timestamps with timezone-aware UTC
        now_utc = datetime.now(timezone.utc).isoformat()
        
        cursor = self.db.execute(
            """
            INSERT INTO albums (
                album_id, album_folder_path, title, description,
                creation_timestamp, access_level, status, scan_run_id,
                first_seen_timestamp, last_seen_timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                album_id,
                album_folder_path,
                title,
                description,
                creation_timestamp_str,
                access_level,
                status,
                scan_run_id,
                now_utc,  # first_seen_timestamp
                now_utc   # last_seen_timestamp
            )
        )
        cursor.close()
    
    def get_album_by_path(self, album_folder_path: str) -> Optional[Dict[str, Any]]:
        """
        Get album by folder path.
        
        Args:
            album_folder_path: Folder path
            
        Returns:
            Dictionary with album data, or None if not found
        """
        cursor = self.db.execute(
            "SELECT * FROM albums WHERE album_folder_path = ?",
            (album_folder_path,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return dict(row)
        return None
    
    def get_album_by_id(self, album_id: str) -> Optional[Dict[str, Any]]:
        """
        Get album by ID.
        
        Args:
            album_id: Album ID
            
        Returns:
            Dictionary with album data, or None if not found
        """
        cursor = self.db.execute(
            "SELECT * FROM albums WHERE album_id = ?",
            (album_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return dict(row)
        return None
    
    def update_album(self, album_id: str, **fields) -> None:
        """
        Update album fields.
        
        Args:
            album_id: Album ID
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
        values.append(album_id)
        
        cursor = self.db.execute(
            f"UPDATE albums SET {set_clause} WHERE album_id = ?",
            values
        )
        cursor.close()
    
    def mark_albums_missing(self, scan_run_id: str) -> int:
        """
        Mark albums as missing if they weren't seen in current scan.
        
        Args:
            scan_run_id: Current scan run ID
            
        Returns:
            Number of albums marked as missing
        """
        cursor = self.db.execute(
            """
            UPDATE albums
            SET status = 'missing'
            WHERE scan_run_id != ? AND status = 'present'
            """,
            (scan_run_id,)
        )
        count = cursor.rowcount
        cursor.close()
        self.db.commit()
        
        if count > 0:
            logger.info(f"Marked {count} album(s) as missing")
        
        return count
    
    def get_album_count(self, status: Optional[str] = None) -> int:
        """
        Get count of albums.
        
        Args:
            status: Optional status filter ('present', 'error', 'missing')
            
        Returns:
            Count of albums
        """
        if status:
            cursor = self.db.execute(
                "SELECT COUNT(*) as count FROM albums WHERE status = ?",
                (status,)
            )
        else:
            cursor = self.db.execute(
                "SELECT COUNT(*) as count FROM albums"
            )
        
        row = cursor.fetchone()
        cursor.close()
        
        return row['count'] if row else 0
