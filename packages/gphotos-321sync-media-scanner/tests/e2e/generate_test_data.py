"""Generate synthetic test data for end-to-end testing.

Creates a comprehensive test dataset resembling Google Takeout structure with:
- Multiple user albums and year-based albums
- All supported media file types (images, videos, RAW formats)
- All JSON sidecar variants (standard, truncated, plain .json)
- Edge cases: edited files, live photos, tilde duplicates, Windows duplicates
- Corrupted files for error handling tests
- Synthetic metadata (no personal data)
- ~10,000 total files (media + sidecars)
"""

import json
import logging
import random
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Import PIL for image generation
try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL not available - will create placeholder image files")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Synthetic data constants
SYNTHETIC_ALBUM_NAMES = [
    "Abstract Patterns",
    "Geometric Shapes",
    "Color Gradients",
    "Nature Textures",
    "Urban Architecture",
    "Minimalist Compositions",
    "Light and Shadow",
    "Symmetry Studies",
]

SYNTHETIC_DESCRIPTIONS = [
    "Collection of abstract visual elements",
    "Geometric composition study",
    "Color theory exploration",
    "Texture and pattern analysis",
    "Architectural form study",
    "Minimalist design principles",
    "Light interaction experiments",
    "Symmetrical arrangements",
    "",  # Empty description
]

# Device types for synthetic metadata
DEVICE_TYPES = ["ANDROID_PHONE", "IOS_PHONE", "ANDROID_TABLET", "CAMERA"]
DEVICE_FOLDERS = ["Camera", "Screenshots", "Downloads", "DCIM", ""]

# File naming patterns
IMAGE_PATTERNS = [
    "IMG_{date}_{seq:04d}",
    "DSC_{seq:04d}",
    "IMG_{seq:04d}",
    "Screenshot_{date}-{time}",
    "PXL_{date}_{time}",
]

VIDEO_PATTERNS = [
    "VID_{date}_{seq:04d}",
    "MOV_{seq:04d}",
    "VIDEO_{date}_{time}",
]

# Media formats to generate
IMAGE_FORMATS = {
    "jpg": {"ext": "jpg", "mime": "image/jpeg", "count": 3500},
    "jpeg": {"ext": "jpeg", "mime": "image/jpeg", "count": 500},
    "JPG": {"ext": "JPG", "mime": "image/jpeg", "count": 300},
    "png": {"ext": "png", "mime": "image/png", "count": 800},
    "PNG": {"ext": "PNG", "mime": "image/png", "count": 100},
    "gif": {"ext": "gif", "mime": "image/gif", "count": 50},
    "webp": {"ext": "webp", "mime": "image/webp", "count": 150},
    "heic": {"ext": "heic", "mime": "image/heic", "count": 200},
}

VIDEO_FORMATS = {
    "mp4": {"ext": "mp4", "mime": "video/mp4", "count": 400},
    "MP4": {"ext": "MP4", "mime": "video/mp4", "count": 50},
    "m4v": {"ext": "m4v", "mime": "video/x-m4v", "count": 30},
    "MOV": {"ext": "MOV", "mime": "video/quicktime", "count": 80},
    "3gp": {"ext": "3gp", "mime": "video/3gpp", "count": 20},
    "avi": {"ext": "avi", "mime": "video/x-msvideo", "count": 10},
}

# RAW formats
RAW_FORMATS = {
    "nef": {"ext": "nef", "mime": "image/x-nikon-nef", "count": 30},
    "cr2": {"ext": "cr2", "mime": "image/x-canon-cr2", "count": 30},
    "arw": {"ext": "arw", "mime": "image/x-sony-arw", "count": 20},
    "dng": {"ext": "dng", "mime": "image/x-adobe-dng", "count": 20},
}

# Sidecar variants
SIDECAR_VARIANTS = [
    ".supplemental-metadata.json",
    ".supplemental-metadat.json",
    ".supplemental-metad.json",
    ".supplemental-meta.json",
    ".supplemental-me.json",
    ".supplemen.json",
    ".suppl.json",
    ".json",
]


class SyntheticDataGenerator:
    """Generates synthetic test data for media scanner."""
    
    def __init__(self, output_dir: Path, total_files_target: int = 10000):
        self.output_dir = Path(output_dir)
        self.total_files_target = total_files_target
        self.media_count = total_files_target // 2
        self.file_counter = 0
        self.base_timestamp = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        self.stats = {
            "total_files": 0,
            "media_files": 0,
            "sidecar_files": 0,
            "albums": 0,
            "user_albums": 0,
            "year_albums": 0,
            "corrupted_files": 0,
            "edited_files": 0,
            "live_photos": 0,
            "tilde_duplicates": 0,
            "windows_duplicates": 0,
            "by_format": {},
        }
    
    def generate(self) -> Dict:
        """Generate complete test dataset."""
        logger.info(f"Generating synthetic test data in: {self.output_dir}")
        logger.info(f"Target: {self.total_files_target} total files (~{self.media_count} media files)")
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        user_album_files = int(self.media_count * 0.6)
        self._generate_user_albums(user_album_files)
        
        year_album_files = self.media_count - self.file_counter
        self._generate_year_albums(year_album_files)
        
        self._generate_edge_cases()
        self._generate_corrupted_files()
        self._create_archive_browser()
        
        self.stats["total_files"] = self._count_files()
        logger.info(f"Generation complete: {json.dumps(self.stats, indent=2)}")
        
        return self.stats
    
    def _generate_user_albums(self, target_files: int) -> None:
        """Generate user-created albums with metadata.json."""
        logger.info(f"Generating user albums (target: {target_files} files)...")
        
        files_per_album = target_files // len(SYNTHETIC_ALBUM_NAMES)
        
        for album_name in SYNTHETIC_ALBUM_NAMES:
            album_dir = self.output_dir / album_name
            album_dir.mkdir(parents=True, exist_ok=True)
            
            self._create_album_metadata(album_dir, album_name)
            self.stats["user_albums"] += 1
            self.stats["albums"] += 1
            
            self._generate_media_files(album_dir, files_per_album)
    
    def _generate_year_albums(self, target_files: int) -> None:
        """Generate year-based albums."""
        logger.info(f"Generating year albums (target: {target_files} files)...")
        
        years = [2020, 2021, 2022, 2023, 2024]
        files_per_year = target_files // len(years)
        
        for year in years:
            album_dir = self.output_dir / f"Photos from {year}"
            album_dir.mkdir(parents=True, exist_ok=True)
            
            self.stats["year_albums"] += 1
            self.stats["albums"] += 1
            
            self._generate_media_files(album_dir, files_per_year, year=year)
    
    def _generate_media_files(self, album_dir: Path, count: int, year: Optional[int] = None) -> None:
        """Generate media files with sidecars."""
        for _ in range(count):
            if self.file_counter >= self.media_count:
                break
            
            format_type, format_info = self._select_format()
            filename = self._generate_filename(format_info["ext"], year)
            file_path = album_dir / filename
            
            if format_type == "image":
                self._create_image_file(file_path, format_info["ext"])
            elif format_type == "video":
                self._create_video_file(file_path, format_info["ext"])
            elif format_type == "raw":
                self._create_raw_file(file_path, format_info["ext"])
            
            if random.random() < 0.9:
                self._create_sidecar(file_path, format_info["mime"])
            
            self.file_counter += 1
            self.stats["media_files"] += 1
            
            ext = format_info["ext"]
            self.stats["by_format"][ext] = self.stats["by_format"].get(ext, 0) + 1
    
    def _select_format(self) -> Tuple[str, Dict]:
        """Select a random format based on distribution."""
        rand = random.random()
        
        total_weight = sum(fmt["count"] for fmt in IMAGE_FORMATS.values())
        total_weight += sum(fmt["count"] for fmt in VIDEO_FORMATS.values())
        total_weight += sum(fmt["count"] for fmt in RAW_FORMATS.values())
        
        cumulative = 0
        
        for ext, info in IMAGE_FORMATS.items():
            cumulative += info["count"]
            if rand < cumulative / total_weight:
                return "image", info
        
        for ext, info in VIDEO_FORMATS.items():
            cumulative += info["count"]
            if rand < cumulative / total_weight:
                return "video", info
        
        for ext, info in RAW_FORMATS.items():
            cumulative += info["count"]
            if rand < cumulative / total_weight:
                return "raw", info
        
        return "image", IMAGE_FORMATS["jpg"]
    
    def _generate_filename(self, ext: str, year: Optional[int] = None) -> str:
        """Generate a synthetic filename."""
        if year:
            date_str = f"{year}{random.randint(1, 12):02d}{random.randint(1, 28):02d}"
        else:
            date_str = f"{random.randint(2020, 2024)}{random.randint(1, 12):02d}{random.randint(1, 28):02d}"
        
        time_str = f"{random.randint(0, 23):02d}{random.randint(0, 59):02d}{random.randint(0, 59):02d}"
        seq = self.file_counter
        
        if ext.lower() in ["mp4", "m4v", "mov", "3gp", "avi"]:
            pattern = random.choice(VIDEO_PATTERNS)
        else:
            pattern = random.choice(IMAGE_PATTERNS)
        
        filename = pattern.format(date=date_str, time=time_str, seq=seq)
        return f"{filename}.{ext}"
    
    def _create_image_file(self, file_path: Path, ext: str) -> None:
        """Create a synthetic image file."""
        if not PIL_AVAILABLE:
            file_path.write_bytes(b"\xff\xd8\xff\xe0" + bytes(random.randint(0, 255) for _ in range(1024)))
            return
        
        width = random.choice([640, 800, 1024, 1920])
        height = random.choice([480, 600, 768, 1080])
        
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)
        
        bg_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        draw.rectangle([(0, 0), (width, height)], fill=bg_color)
        
        for _ in range(random.randint(3, 10)):
            shape_type = random.choice(["rectangle", "ellipse"])
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            
            x1 = random.randint(0, width - 1)
            y1 = random.randint(0, height - 1)
            x2 = random.randint(x1, width)
            y2 = random.randint(y1, height)
            
            if shape_type == "rectangle":
                draw.rectangle([(x1, y1), (x2, y2)], fill=color)
            else:
                draw.ellipse([(x1, y1), (x2, y2)], fill=color)
        
        if ext.lower() in ["jpg", "jpeg"]:
            img.save(file_path, "JPEG", quality=85)
        elif ext.lower() == "png":
            img.save(file_path, "PNG")
        elif ext.lower() == "webp":
            img.save(file_path, "WEBP", quality=85)
        elif ext.lower() == "gif":
            img.save(file_path, "GIF")
        else:
            img.save(file_path, "JPEG")
    
    def _create_video_file(self, file_path: Path, ext: str) -> None:
        """Create a synthetic video file placeholder."""
        if ext.lower() == "mp4" or ext.upper() == "MP4":
            header = b"\x00\x00\x00\x20\x66\x74\x79\x70\x69\x73\x6f\x6d"
        elif ext.lower() == "m4v":
            header = b"\x00\x00\x00\x20\x66\x74\x79\x70\x4d\x34\x56\x20"
        elif ext.upper() == "MOV":
            header = b"\x00\x00\x00\x14\x66\x74\x79\x70\x71\x74\x20\x20"
        elif ext.lower() == "3gp":
            header = b"\x00\x00\x00\x14\x66\x74\x79\x70\x33\x67\x70"
        elif ext.lower() == "avi":
            header = b"\x52\x49\x46\x46\x00\x00\x00\x00\x41\x56\x49\x20"
        else:
            header = b"\x00\x00\x00\x00"
        
        size = random.randint(1024, 10240)
        data = header + bytes(random.randint(0, 255) for _ in range(size))
        file_path.write_bytes(data)
    
    def _create_raw_file(self, file_path: Path, ext: str) -> None:
        """Create a synthetic RAW file placeholder."""
        if ext.lower() == "nef":
            header = b"\x4d\x4d\x00\x2a"
        elif ext.lower() in ["cr2", "arw", "dng"]:
            header = b"\x49\x49\x2a\x00"
        else:
            header = b"\x00\x00\x00\x00"
        
        size = random.randint(5120, 20480)
        data = header + bytes(random.randint(0, 255) for _ in range(size))
        file_path.write_bytes(data)
    
    def _create_sidecar(self, media_path: Path, mime_type: str) -> None:
        """Create JSON sidecar for media file."""
        if random.random() < 0.8:
            sidecar_ext = SIDECAR_VARIANTS[0]
        else:
            sidecar_ext = random.choice(SIDECAR_VARIANTS[1:])
        
        sidecar_path = Path(str(media_path) + sidecar_ext)
        metadata = self._generate_metadata(media_path.name, mime_type)
        
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        self.stats["sidecar_files"] += 1
    
    def _generate_metadata(self, filename: str, mime_type: str) -> Dict:
        """Generate synthetic JSON metadata."""
        days_offset = random.randint(0, 1825)
        taken_time = self.base_timestamp + timedelta(days=days_offset)
        taken_timestamp = int(taken_time.timestamp())
        
        upload_time = taken_time + timedelta(hours=random.randint(1, 72))
        upload_timestamp = int(upload_time.timestamp())
        
        metadata = {
            "title": filename,
            "description": random.choice(SYNTHETIC_DESCRIPTIONS),
            "imageViews": str(random.randint(0, 100)),
            "creationTime": {
                "timestamp": str(upload_timestamp),
                "formatted": upload_time.strftime("%b %d, %Y, %I:%M:%S %p UTC"),
            },
            "photoTakenTime": {
                "timestamp": str(taken_timestamp),
                "formatted": taken_time.strftime("%b %d, %Y, %I:%M:%S %p UTC"),
            },
        }
        
        if random.random() < 0.5:
            lat = random.uniform(-90, 90)
            lon = random.uniform(-180, 180)
            alt = random.uniform(0, 3000)
            
            metadata["geoData"] = {
                "latitude": lat,
                "longitude": lon,
                "altitude": alt,
                "latitudeSpan": 0.0,
                "longitudeSpan": 0.0,
            }
            
            metadata["geoDataExif"] = metadata["geoData"].copy()
        
        if random.random() < 0.7:
            metadata["googlePhotosOrigin"] = {
                "mobileUpload": {
                    "deviceFolder": {
                        "localFolderName": random.choice(DEVICE_FOLDERS)
                    },
                    "deviceType": random.choice(DEVICE_TYPES)
                }
            }
        
        if random.random() < 0.2:
            mod_time = upload_time + timedelta(days=random.randint(1, 30))
            mod_timestamp = int(mod_time.timestamp())
            
            metadata["modificationTime"] = {
                "timestamp": str(mod_timestamp),
                "formatted": mod_time.strftime("%b %d, %Y, %I:%M:%S %p UTC"),
            }
        
        if random.random() < 0.1:
            metadata["favorited"] = True
        if random.random() < 0.05:
            metadata["archived"] = True
        
        return metadata
    
    def _create_album_metadata(self, album_dir: Path, album_name: str) -> None:
        """Create album metadata.json file."""
        created_time = self.base_timestamp + timedelta(days=random.randint(0, 365))
        created_timestamp = int(created_time.timestamp())
        
        metadata = {
            "title": album_name,
            "description": random.choice(SYNTHETIC_DESCRIPTIONS),
            "access": "protected",
            "date": {
                "timestamp": str(created_timestamp),
                "formatted": created_time.strftime("%b %d, %Y, %I:%M:%S %p UTC"),
            }
        }
        
        metadata_path = album_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    def _generate_edge_cases(self) -> None:
        """Generate edge case files for testing."""
        logger.info("Generating edge case files...")
        
        edge_dir = self.output_dir / "Edge Cases Album"
        edge_dir.mkdir(parents=True, exist_ok=True)
        
        self._create_album_metadata(edge_dir, "Edge Cases Album")
        self.stats["user_albums"] += 1
        self.stats["albums"] += 1
        
        # Edited files
        for i in range(5):
            base = f"IMG_EDITED_{i:04d}"
            orig = edge_dir / f"{base}.jpg"
            edited = edge_dir / f"{base}-edited.jpg"
            
            self._create_image_file(orig, "jpg")
            self._create_image_file(edited, "jpg")
            self._create_sidecar(orig, "image/jpeg")
            
            self.stats["edited_files"] += 1
            self.stats["media_files"] += 2
        
        # Tilde duplicates
        for i in range(4):
            base = f"IMG_TILDE_{i:04d}"
            orig = edge_dir / f"{base}.jpg"
            dup2 = edge_dir / f"{base}~2.jpg"
            dup3 = edge_dir / f"{base}~3.jpg"
            
            self._create_image_file(orig, "jpg")
            self._create_image_file(dup2, "jpg")
            self._create_image_file(dup3, "jpg")
            self._create_sidecar(orig, "image/jpeg")
            
            if random.random() < 0.5:
                self._create_sidecar(dup2, "image/jpeg")
            
            self.stats["tilde_duplicates"] += 2
            self.stats["media_files"] += 3
        
        # Windows duplicates
        for i in range(3):
            base = f"IMG_WINDOWS_{i:04d}"
            orig = edge_dir / f"{base}.jpg"
            dup1 = edge_dir / f"{base}(1).jpg"
            dup2 = edge_dir / f"{base}(2).jpg"
            
            self._create_image_file(orig, "jpg")
            self._create_image_file(dup1, "jpg")
            self._create_image_file(dup2, "jpg")
            
            metadata = self._generate_metadata(base + ".jpg", "image/jpeg")
            
            for suffix in ["", "(1)", "(2)"]:
                sidecar = Path(str(orig) + f".supplemental-metadata{suffix}.json")
                with open(sidecar, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2)
                self.stats["sidecar_files"] += 1
            
            self.stats["windows_duplicates"] += 2
            self.stats["media_files"] += 3
        
        # Files without sidecars
        for i in range(10):
            file_path = edge_dir / f"IMG_NO_SIDECAR_{i:04d}.jpg"
            self._create_image_file(file_path, "jpg")
            self.stats["media_files"] += 1
        
        # Orphaned sidecars
        for i in range(5):
            sidecar = edge_dir / f"IMG_ORPHAN_{i:04d}.jpg.supplemental-metadata.json"
            metadata = self._generate_metadata(f"IMG_ORPHAN_{i:04d}.jpg", "image/jpeg")
            with open(sidecar, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
            self.stats["sidecar_files"] += 1
    
    def _generate_corrupted_files(self) -> None:
        """Generate corrupted files for error handling tests."""
        logger.info("Generating corrupted files...")
        
        corrupt_dir = self.output_dir / "Corrupted Files"
        corrupt_dir.mkdir(parents=True, exist_ok=True)
        
        self._create_album_metadata(corrupt_dir, "Corrupted Files")
        
        # Corrupted image
        (corrupt_dir / "corrupted_image.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"CORRUPT")
        
        # Corrupted video
        (corrupt_dir / "corrupted_video.mp4").write_bytes(b"\x00\x00\x00\x20" + b"CORRUPT")
        
        # Empty file
        (corrupt_dir / "empty_file.jpg").write_bytes(b"")
        
        # Invalid JSON sidecar
        (corrupt_dir / "invalid.jpg").write_bytes(b"\xff\xd8\xff\xe0" + bytes(1024))
        (corrupt_dir / "invalid.jpg.supplemental-metadata.json").write_text("{invalid json")
        
        self.stats["corrupted_files"] = 4
        self.stats["media_files"] += 4
    
    def _create_archive_browser(self) -> None:
        """Create archive_browser.html (part of Takeout structure)."""
        html_path = self.output_dir / "archive_browser.html"
        html_content = """<!DOCTYPE html>
<html>
<head><title>Google Photos Archive</title></head>
<body><h1>Synthetic Test Data</h1><p>This is a synthetic Google Photos Takeout structure for testing.</p></body>
</html>"""
        html_path.write_text(html_content, encoding="utf-8")
    
    def _count_files(self) -> int:
        """Count total files in output directory."""
        return sum(1 for _ in self.output_dir.rglob("*") if _.is_file())


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate synthetic test data for media scanner")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory for test data")
    parser.add_argument("--total-files", type=int, default=10000, help="Target total file count")
    
    args = parser.parse_args()
    
    generator = SyntheticDataGenerator(args.output_dir, args.total_files)
    stats = generator.generate()
    
    logger.info("=" * 60)
    logger.info("GENERATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Total files: {stats['total_files']}")
    logger.info(f"Media files: {stats['media_files']}")
    logger.info(f"Sidecar files: {stats['sidecar_files']}")
    logger.info(f"Albums: {stats['albums']} (user: {stats['user_albums']}, year: {stats['year_albums']})")
    logger.info(f"Edge cases: edited={stats['edited_files']}, tilde_dups={stats['tilde_duplicates']}, win_dups={stats['windows_duplicates']}")
    logger.info(f"Corrupted files: {stats['corrupted_files']}")


if __name__ == "__main__":
    main()
