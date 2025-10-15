"""Metadata extraction modules."""

from .json_parser import parse_json_sidecar
from .exif_extractor import (
    extract_exif,
    extract_exif_with_exiftool,
    extract_exif_smart,
    extract_resolution,
)
from .video_extractor import extract_video_metadata, is_video_file
from .aggregator import aggregate_metadata

__all__ = [
    'parse_json_sidecar',
    'extract_exif',
    'extract_exif_with_exiftool',
    'extract_exif_smart',
    'extract_resolution',
    'extract_video_metadata',
    'is_video_file',
    'aggregate_metadata',
]
