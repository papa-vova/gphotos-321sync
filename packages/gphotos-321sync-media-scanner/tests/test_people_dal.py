"""Tests for PeopleDAL."""

import pytest
from pathlib import Path

from gphotos_321sync.media_scanner.database import DatabaseConnection
from gphotos_321sync.media_scanner.dal.people import PeopleDAL
from gphotos_321sync.media_scanner.migrations import MigrationRunner


@pytest.fixture
def test_db(tmp_path):
    """Create test database with schema."""
    db_path = tmp_path / "test.db"
    db_conn = DatabaseConnection(db_path)
    
    # Apply migrations
    schema_dir = Path(__file__).parent.parent / "src" / "gphotos_321sync" / "media_scanner" / "schema"
    runner = MigrationRunner(db_conn, schema_dir)
    runner.apply_migrations()
    
    conn = db_conn.connect()
    yield conn
    conn.close()


def test_get_or_create_person_new(test_db):
    """Test creating a new person."""
    people_dal = PeopleDAL(test_db)
    
    person_id = people_dal.get_or_create_person("John Doe")
    
    assert person_id is not None
    assert len(person_id) == 36  # UUID format
    
    # Verify person was created
    cursor = test_db.cursor()
    cursor.execute("SELECT person_name FROM people WHERE person_id = ?", (person_id,))
    result = cursor.fetchone()
    assert result['person_name'] == "John Doe"


def test_get_or_create_person_existing(test_db):
    """Test getting an existing person."""
    people_dal = PeopleDAL(test_db)
    
    # Create person first time
    person_id1 = people_dal.get_or_create_person("Jane Smith")
    
    # Get same person second time
    person_id2 = people_dal.get_or_create_person("Jane Smith")
    
    # Should return same ID
    assert person_id1 == person_id2


def test_add_people_tags(test_db):
    """Test adding people tags to a media item."""
    people_dal = PeopleDAL(test_db)
    
    media_item_id = "test-media-123"
    people_names = ["Alice", "Bob", "Charlie"]
    
    people_dal.add_people_tags(media_item_id, people_names)
    
    # Verify tags were created
    cursor = test_db.cursor()
    cursor.execute(
        """
        SELECT p.person_name, pt.tag_order
        FROM people_tags pt
        JOIN people p ON pt.person_id = p.person_id
        WHERE pt.media_item_id = ?
        ORDER BY pt.tag_order
        """,
        (media_item_id,)
    )
    results = cursor.fetchall()
    
    assert len(results) == 3
    assert results[0]['person_name'] == "Alice"
    assert results[0]['tag_order'] == 0
    assert results[1]['person_name'] == "Bob"
    assert results[1]['tag_order'] == 1
    assert results[2]['person_name'] == "Charlie"
    assert results[2]['tag_order'] == 2


def test_add_people_tags_empty_list(test_db):
    """Test adding empty people list (should do nothing)."""
    people_dal = PeopleDAL(test_db)
    
    media_item_id = "test-media-456"
    people_dal.add_people_tags(media_item_id, [])
    
    # Verify no tags were created
    cursor = test_db.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM people_tags WHERE media_item_id = ?", (media_item_id,))
    result = cursor.fetchone()
    assert result['count'] == 0


def test_add_people_tags_replaces_existing(test_db):
    """Test that adding tags replaces existing tags."""
    people_dal = PeopleDAL(test_db)
    
    media_item_id = "test-media-789"
    
    # Add initial tags
    people_dal.add_people_tags(media_item_id, ["Person A", "Person B"])
    
    # Replace with new tags
    people_dal.add_people_tags(media_item_id, ["Person C"])
    
    # Verify only new tags exist
    cursor = test_db.cursor()
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
    
    assert len(results) == 1
    assert results[0]['person_name'] == "Person C"


def test_get_people_for_media_item(test_db):
    """Test retrieving people for a media item."""
    people_dal = PeopleDAL(test_db)
    
    media_item_id = "test-media-abc"
    people_names = ["David", "Emma"]
    
    # Add tags
    people_dal.add_people_tags(media_item_id, people_names)
    
    # Retrieve tags
    retrieved_names = people_dal.get_people_for_media_item(media_item_id)
    
    assert retrieved_names == ["David", "Emma"]


def test_get_people_for_media_item_no_tags(test_db):
    """Test retrieving people for media item with no tags."""
    people_dal = PeopleDAL(test_db)
    
    retrieved_names = people_dal.get_people_for_media_item("nonexistent-media")
    
    assert retrieved_names == []
