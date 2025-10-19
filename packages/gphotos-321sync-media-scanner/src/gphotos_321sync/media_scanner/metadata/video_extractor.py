"""Video metadata extraction using ffprobe."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def is_video_file(mime_type: str) -> bool:
    """
    Check if MIME type represents a video file.
    
    Args:
        mime_type: MIME type string
        
    Returns:
        True if video, False otherwise
    """
    return mime_type.startswith('video/')


def extract_video_metadata(file_path: Path) -> Dict[str, Any]:
    """
    Extract video metadata using ffprobe.
    
    Extracts:
    - duration_seconds: float
    - width: int
    - height: int
    - frame_rate: float
    
    Args:
        file_path: Path to video file
        
    Returns:
        Dictionary with video metadata
        
    Raises:
        FileNotFoundError: If ffprobe is not available
        subprocess.CalledProcessError: If ffprobe fails
    """
    metadata = {}
    
    try:
        # Run ffprobe to get video info
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(file_path)
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',  # Explicitly use UTF-8 to handle non-ASCII paths
            check=True,
            timeout=30  # 30 second timeout
        )
        
        data = json.loads(result.stdout)
        
        # Extract format-level metadata
        if 'format' in data:
            fmt = data['format']
            
            # Duration
            if 'duration' in fmt:
                metadata['duration_seconds'] = float(fmt['duration'])
        
        # Extract video stream metadata
        if 'streams' in data:
            for stream in data['streams']:
                if stream.get('codec_type') == 'video':
                    # Resolution
                    if 'width' in stream:
                        metadata['width'] = int(stream['width'])
                    if 'height' in stream:
                        metadata['height'] = int(stream['height'])
                    
                    # Frame rate
                    if 'r_frame_rate' in stream:
                        metadata['frame_rate'] = _parse_frame_rate(stream['r_frame_rate'])
                    elif 'avg_frame_rate' in stream:
                        metadata['frame_rate'] = _parse_frame_rate(stream['avg_frame_rate'])
                    
                    # Only process first video stream
                    break
    
    except FileNotFoundError:
        logger.warning("ffprobe not found - video metadata extraction disabled")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"ffprobe failed for {file_path}: {e.stderr}")
        raise
    except subprocess.TimeoutExpired:
        logger.error(f"ffprobe timed out for {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ffprobe output for {file_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error extracting video metadata from {file_path}: {e}")
        raise
    
    return metadata


def _parse_frame_rate(frame_rate_str: str) -> Optional[float]:
    """
    Parse frame rate string to float.
    
    ffprobe returns frame rate as "30000/1001" or "30/1"
    
    Args:
        frame_rate_str: Frame rate string
        
    Returns:
        Frame rate as float or None
    """
    try:
        if '/' in frame_rate_str:
            numerator, denominator = frame_rate_str.split('/')
            num = float(numerator)
            den = float(denominator)
            if den == 0:
                return None
            return num / den
        else:
            return float(frame_rate_str)
    except (ValueError, ZeroDivisionError):
        logger.warning(f"Could not parse frame rate: {frame_rate_str}")
        return None
