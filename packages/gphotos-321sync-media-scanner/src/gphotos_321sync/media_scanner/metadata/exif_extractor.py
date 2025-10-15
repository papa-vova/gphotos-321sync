"""EXIF metadata extraction using Pillow and ExifTool."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from ..mime_detector import detect_mime_type, is_image_mime_type, is_unknown_mime_type

logger = logging.getLogger(__name__)


def extract_exif(file_path: Path) -> Dict[str, Any]:
    """
    Extract EXIF metadata from image file using Pillow.
    
    Supports: JPEG, PNG, HEIC, GIF, WebP, BMP, TIFF
    
    Args:
        file_path: Path to image file
        
    Returns:
        Dictionary with EXIF metadata:
            - datetime_original: str (ISO format)
            - datetime_digitized: str (ISO format)
            - gps_latitude: float
            - gps_longitude: float
            - gps_altitude: float
            - camera_make: str
            - camera_model: str
            - lens_make: str
            - lens_model: str
            - focal_length: float
            - f_number: float
            - exposure_time: str
            - iso: int
            - orientation: int (1-8)
            - flash: str
            - white_balance: str
    """
    metadata = {}
    
    try:
        with Image.open(file_path) as img:
            exif_data = img.getexif()
            
            if not exif_data:
                logger.debug(f"No EXIF data found in {file_path}")
                return metadata
            
            # Extract basic EXIF tags
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                
                # DateTime fields
                if tag_name == 'DateTimeOriginal':
                    metadata['datetime_original'] = _parse_exif_datetime(value)
                elif tag_name == 'DateTimeDigitized':
                    metadata['datetime_digitized'] = _parse_exif_datetime(value)
                
                # Camera info
                elif tag_name == 'Make':
                    metadata['camera_make'] = str(value).strip()
                elif tag_name == 'Model':
                    metadata['camera_model'] = str(value).strip()
                elif tag_name == 'LensMake':
                    metadata['lens_make'] = str(value).strip()
                elif tag_name == 'LensModel':
                    metadata['lens_model'] = str(value).strip()
                
                # Exposure settings
                elif tag_name == 'FocalLength':
                    metadata['focal_length'] = _parse_rational(value)
                elif tag_name == 'FNumber':
                    metadata['f_number'] = _parse_rational(value)
                elif tag_name == 'ExposureTime':
                    metadata['exposure_time'] = _format_exposure_time(value)
                elif tag_name == 'ISOSpeedRatings' or tag_name == 'ISO':
                    metadata['iso'] = int(value) if isinstance(value, (int, float)) else int(value[0]) if isinstance(value, tuple) else None
                
                # Orientation
                elif tag_name == 'Orientation':
                    metadata['orientation'] = int(value)
                
                # Flash
                elif tag_name == 'Flash':
                    metadata['flash'] = _parse_flash(value)
                
                # White balance
                elif tag_name == 'WhiteBalance':
                    metadata['white_balance'] = _parse_white_balance(value)
            
            # Extract GPS data
            gps_data = _extract_gps_data(exif_data)
            if gps_data:
                metadata.update(gps_data)
    
    except Exception as e:
        logger.warning(f"Failed to extract EXIF from {file_path}: {e}")
    
    return metadata


def extract_resolution(file_path: Path) -> Optional[Tuple[int, int]]:
    """
    Extract image resolution (width, height).
    
    Args:
        file_path: Path to image file
        
    Returns:
        Tuple of (width, height) or None if extraction fails
    """
    try:
        with Image.open(file_path) as img:
            return img.size  # (width, height)
    except Exception as e:
        logger.warning(f"Failed to extract resolution from {file_path}: {e}")
        return None


def _extract_gps_data(exif_data) -> Dict[str, float]:
    """
    Extract GPS coordinates from EXIF data.
    
    Args:
        exif_data: EXIF data from PIL Image
        
    Returns:
        Dictionary with gps_latitude, gps_longitude, gps_altitude
    """
    gps_info = {}
    
    try:
        # Get GPS IFD
        gps_ifd = exif_data.get_ifd(0x8825)  # GPS IFD tag
        
        if not gps_ifd:
            return gps_info
        
        # Parse GPS tags
        gps_data = {}
        for tag_id, value in gps_ifd.items():
            tag_name = GPSTAGS.get(tag_id, tag_id)
            gps_data[tag_name] = value
        
        # Extract latitude
        if 'GPSLatitude' in gps_data and 'GPSLatitudeRef' in gps_data:
            lat = _convert_gps_coordinate(gps_data['GPSLatitude'])
            if lat is not None:
                if gps_data['GPSLatitudeRef'] == 'S':
                    lat = -lat
                gps_info['gps_latitude'] = lat
        
        # Extract longitude
        if 'GPSLongitude' in gps_data and 'GPSLongitudeRef' in gps_data:
            lon = _convert_gps_coordinate(gps_data['GPSLongitude'])
            if lon is not None:
                if gps_data['GPSLongitudeRef'] == 'W':
                    lon = -lon
                gps_info['gps_longitude'] = lon
        
        # Extract altitude
        if 'GPSAltitude' in gps_data:
            altitude = _parse_rational(gps_data['GPSAltitude'])
            if altitude is not None:
                if 'GPSAltitudeRef' in gps_data and gps_data['GPSAltitudeRef'] == 1:
                    altitude = -altitude  # Below sea level
                gps_info['gps_altitude'] = altitude
    
    except Exception as e:
        logger.warning(f"Failed to extract GPS data: {e}", exc_info=True)
    
    return gps_info


def _convert_gps_coordinate(coord_tuple) -> Optional[float]:
    """
    Convert GPS coordinate from degrees/minutes/seconds to decimal.
    
    Args:
        coord_tuple: Tuple of (degrees, minutes, seconds) - can be floats or rationals
        
    Returns:
        Decimal coordinate or None if conversion fails
    """
    try:
        if not coord_tuple or len(coord_tuple) < 3:
            return None
        
        # Handle both float and rational formats
        # Pillow may return IFDRational objects that look like floats but aren't
        # Just convert everything to float - IFDRational, int, float, and tuples all work
        from PIL.TiffImagePlugin import IFDRational
        
        degrees = float(coord_tuple[0]) if isinstance(coord_tuple[0], (int, float, IFDRational)) else _parse_rational(coord_tuple[0])
        minutes = float(coord_tuple[1]) if isinstance(coord_tuple[1], (int, float, IFDRational)) else _parse_rational(coord_tuple[1])
        seconds = float(coord_tuple[2]) if isinstance(coord_tuple[2], (int, float, IFDRational)) else _parse_rational(coord_tuple[2])
        
        if degrees is None or minutes is None or seconds is None:
            return None
        
        return float(degrees) + (float(minutes) / 60.0) + (float(seconds) / 3600.0)
    except Exception:
        return None


def _parse_rational(value) -> Optional[float]:
    """
    Parse EXIF rational value to float.
    
    Args:
        value: Rational value (can be int, float, IFDRational, or tuple)
        
    Returns:
        Float value or None
    """
    from PIL.TiffImagePlugin import IFDRational
    
    if isinstance(value, (int, float, IFDRational)):
        return float(value)
    elif isinstance(value, tuple) and len(value) == 2:
        numerator, denominator = value
        if denominator == 0:
            return None
        return float(numerator) / float(denominator)
    return None


def _parse_exif_datetime(value: str) -> Optional[str]:
    """
    Parse EXIF datetime to ISO format.
    
    EXIF format: "2020:01:01 12:00:00"
    ISO format: "2020-01-01T12:00:00"
    
    Args:
        value: EXIF datetime string
        
    Returns:
        ISO format datetime string or None
    """
    try:
        # Replace colons in date part with hyphens
        parts = value.split(' ')
        if len(parts) == 2:
            date_part = parts[0].replace(':', '-')
            time_part = parts[1]
            return f"{date_part}T{time_part}"
    except Exception:
        pass
    
    return None


def _format_exposure_time(value) -> str:
    """
    Format exposure time as fraction string.
    
    Args:
        value: Exposure time (rational or float)
        
    Returns:
        Formatted string like "1/100" or "2.5"
    """
    if isinstance(value, tuple) and len(value) == 2:
        numerator, denominator = value
        if numerator == 1:
            return f"1/{denominator}"
        else:
            return f"{numerator}/{denominator}"
    elif isinstance(value, (int, float)):
        return str(value)
    
    return str(value)


def _parse_flash(value: int) -> str:
    """
    Parse flash value to human-readable string.
    
    Args:
        value: Flash value (bitmask)
        
    Returns:
        Flash description
    """
    if value & 0x1:
        return "Flash fired"
    else:
        return "Flash did not fire"


def _parse_white_balance(value: int) -> str:
    """
    Parse white balance value.
    
    Args:
        value: White balance value (0 = auto, 1 = manual)
        
    Returns:
        White balance description
    """
    return "Auto" if value == 0 else "Manual"


def extract_exif_with_exiftool(file_path: Path) -> Dict[str, Any]:
    """
    Extract EXIF metadata from RAW image files using ExifTool.
    
    Used for RAW formats that Pillow cannot read (CR2, NEF, ARW, DNG, etc.)
    
    Args:
        file_path: Path to RAW image file
        
    Returns:
        Dictionary with EXIF metadata (same format as extract_exif)
        
    Raises:
        FileNotFoundError: If exiftool is not available
        subprocess.CalledProcessError: If exiftool fails
    """
    metadata = {}
    
    try:
        # Run exiftool with JSON output
        result = subprocess.run(
            [
                'exiftool',
                '-json',
                '-DateTimeOriginal',
                '-CreateDate',
                '-GPSLatitude',
                '-GPSLongitude',
                '-GPSAltitude',
                '-Make',
                '-Model',
                '-LensMake',
                '-LensModel',
                '-FocalLength',
                '-FNumber',
                '-ExposureTime',
                '-ISO',
                '-Orientation',
                '-Flash',
                '-WhiteBalance',
                '-ImageWidth',
                '-ImageHeight',
                str(file_path)
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        
        data = json.loads(result.stdout)
        if not data or len(data) == 0:
            return metadata
        
        # ExifTool returns array with single object
        exif = data[0]
        
        # Extract timestamps
        if 'DateTimeOriginal' in exif:
            metadata['datetime_original'] = _normalize_exiftool_datetime(exif['DateTimeOriginal'])
        elif 'CreateDate' in exif:
            metadata['datetime_digitized'] = _normalize_exiftool_datetime(exif['CreateDate'])
        
        # Extract GPS
        if 'GPSLatitude' in exif:
            metadata['gps_latitude'] = _parse_exiftool_gps_coordinate(exif['GPSLatitude'])
        if 'GPSLongitude' in exif:
            metadata['gps_longitude'] = _parse_exiftool_gps_coordinate(exif['GPSLongitude'])
        if 'GPSAltitude' in exif:
            metadata['gps_altitude'] = _parse_exiftool_altitude(exif['GPSAltitude'])
        
        # Extract camera info
        if 'Make' in exif:
            metadata['camera_make'] = str(exif['Make']).strip()
        if 'Model' in exif:
            metadata['camera_model'] = str(exif['Model']).strip()
        if 'LensMake' in exif:
            metadata['lens_make'] = str(exif['LensMake']).strip()
        if 'LensModel' in exif:
            metadata['lens_model'] = str(exif['LensModel']).strip()
        
        # Extract exposure settings
        if 'FocalLength' in exif:
            metadata['focal_length'] = _parse_exiftool_number(exif['FocalLength'])
        if 'FNumber' in exif:
            metadata['f_number'] = _parse_exiftool_number(exif['FNumber'])
        if 'ExposureTime' in exif:
            metadata['exposure_time'] = str(exif['ExposureTime'])
        if 'ISO' in exif:
            metadata['iso'] = int(exif['ISO'])
        
        # Extract orientation
        if 'Orientation' in exif:
            metadata['orientation'] = _parse_exiftool_orientation(exif['Orientation'])
        
        # Extract resolution
        if 'ImageWidth' in exif:
            metadata['width'] = int(exif['ImageWidth'])
        if 'ImageHeight' in exif:
            metadata['height'] = int(exif['ImageHeight'])
    
    except FileNotFoundError:
        logger.warning("exiftool not found - RAW format metadata extraction disabled")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"exiftool failed for {file_path}: {e.stderr}")
        raise
    except subprocess.TimeoutExpired:
        logger.error(f"exiftool timed out for {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse exiftool output for {file_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error extracting EXIF with exiftool from {file_path}: {e}")
        raise
    
    return metadata


def _normalize_exiftool_datetime(dt_str: str) -> Optional[str]:
    """
    Normalize ExifTool datetime to ISO format.
    
    ExifTool format: "2020:01:01 12:00:00"
    ISO format: "2020-01-01T12:00:00"
    """
    try:
        parts = dt_str.split(' ')
        if len(parts) == 2:
            date_part = parts[0].replace(':', '-')
            time_part = parts[1]
            return f"{date_part}T{time_part}"
    except Exception:
        pass
    return None


def _parse_exiftool_gps_coordinate(coord_str: str) -> Optional[float]:
    """
    Parse ExifTool GPS coordinate string to decimal.
    
    ExifTool format: "37 deg 46' 29.64\" N" or "37.7749"
    """
    try:
        # If already decimal
        if 'deg' not in coord_str:
            # Remove direction letter if present
            coord_str = coord_str.rstrip('NSEW ')
            return float(coord_str)
        
        # Parse degrees/minutes/seconds format
        # Example: "37 deg 46' 29.64\" N"
        import re
        match = re.match(r"(\d+) deg (\d+)' ([\d.]+)\" ([NSEW])", coord_str)
        if match:
            degrees = float(match.group(1))
            minutes = float(match.group(2))
            seconds = float(match.group(3))
            direction = match.group(4)
            
            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
            
            # Apply direction
            if direction in ['S', 'W']:
                decimal = -decimal
            
            return decimal
    except Exception as e:
        logger.warning(f"Could not parse GPS coordinate: {coord_str}: {e}")
    
    return None


def _parse_exiftool_altitude(alt_str: str) -> Optional[float]:
    """
    Parse ExifTool altitude string.
    
    ExifTool format: "10.5 m" or "10.5 m Above Sea Level"
    """
    try:
        # Extract number, removing units
        import re
        match = re.match(r"([\d.]+)", alt_str)
        if match:
            altitude = float(match.group(1))
            # Check if below sea level
            if 'below' in alt_str.lower():
                altitude = -altitude
            return altitude
    except Exception:
        pass
    return None


def _parse_exiftool_number(value) -> Optional[float]:
    """Parse ExifTool numeric value, removing units."""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        # Remove common units
        value_str = str(value).split()[0]  # Take first part before space
        return float(value_str)
    except Exception:
        return None


def _parse_exiftool_orientation(value) -> Optional[int]:
    """
    Parse ExifTool orientation value.
    
    Can be int (1-8) or string like "Horizontal (normal)"
    """
    try:
        if isinstance(value, int):
            return value
        # Try to extract number from string
        import re
        match = re.search(r'\d+', str(value))
        if match:
            return int(match.group())
    except Exception:
        pass
    return None


def extract_exif_smart(file_path: Path, use_exiftool: bool = False) -> Dict[str, Any]:
    """
    Smart EXIF extraction with automatic format detection and tool selection.
    
    Strategy:
    1. Detect MIME type using magic bytes
    2. If known image format (JPEG/PNG/HEIC) → use Pillow (fast)
    3. If unknown format (application/octet-stream) and ExifTool enabled → use ExifTool
       (handles RAW formats: CR2, NEF, ARW, DNG, etc.)
    4. Otherwise → return empty dict
    
    Args:
        file_path: Path to image file
        use_exiftool: Whether ExifTool is enabled in config
        
    Returns:
        Dictionary with EXIF metadata
    """
    mime_type = detect_mime_type(file_path)
    
    # Known image format - use Pillow (fast path)
    if is_image_mime_type(mime_type):
        try:
            return extract_exif(file_path)
        except Exception as e:
            logger.warning(f"Pillow failed for {file_path}: {e}")
            return {}
    
    # Unknown format - try ExifTool if enabled
    # This handles RAW formats that filetype library can't detect
    if is_unknown_mime_type(mime_type) and use_exiftool:
        try:
            return extract_exif_with_exiftool(file_path)
        except FileNotFoundError:
            logger.debug(f"ExifTool not available for {file_path}")
            return {}
        except Exception as e:
            logger.warning(f"ExifTool failed for {file_path}: {e}")
            return {}
    
    # Not an image or ExifTool not enabled
    return {}
