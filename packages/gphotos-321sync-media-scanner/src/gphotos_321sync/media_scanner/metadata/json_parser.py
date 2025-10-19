"""Parser for Google Takeout JSON sidecar files."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def parse_json_sidecar(json_path: Path) -> Dict[str, Any]:
    """
    Parse Google Takeout JSON sidecar file.
    
    Extracts metadata from .json files that accompany media files in
    Google Takeout exports.
    
    Args:
        json_path: Path to JSON sidecar file
        
    Returns:
        Dictionary with parsed metadata:
            - title: str
            - description: str
            - photoTakenTime: datetime (ISO format)
            - geoData: dict with latitude, longitude, altitude, latitudeSpan, longitudeSpan
            - people: list of person names
            
    Raises:
        FileNotFoundError: If JSON file doesn't exist
        json.JSONDecodeError: If JSON is malformed
    """
    if not json_path.exists():
        raise FileNotFoundError(f"JSON sidecar not found: {json_path}")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON {json_path}: {e}")
        raise
    
    metadata = {}
    
    # Extract title
    if 'title' in data:
        metadata['title'] = data['title']
    
    # Extract description
    if 'description' in data:
        metadata['description'] = data['description']
    
    # Extract photo taken time
    if 'photoTakenTime' in data:
        metadata['photoTakenTime'] = _parse_photo_taken_time(data['photoTakenTime'])
    
    # Extract creation time (fallback if photoTakenTime missing)
    if 'creationTime' in data and 'photoTakenTime' not in metadata:
        metadata['creationTime'] = _parse_timestamp(data['creationTime'])
    
    # Extract geo data
    if 'geoData' in data:
        metadata['geoData'] = _parse_geo_data(data['geoData'])
    
    # Extract geoDataExif (fallback if geoData missing)
    if 'geoDataExif' in data and 'geoData' not in metadata:
        metadata['geoData'] = _parse_geo_data(data['geoDataExif'])
    
    # Extract people
    if 'people' in data:
        metadata['people'] = _parse_people(data['people'])
    
    # Extract URL (for reference)
    if 'url' in data:
        metadata['url'] = data['url']
    
    # Extract Google Photos origin
    if 'googlePhotosOrigin' in data:
        metadata['googlePhotosOrigin'] = data['googlePhotosOrigin']
    
    # Extract image views (note: string, not int)
    if 'imageViews' in data:
        metadata['imageViews'] = data['imageViews']
    
    # Extract app source (Android package name)
    if 'appSource' in data:
        metadata['appSource'] = data['appSource']
    
    return metadata


def _parse_photo_taken_time(photo_taken_time: Dict[str, Any]) -> Optional[str]:
    """
    Parse photoTakenTime object to ISO timestamp.
    
    Args:
        photo_taken_time: Dictionary with timestamp, formatted
        
    Returns:
        ISO format timestamp string or None
    """
    if 'timestamp' in photo_taken_time:
        # Unix timestamp (seconds since epoch)
        timestamp = int(photo_taken_time['timestamp'])
        # Use timezone-aware datetime (UTC)
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.isoformat()
    elif 'formatted' in photo_taken_time:
        # Try to parse formatted string
        return _parse_formatted_timestamp(photo_taken_time['formatted'])
    
    return None


def _parse_timestamp(timestamp_data: Dict[str, Any]) -> Optional[str]:
    """
    Parse generic timestamp object.
    
    Args:
        timestamp_data: Dictionary with timestamp or formatted
        
    Returns:
        ISO format timestamp string or None
    """
    if isinstance(timestamp_data, dict):
        if 'timestamp' in timestamp_data:
            timestamp = int(timestamp_data['timestamp'])
            # Use timezone-aware datetime (UTC)
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            return dt.isoformat()
        elif 'formatted' in timestamp_data:
            return _parse_formatted_timestamp(timestamp_data['formatted'])
    
    return None


def _parse_formatted_timestamp(formatted: str) -> Optional[str]:
    """
    Parse formatted timestamp string to ISO format.
    
    Google uses various formats like:
    - "Jan 1, 2020, 12:00:00 AM UTC"
    - "2020-01-01T00:00:00Z"
    
    Args:
        formatted: Formatted timestamp string
        
    Returns:
        ISO format timestamp string or None
    """
    # If already ISO format, return as-is
    if 'T' in formatted and ('Z' in formatted or '+' in formatted):
        return formatted
    
    # Try common Google Photos formats
    formats = [
        "%b %d, %Y, %I:%M:%S %p UTC",  # Jan 1, 2020, 12:00:00 AM UTC
        "%b %d, %Y, %I:%M:%S %p",      # Jan 1, 2020, 12:00:00 AM
        "%Y-%m-%d %H:%M:%S UTC",       # 2020-01-01 00:00:00 UTC
        "%Y-%m-%d %H:%M:%S",           # 2020-01-01 00:00:00
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(formatted, fmt)
            # Make timezone-aware (Google Photos timestamps are UTC)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    
    logger.warning(f"Could not parse timestamp format: {formatted}")
    return None


def _parse_geo_data(geo_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Parse geoData object.
    
    Args:
        geo_data: Dictionary with latitude, longitude, altitude, etc.
        
    Returns:
        Dictionary with parsed geo coordinates
    """
    result = {}
    
    if 'latitude' in geo_data:
        result['latitude'] = float(geo_data['latitude'])
    
    if 'longitude' in geo_data:
        result['longitude'] = float(geo_data['longitude'])
    
    if 'altitude' in geo_data:
        result['altitude'] = float(geo_data['altitude'])
    
    if 'latitudeSpan' in geo_data:
        result['latitudeSpan'] = float(geo_data['latitudeSpan'])
    
    if 'longitudeSpan' in geo_data:
        result['longitudeSpan'] = float(geo_data['longitudeSpan'])
    
    return result


def _parse_people(people: List[Dict[str, Any]]) -> List[str]:
    """
    Parse people array to list of names.
    
    Args:
        people: List of person objects with 'name' field
        
    Returns:
        List of person names
    """
    names = []
    for person in people:
        if 'name' in person:
            names.append(person['name'])
    return names
