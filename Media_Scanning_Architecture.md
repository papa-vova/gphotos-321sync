# Media Scanning Architecture

**Status:** 🚧 Draft - Ongoing Implementation

This document outlines the architecture for scanning and indexing Google Photos Takeout media files into a local database.

## Overview

The media scanning process builds a comprehensive inventory of all media files, their metadata, album associations, and people tags. The system is designed for parallel processing with efficient resource management.

## Database Schema

### Design Principles

- **No foreign keys** - Simplifies migrations and updates
- **Sized types** - Efficient storage (not TEXT everywhere)
- **Text-based IDs** - Human-readable, sortable by timestamp
- **Nullable fields** - Handles missing data gracefully
- **Batch writes** - Minimizes SQLite lock contention
- **WAL mode** - Allows concurrent reads during scan

### Tables

#### media_items

Primary table storing all media files and their metadata.

```sql
CREATE TABLE media_items (
    -- ID: 17 chars max (YYYYMMDD_HHMMSS_NNN)
    id CHAR(17) PRIMARY KEY,
    
    -- Filenames: reasonable limits
    original_title VARCHAR(255) NOT NULL,  -- From: title (JSON) - original filename
    
    -- File properties
    file_size_bytes BIGINT NOT NULL,  -- File size in bytes
    file_crc32 CHAR(8) NOT NULL,  -- CRC32 checksum (hex string)
    
    -- Media type
    media_type CHAR(5) NOT NULL CHECK(media_type IN ('photo', 'video')),  -- Probed from file content
    file_extension VARCHAR(10) NOT NULL,  -- From filename (e.g., .jpg, .mp4)
    mime_type VARCHAR(50),  -- Probed from file content (e.g., image/jpeg, video/mp4)
    
    -- Timestamps (Unix epoch seconds)
    photo_taken_time INTEGER,  -- From: photoTakenTime.timestamp (JSON) - PRIMARY timestamp
    creation_time INTEGER,  -- From: creationTime.timestamp (JSON) - when uploaded to Google Photos
    modification_time INTEGER,  -- From: modificationTime.timestamp (JSON) - when edited
    photo_last_modified_time INTEGER,  -- From: photoLastModifiedTime.timestamp (JSON)
    
    -- Location data
    geo_latitude REAL,  -- From: geoData.latitude (JSON) - may be user-edited
    geo_longitude REAL,  -- From: geoData.longitude (JSON)
    geo_altitude REAL,  -- From: geoData.altitude (JSON)
    geo_exif_latitude REAL,  -- From: geoDataExif.latitude (JSON) - original from camera
    geo_exif_longitude REAL,  -- From: geoDataExif.longitude (JSON)
    geo_exif_altitude REAL,  -- From: geoDataExif.altitude (JSON)
    geo_user_edited TINYINT DEFAULT 0,  -- Calculated: 1 if geoData != geoDataExif
    
    -- Editing status
    is_edited TINYINT DEFAULT 0,  -- Detected: 1 if filename contains -edited suffix
    original_media_id CHAR(17),  -- Links to original (e.g., original=20200920_131207_000, this edited file=20200920_131207_001)
    has_edited_version TINYINT DEFAULT 0,  -- 1 if edited version exists (set on original when edited found)
    
    -- EXIF data (extracted from media file)
    exif_width SMALLINT,
    exif_height SMALLINT,
    exif_camera_make VARCHAR(50),
    exif_camera_model VARCHAR(50),
    exif_iso SMALLINT,
    exif_exposure_time VARCHAR(20),
    exif_f_number REAL,
    
    -- Google Photos metadata
    image_views INTEGER,  -- From: imageViews (JSON)
    google_photos_url VARCHAR(200),  -- From: url (JSON)
    device_type VARCHAR(30),  -- From: googlePhotosOrigin.mobileUpload.deviceType (JSON)
    device_folder VARCHAR(100),  -- From: googlePhotosOrigin.mobileUpload.deviceFolder.localFolderName (JSON)
    
    -- Organization flags
    archived TINYINT DEFAULT 0,  -- From: archived (JSON)
    trashed TINYINT DEFAULT 0,  -- From: trashed (JSON)
    favorited TINYINT DEFAULT 0,  -- From: favorited (JSON)
    
    -- Processing metadata
    scan_timestamp INTEGER NOT NULL,  -- When this record was created (Unix epoch)
    
    -- Index fields (derived from photo_taken_time)
    year SMALLINT,
    month TINYINT,
    day TINYINT
);

CREATE INDEX idx_media_timestamp ON media_items(photo_taken_time);
CREATE INDEX idx_media_date ON media_items(year, month, day);
CREATE INDEX idx_media_type ON media_items(media_type);
CREATE INDEX idx_media_edited ON media_items(is_edited);
CREATE INDEX idx_media_original ON media_items(original_media_id);
CREATE INDEX idx_media_title ON media_items(original_title);
```

#### media_metadata

Stores metadata sidecar filenames (only for files that have them).

```sql
CREATE TABLE media_metadata (
    media_id CHAR(17) PRIMARY KEY,  -- References media_items.id
    metadata_filename VARCHAR(255) NOT NULL  -- Sidecar filename (e.g., "IMG_20200920_131207.jpg.supplemental-metadata.json" or truncated)
);
```

#### media_descriptions

Stores descriptions/captions (only for files that have them).

```sql
CREATE TABLE media_descriptions (
    media_id CHAR(17) PRIMARY KEY,  -- References media_items.id
    original_description VARCHAR(2048) NOT NULL  -- From: description (JSON) - user-added caption in Google Photos
);
```

#### albums

```sql
CREATE TABLE albums (
    id VARCHAR(64) PRIMARY KEY,  -- Hash or sanitized album name
    original_title VARCHAR(255) NOT NULL UNIQUE,  -- From: title (album metadata.json)
    name VARCHAR(255) NOT NULL,  -- Display name (defaults to original_title, can be changed)
    original_description VARCHAR(2048),  -- From: description (album metadata.json)
    description VARCHAR(2048),  -- User-editable description (defaults to original_description)
    access_level VARCHAR(20),  -- From: access (album metadata.json) - e.g., "protected", "shared"
    creation_timestamp INTEGER,  -- From: date.timestamp (album metadata.json)
    scan_timestamp INTEGER NOT NULL  -- When this album was scanned (Unix epoch)
);

CREATE INDEX idx_album_original_title ON albums(original_title);
CREATE INDEX idx_album_name ON albums(name);
```

#### album_items

```sql
CREATE TABLE album_items (
    album_id VARCHAR(64) NOT NULL,  -- References albums.id
    media_id CHAR(17) NOT NULL,  -- References media_items.id
    PRIMARY KEY (album_id, media_id)
);

CREATE INDEX idx_album_items_album ON album_items(album_id);
CREATE INDEX idx_album_items_media ON album_items(media_id);
```

#### people_tags

```sql
CREATE TABLE people_tags (
    media_id CHAR(17) NOT NULL,  -- References media_items.id
    person_name VARCHAR(100) NOT NULL,  -- From: people[].name (JSON) - supports Unicode
    tag_order TINYINT DEFAULT 0,  -- Order in people array (0-based)
    PRIMARY KEY (media_id, person_name)
);

CREATE INDEX idx_people_media ON people_tags(media_id);
CREATE INDEX idx_people_name ON people_tags(person_name);
```

#### scan_log

```sql
CREATE TABLE scan_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,  -- When log entry was created (Unix epoch)
    level CHAR(7) NOT NULL CHECK(level IN ('INFO', 'WARNING', 'ERROR')),
    message VARCHAR(500) NOT NULL,  -- Log message
    file_path VARCHAR(512),  -- File being processed (if applicable)
    details TEXT  -- Additional context as JSON
);

CREATE INDEX idx_scan_log_timestamp ON scan_log(timestamp);
CREATE INDEX idx_scan_log_level ON scan_log(level);
```

#### scan_metadata

```sql
CREATE TABLE scan_metadata (
    key VARCHAR(50) PRIMARY KEY,  -- e.g., "last_scan_time", "total_files_scanned", "total_errors"
    value VARCHAR(200) NOT NULL  -- String representation of value
);
```

### Type Sizing

| Type | Size | Range | Use Case |
|------|------|-------|----------|
| `TINYINT` | 1 byte | 0-255 | Booleans, small counts |
| `SMALLINT` | 2 bytes | -32,768 to 32,767 | Image dimensions, ISO, year |
| `INTEGER` | 4 bytes | -2B to 2B | Unix timestamps, counts |
| `BIGINT` | 8 bytes | -9E18 to 9E18 | File sizes |
| `REAL` | 4 bytes | ~7 decimal digits | GPS coordinates |
| `CHAR(N)` | N bytes | Fixed length | IDs, CRC32 |
| `VARCHAR(N)` | N bytes + overhead | Variable length | Filenames, URLs, descriptions |

**Storage Estimate:**

- **media_items:** ~450 bytes per item (100k items = ~45 MB)
- **media_metadata:** ~280 bytes per item (50k items with sidecars = ~14 MB)
- **media_descriptions:** ~2100 bytes per item (5k items with descriptions = ~10 MB)
- **Total for 100k media items:** ~69 MB

### Data Integrity Constraints

```sql
ALTER TABLE media_items ADD CONSTRAINT chk_year 
    CHECK (year IS NULL OR (year >= 2000 AND year <= 2200));

ALTER TABLE media_items ADD CONSTRAINT chk_month 
    CHECK (month IS NULL OR (month >= 1 AND month <= 12));

ALTER TABLE media_items ADD CONSTRAINT chk_day 
    CHECK (day IS NULL OR (day >= 1 AND day <= 31));

ALTER TABLE media_items ADD CONSTRAINT chk_geo_lat 
    CHECK (geo_latitude IS NULL OR (geo_latitude >= -90 AND geo_latitude <= 90));

ALTER TABLE media_items ADD CONSTRAINT chk_geo_lon 
    CHECK (geo_longitude IS NULL OR (geo_longitude >= -180 AND geo_longitude <= 180));
```

## Architecture

### Component Diagram

```text
┌─────────────────────────────────────────────────────────────┐
│                     Scan Orchestrator                       │
│  - Discovers all media files                                │
│  - Creates work queue                                       │
│  - Manages worker pool                                      │
│  - Batches results for DB writes                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Worker Pool (N workers)                 │
│  - Process files in parallel                                │
│  - Extract EXIF data                                        │
│  - Parse JSON metadata                                      │
│  - Calculate CRC32                                          │
│  - Detect edited versions                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Batch Writer                             │
│  - Collects results from workers                            │
│  - Batches inserts (e.g., 100 items)                        │
│  - Single transaction per batch                             │
│  - Handles conflicts/duplicates                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLite Database                          │
│  - Write-Ahead Logging (WAL) mode                           │
│  - Concurrent reads during scan                             │
└─────────────────────────────────────────────────────────────┘
```

### Processing Flow

#### Phase 1: Discovery

1. Walk directory tree
2. Identify media files (by extension)
3. Identify JSON sidecars (`.supplemental-metadata.json`)
4. Build file pairs: `[(media, json), ...]`
5. Identify albums (folders with `metadata.json`)

#### Phase 2: Worker Processing

For each `(media_file, json_file)` in queue:

1. Read JSON metadata
2. Extract EXIF from media file
3. Calculate CRC32
4. Determine `media_id` from timestamp
5. Detect if edited version (check `-edited` suffix)
6. Apply user override logic
7. Return `MediaItem` object

#### Phase 3: Batch Writing

1. Collect N results from workers
2. Begin transaction
3. Insert into `media_items`
4. Insert into `media_metadata` (if sidecar exists)
5. Insert into `media_descriptions` (if description exists)
6. Insert into `people_tags` (if people tagged)
7. Insert into `album_items`
8. Commit transaction
9. Log progress

#### Phase 4: Post-Processing

1. Link edited versions to originals (set `original_media_id` and `has_edited_version`)
2. Generate statistics

## User Override Detection

### Location Override

User-edited location takes precedence over original EXIF data.

```python
def detect_geo_override(json_data):
    """
    Detect if user manually edited location.
    
    Returns: (latitude, longitude, altitude, is_user_edited)
    """
    geo = json_data.get('geoData', {})
    geo_exif = json_data.get('geoDataExif', {})
    
    # If no geoDataExif, use geoData (no override possible)
    if not geo_exif:
        return (geo, False)
    
    # If geoData differs from geoDataExif, user edited it
    if (geo.get('latitude') != geo_exif.get('latitude') or
        geo.get('longitude') != geo_exif.get('longitude')):
        return (geo, True)  # User override
    
    # Otherwise, prefer geoDataExif (original)
    return (geo_exif, False)
```

**Storage:**

- Store both `geo_*` (user-edited) and `geo_exif_*` (original)
- Set `geo_user_edited = 1` if they differ
- Sync tools can choose which to use

### Timestamp Priority

```python
def get_best_timestamp(json_data):
    """
    Priority: photoTakenTime > creationTime
    """
    if 'photoTakenTime' in json_data:
        return json_data['photoTakenTime']['timestamp']
    if 'creationTime' in json_data:
        return json_data['creationTime']['timestamp']
    return None
```

### Description Override

```python
def has_user_description(json_data):
    """
    User added description if non-empty.
    """
    desc = json_data.get('description', '').strip()
    return bool(desc)
```

**Other potential overrides:**

- `modificationTime` - Indicates photo was edited
- `favorited` - User explicitly starred the photo
- `archived` - User explicitly archived

## Unique ID Generation

Media IDs are generated from timestamps with collision handling.

**Format:** `YYYYMMDD_HHMMSS_NNN`

**Example:** `20200920_131207_000`

```python
def generate_media_id(timestamp: int, original_filename: str, 
                      existing_ids: set) -> str:
    """
    Generate unique ID based on timestamp.
    
    Args:
        timestamp: Unix epoch seconds
        original_filename: For tie-breaking
        existing_ids: Already used IDs
    
    Returns:
        Unique ID string (17 chars)
    """
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    base_id = dt.strftime("%Y%m%d_%H%M%S")
    
    # Try without suffix first
    if base_id + "_000" not in existing_ids:
        return base_id + "_000"
    
    # Find next available suffix (000-999)
    for suffix in range(1, 1000):
        candidate = f"{base_id}_{suffix:03d}"
        if candidate not in existing_ids:
            return candidate
    
    # Fallback: use filename hash
    hash_suffix = hashlib.md5(original_filename.encode()).hexdigest()[:6]
    return f"{base_id}_{hash_suffix}"
```

**Properties:**

- Sortable by time
- Human-readable
- Handles up to 1000 files per second
- Preserves original filename for re-export matching

## Resource Management

### Configuration

```python
@dataclass
class ScanConfig:
    # Worker settings
    num_workers: int = None  # Auto-detect: min(32, cpu_count + 4)
    batch_size: int = 100    # Items per DB transaction
    queue_size: int = 1000   # Max items in work queue
    
    # Memory limits
    max_memory_mb: int = 2048  # Max memory per worker
    
    # Performance
    enable_exif: bool = True
    enable_crc32: bool = True
    skip_large_files_mb: int = 500  # Skip CRC for files > 500MB
    
    # Database
    db_path: str = "media_inventory.db"
    wal_mode: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "scan.log"
    progress_interval: int = 100  # Log every N files
```

### Auto-Configuration

```python
def auto_configure() -> ScanConfig:
    """Auto-detect optimal settings based on system resources."""
    config = ScanConfig()
    
    # Worker count
    cpu_count = os.cpu_count() or 4
    config.num_workers = min(32, cpu_count + 4)
    
    # Adjust for available memory
    available_mb = psutil.virtual_memory().available // (1024 * 1024)
    if available_mb < 4096:
        config.num_workers = max(2, config.num_workers // 2)
    
    return config
```

**Defaults:**

- **Workers:** `min(32, CPU_count + 4)`
- **Batch size:** 100 items per transaction
- **Queue size:** 1000 items
- **Memory limit:** 2 GB per worker
- **Skip CRC:** Files > 500 MB

## Error Handling

### Error Categories

#### Recoverable Errors (log and continue)

- Missing JSON sidecar
- Corrupted EXIF data
- Invalid JSON format
- CRC calculation failure
- Permission denied on individual file

#### Fatal Errors (stop processing)

- Database connection failure
- Disk full
- Permission denied on database file
- Out of memory

### Error Handling Strategy

```python
class ScanError(Exception):
    """Base exception for scan errors."""
    pass

class RecoverableError(ScanError):
    """Error that allows continuing."""
    pass

class FatalError(ScanError):
    """Error that requires stopping."""
    pass

def process_media_file(file_path, json_path):
    try:
        # Process file
        return media_item
    except JSONDecodeError as e:
        log_warning(f"Invalid JSON for {file_path}: {e}")
        # Continue with EXIF-only data
        return media_item_from_exif_only(file_path)
    except PermissionError as e:
        log_warning(f"Cannot read {file_path}: {e}")
        return None  # Skip this file
    except Exception as e:
        log_error(f"Unexpected error processing {file_path}: {e}")
        return None
```

### Logging Strategy

**Levels:**

- **INFO:** Progress updates, statistics
- **WARNING:** Recoverable errors, missing data
- **ERROR:** Unexpected errors, skipped files

**Destinations:**

- Console (with progress bar)
- Log file (`scan.log`)
- Database (`scan_log` table)

## Implementation Phases

### Phase 1: Basic Scanning (MVP)

- File discovery
- JSON parsing
- Basic metadata extraction
- Database insertion
- Single-threaded processing

### Phase 2: Parallel Processing

- Worker pool implementation
- Batch writing
- Progress tracking
- Resource management

### Phase 3: EXIF Integration

- EXIF extraction (using `exiftool` or `pillow`)
- Timestamp extraction from EXIF
- Camera metadata
- Fallback when JSON missing

### Phase 4: Advanced Features

- CRC32 calculation
- Edited version detection
- Album processing
- People tags extraction

### Phase 5: Optimization

- Resume capability (skip already scanned)
- Incremental updates
- Performance tuning
- Memory optimization

## Performance Targets

**For 100,000 files:**

- **Scan time:** < 10 minutes (with EXIF and CRC32)
- **Memory usage:** < 4 GB total
- **Database size:** ~55 MB
- **CPU usage:** 80-90% during scan

**Bottlenecks:**

- Disk I/O (reading files)
- EXIF extraction (CPU-bound)
- CRC32 calculation (CPU-bound)
- SQLite writes (lock contention)

**Optimizations:**

- Parallel workers (I/O + CPU)
- Batch writes (reduce lock contention)
- Skip CRC for large files
- WAL mode (concurrent reads)

## Open Questions

1. **EXIF library:** Use `exiftool` (external) or `pillow` (Python)?
2. **CRC32:** Always calculate or make optional?
3. **Resume:** Track processed files in DB or separate state file?
4. **Duplicates:** Detect by CRC32 or by filename?
5. **Album detection:** Parse folder structure or rely on `metadata.json`?

## Next Steps

1. Implement database schema creation
2. Build file discovery logic
3. Create worker pool framework
4. Implement JSON parsing
5. Add batch writer
6. Integrate EXIF extraction
7. Add progress tracking and logging
8. Performance testing and optimization

## References

- [Google_Takeout_Structure.md](./Google_Takeout_Structure.md) - Detailed takeout format documentation
- [SQLite WAL Mode](https://www.sqlite.org/wal.html) - Write-Ahead Logging
- [Python multiprocessing](https://docs.python.org/3/library/multiprocessing.html) - Parallel processing
