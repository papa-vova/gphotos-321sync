"""Data access layer for people and people tags."""

import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


class PeopleDAL:
    """Data access layer for people and people tags."""
    
    def __init__(self, db):
        """Initialize PeopleDAL.
        
        Args:
            db: Database connection (sqlite3.Connection with row_factory)
        """
        self.db = db
    
    def get_or_create_person(self, person_name: str) -> str:
        """Get existing person ID or create new person.
        
        Args:
            person_name: Name of the person
            
        Returns:
            person_id (UUID4 string)
        """
        cursor = self.db.cursor()
        
        # Try to find existing person
        cursor.execute(
            "SELECT person_id FROM people WHERE person_name = ?",
            (person_name,)
        )
        result = cursor.fetchone()
        
        if result:
            person_id = result['person_id']
            cursor.close()
            return person_id
        
        # Create new person
        person_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO people (person_id, person_name) VALUES (?, ?)",
            (person_id, person_name)
        )
        cursor.close()
        
        logger.debug(f"Created person: {{'person_id': {person_id!r}, 'name': {person_name!r}}}")
        return person_id
    
    def add_people_tags(self, media_item_id: str, people_names: list[str]):
        """Add people tags for a media item.
        
        Args:
            media_item_id: Media item UUID
            people_names: List of person names (in order)
        """
        if not people_names:
            return
        
        cursor = self.db.cursor()
        
        # Delete existing tags for this media item
        cursor.execute(
            "DELETE FROM people_tags WHERE media_item_id = ?",
            (media_item_id,)
        )
        
        # Insert new tags
        for tag_order, person_name in enumerate(people_names):
            person_id = self.get_or_create_person(person_name)
            cursor.execute(
                "INSERT INTO people_tags (media_item_id, person_id, tag_order) VALUES (?, ?, ?)",
                (media_item_id, person_id, tag_order)
            )
        
        cursor.close()
        logger.debug(f"Added {len(people_names)} people tags for media_item {media_item_id}")
    
    def get_people_for_media_item(self, media_item_id: str) -> list[str]:
        """Get people names for a media item.
        
        Args:
            media_item_id: Media item UUID
            
        Returns:
            List of person names (in tag_order)
        """
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT p.person_name
            FROM people_tags pt
            JOIN people p ON pt.person_id = p.person_id
            WHERE pt.media_item_id = ?
            ORDER BY pt.tag_order
            """,
            (media_item_id,)
        )
        results = cursor.fetchall()
        cursor.close()
        
        return [row['person_name'] for row in results]
