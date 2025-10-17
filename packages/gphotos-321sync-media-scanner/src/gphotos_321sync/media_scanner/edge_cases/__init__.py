"""Edge case handlers for special media types."""

from .live_photos import detect_live_photo_pairs, link_live_photo_pairs
from .edited_variants import detect_edited_variants, link_edited_variants

__all__ = [
    'detect_live_photo_pairs',
    'link_live_photo_pairs',
    'detect_edited_variants',
    'link_edited_variants',
]
