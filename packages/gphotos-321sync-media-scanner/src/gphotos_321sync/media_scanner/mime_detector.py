"""MIME type detection using filetype library (pure Python, cross-platform)."""

from pathlib import Path
import filetype


def detect_mime_type(file_path: Path) -> str:
    """
    Detect MIME type of a file by reading its magic bytes.
    
    Uses the filetype library which reads file signatures without
    requiring external dependencies like libmagic.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MIME type string (e.g., 'image/jpeg', 'video/mp4')
        Returns 'application/octet-stream' if type cannot be determined
        
    Raises:
        OSError: If file cannot be read
    """
    kind = filetype.guess(str(file_path))
    if kind is not None:
        return kind.mime
    return 'application/octet-stream'


def is_image_mime_type(mime_type: str) -> bool:
    """Check if a MIME type represents an image."""
    return mime_type.startswith('image/')


def is_video_mime_type(mime_type: str) -> bool:
    """Check if a MIME type represents a video."""
    return mime_type.startswith('video/')
