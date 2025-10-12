# Media Scanning Architecture

**Status:** 🚧 OBSOLETE: first rough draft

This document outlines the architecture for scanning and indexing Google Photos Takeout media files into a local database.

## Overview

The media scanning process builds a comprehensive inventory of all media files, their metadata, album associations, and people tags. The system is designed for parallel processing with efficient resource management.

## Database Schema

### Design Principles

- **No foreign keys** - Simplifies migrations and updates; referential integrity enforced by application
- **Sized types** - PostgreSQL portability (SQLite ignores sizes)
- **Text-based IDs** - Human-readable, sortable by timestamp
- **No NULLs (with exceptions)** - Most fields use defaults (0, 0.0, '') instead of NULL; generated columns (`year`, `month`, `day`) are NULL when timestamp=0
- **Generated columns** - Auto-computed fields (year/month/day, geo_user_edited) using SQLite 3.31+
- **Batch writes** - Minimizes SQLite lock contention
- **WAL mode** - Allows concurrent reads during scan
- **Single writer** - Only writer thread opens DB connection; workers never touch DB

### Tables

#### media_items

Primary table storing all media files and their metadata.

```sql
CREATE TABLE media_items (
    -- ID: 19 chars (YYYYMMDD_HHMMSS_NNN)
    id CHAR(19) PRIMARY KEY,
    
    -- Filenames: reasonable limits
    original_title VARCHAR(255) NOT NULL,  -- From: title (JSON) - original filename
    
    -- File location and identity
    relative_path VARCHAR(1024) NOT NULL,  -- Path inside Takeout (normalized NFKC, e.g., "Photos from 2020/IMG_1234.jpg")
    batch_id VARCHAR(64) NOT NULL,  -- ID of the Takeout export run (for tracking multiple imports)
    
    -- File properties
    file_size_bytes BIGINT NOT NULL,  -- File size in bytes
    file_crc32 CHAR(8) NOT NULL,  -- CRC32 checksum (zero-padded 8-char hex string, e.g., '0a1b2c3d')
    
    -- MIME detection
    mime_suspect SMALLINT DEFAULT 0,  -- 1 if MIME from extension fallback (not magic bytes)
    
    -- Media type
    media_type CHAR(5) NOT NULL,  -- Probed from file content ('photo' or 'video')
    file_extension VARCHAR(10) NOT NULL,  -- From filename (e.g., .jpg, .mp4)
    mime_type VARCHAR(50) NOT NULL,  -- Probed from file content (e.g., image/jpeg, video/mp4, application/octet-stream for unknown)
    
    -- Timestamps (Unix epoch seconds)
    photo_taken_time INTEGER DEFAULT 0,  -- From: photoTakenTime.timestamp (JSON) - PRIMARY timestamp (0 if unknown)
    creation_time INTEGER DEFAULT 0,  -- From: creationTime.timestamp (JSON) - when uploaded to Google Photos
    modification_time INTEGER DEFAULT 0,  -- From: modificationTime.timestamp (JSON) - when edited
    photo_last_modified_time INTEGER DEFAULT 0,  -- From: photoLastModifiedTime.timestamp (JSON)
    
    -- Location data
    has_geo SMALLINT DEFAULT 0,  -- 1 if location data present, 0 if unknown (distinguishes 0.0/0.0 from Equator/Greenwich)
    geo_latitude REAL DEFAULT 0.0,  -- From: geoData.latitude (JSON) - may be user-edited
    geo_longitude REAL DEFAULT 0.0,  -- From: geoData.longitude (JSON)
    geo_altitude REAL DEFAULT 0.0,  -- From: geoData.altitude (JSON)
    has_geo_exif SMALLINT DEFAULT 0,  -- 1 if EXIF location present
    geo_exif_latitude REAL DEFAULT 0.0,  -- From: geoDataExif.latitude (JSON) - original from camera
    geo_exif_longitude REAL DEFAULT 0.0,  -- From: geoDataExif.longitude (JSON)
    geo_exif_altitude REAL DEFAULT 0.0,  -- From: geoDataExif.altitude (JSON)
    geo_user_edited SMALLINT GENERATED ALWAYS AS (
        CASE WHEN has_geo = 1 AND has_geo_exif = 1 
             AND (geo_latitude != geo_exif_latitude OR geo_longitude != geo_exif_longitude)
        THEN 1 ELSE 0 END
    ) STORED  -- 1 if user edited location (geoData differs from geoDataExif)
    
    -- Editing status
    is_edited SMALLINT DEFAULT 0,  -- Detected: 1 if filename contains -edited suffix (localized: -bearbeitet, -modifié, etc.)
    original_media_id CHAR(19) DEFAULT '',  -- Links to original (empty string if not edited)
    has_edited_version SMALLINT DEFAULT 0,  -- 1 if edited version exists (set on original when edited found)
    
    -- EXIF data (extracted from media file)
    exif_width INTEGER DEFAULT 0,  -- Image width in pixels (0 if unknown)
    exif_height INTEGER DEFAULT 0,  -- Image height in pixels
    exif_camera_make VARCHAR(50) DEFAULT '',
    exif_camera_model VARCHAR(50) DEFAULT '',
    exif_iso INTEGER DEFAULT 0,  -- ISO values (0 if unknown)
    exif_exposure_time VARCHAR(20) DEFAULT '',
    exif_f_number REAL DEFAULT 0.0,
    
    -- Google Photos metadata
    image_views INTEGER DEFAULT 0,  -- From: imageViews (JSON)
    google_photos_url VARCHAR(2048) DEFAULT '',  -- From: url (JSON)
    device_type VARCHAR(30) DEFAULT '',  -- From: googlePhotosOrigin.mobileUpload.deviceType (JSON)
    device_folder VARCHAR(100) DEFAULT '',  -- From: googlePhotosOrigin.mobileUpload.deviceFolder.localFolderName (JSON)
    
    -- Organization flags
    archived SMALLINT DEFAULT 0,  -- From: archived (JSON)
    trashed SMALLINT DEFAULT 0,  -- From: trashed (JSON)
    favorited SMALLINT DEFAULT 0,  -- From: favorited (JSON)
    
    -- Processing metadata
    scan_timestamp INTEGER NOT NULL,  -- When this record was created (Unix epoch)
    last_seen_batch_id VARCHAR(64) NOT NULL,  -- Last batch_id that saw this file (for resumability/soft-delete detection)
    status SMALLINT DEFAULT 0,  -- 0=present, 1=missing_in_latest (updated post-scan)
    
    -- Index fields (generated from photo_taken_time, NULL if timestamp is 0)
    year SMALLINT GENERATED ALWAYS AS (
        CASE WHEN photo_taken_time = 0 THEN NULL 
        ELSE CAST(strftime('%Y', photo_taken_time, 'unixepoch') AS INTEGER) END
    ) STORED,
    month SMALLINT GENERATED ALWAYS AS (
        CASE WHEN photo_taken_time = 0 THEN NULL 
        ELSE CAST(strftime('%m', photo_taken_time, 'unixepoch') AS INTEGER) END
    ) STORED,
    day SMALLINT GENERATED ALWAYS AS (
        CASE WHEN photo_taken_time = 0 THEN NULL 
        ELSE CAST(strftime('%d', photo_taken_time, 'unixepoch') AS INTEGER) END
    ) STORED,
    
    -- Constraints
    UNIQUE(batch_id, relative_path),  -- Identity within an import
    CHECK(media_type IN ('photo', 'video')),
    CHECK(length(id) = 19),  -- Enforce 19-char ID format
    CHECK(length(file_crc32) = 8),  -- Enforce 8-char CRC32 hex
    CHECK(geo_latitude >= -90 AND geo_latitude <= 90),
    CHECK(geo_longitude >= -180 AND geo_longitude <= 180)
);

-- Indexes: Create AFTER bulk load for better performance (see "Deferred Index Creation" section)
-- Compound indexes for common query patterns:
-- CREATE INDEX idx_media_timeline ON media_items(media_type, photo_taken_time);  -- Timeline views filtered by type
-- CREATE INDEX idx_media_missing ON media_items(last_seen_batch_id, id);  -- Find files not in latest batch
-- CREATE INDEX idx_media_dedup ON media_items(file_size_bytes, file_crc32);  -- Deduplication
-- CREATE INDEX idx_media_original ON media_items(original_media_id) WHERE original_media_id != '';  -- Edited file lookups
-- Single-column indexes (create only if needed by queries):
-- CREATE INDEX idx_media_timestamp ON media_items(photo_taken_time);
-- CREATE INDEX idx_media_date ON media_items(year, month, day);
-- CREATE INDEX idx_media_suspect ON media_items(mime_suspect) WHERE mime_suspect = 1;  -- Audit suspect MIME types
-- CREATE INDEX idx_media_status ON media_items(status) WHERE status = 1;  -- Find missing files
```

#### media_metadata

Stores metadata sidecar filenames (only for files that have them).

```sql
CREATE TABLE media_metadata (
    media_id CHAR(19) PRIMARY KEY,  -- References media_items.id
    metadata_filename VARCHAR(255) NOT NULL  -- Sidecar filename (e.g., "IMG_20200920_131207.jpg.supplemental-metadata.json" or truncated)
);
```

#### media_descriptions

Stores descriptions/captions (only for files that have them).

```sql
CREATE TABLE media_descriptions (
    media_id CHAR(19) PRIMARY KEY,  -- References media_items.id
    original_description VARCHAR(2048) NOT NULL  -- From: description (JSON) - user-added caption in Google Photos
);
```

#### albums

```sql
CREATE TABLE albums (
    album_id TEXT PRIMARY KEY,  -- UUID (stable across exports)
    title VARCHAR(255) NOT NULL,  -- From: title (album metadata.json) - current value
    description VARCHAR(2048) DEFAULT '',  -- From: description (album metadata.json) - current value
    access_level VARCHAR(20) DEFAULT '',  -- From: access (album metadata.json) - e.g., "protected", "shared"
    creation_timestamp INTEGER DEFAULT 0,  -- From: date.timestamp (album metadata.json)
    scan_timestamp INTEGER NOT NULL,  -- When this album was last seen (Unix epoch)
    CHECK(length(album_id) = 36)  -- Enforce UUID format (with hyphens)
);

-- CREATE INDEX idx_album_title ON albums(title);
```

#### album_aliases

Tracks all known identifiers for an album (folder paths, metadata tuples) to enable reconciliation across exports.

```sql
CREATE TABLE album_aliases (
    album_id TEXT NOT NULL,  -- References albums.album_id (application enforced)
    alias_type VARCHAR(20) NOT NULL,  -- 'takeout_path' or 'meta_tuple'
    alias_value TEXT NOT NULL,  -- Path or "title|created_ts|access" tuple
    first_seen_batch_id VARCHAR(64) NOT NULL,  -- When this alias was first observed
    PRIMARY KEY (alias_type, alias_value)
);

-- CREATE INDEX idx_album_aliases_album ON album_aliases(album_id);
```

#### album_items

```sql
CREATE TABLE album_items (
    album_id TEXT NOT NULL,  -- References albums.album_id (application enforced)
    media_id CHAR(19) NOT NULL,  -- References media_items.id (application enforced)
    PRIMARY KEY (album_id, media_id)
);

-- CREATE INDEX idx_album_items_album ON album_items(album_id);
-- CREATE INDEX idx_album_items_media ON album_items(media_id);
```

#### people_tags

```sql
CREATE TABLE people_tags (
    media_id CHAR(19) NOT NULL,  -- References media_items.id (application enforced)
    tag_order SMALLINT NOT NULL,  -- Order in people array (0-based)
    person_name VARCHAR(100) NOT NULL,  -- From: people[].name (JSON) - supports Unicode
    PRIMARY KEY (media_id, tag_order)
);

-- CREATE INDEX idx_people_media ON people_tags(media_id);
-- CREATE INDEX idx_people_name ON people_tags(person_name);
```

#### scan_log

```sql
CREATE TABLE scan_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,  -- Unix epoch
    level VARCHAR(10) NOT NULL,  -- INFO, WARNING, ERROR
    message VARCHAR(500) NOT NULL,
    file_path VARCHAR(1024),  -- Optional: file being processed (match media_items.relative_path length) (if applicable)
    details TEXT  -- Additional context as JSON
);

-- CREATE INDEX idx_scan_log_timestamp ON scan_log(timestamp);
-- CREATE INDEX idx_scan_log_level ON scan_log(level);
```

#### scan_metadata

```sql
CREATE TABLE scan_metadata (
    key VARCHAR(50) PRIMARY KEY,  -- e.g., "last_scan_time", "total_files_scanned", "total_errors", "current_batch_id"
    value VARCHAR(500) NOT NULL  -- String representation of value
);
```

### Type Sizing

**PostgreSQL Portability:**

This schema uses sized types (`CHAR(N)`, `VARCHAR(N)`, `SMALLINT`, etc.) for **PostgreSQL compatibility**, not for SQLite storage optimization.

| Type | PostgreSQL Behavior | SQLite Behavior | Use Case |
|------|---------------------|-----------------|----------|
| `SMALLINT` | 2 bytes (-32768 to 32767) | Dynamic (1-8 bytes) | Booleans (0/1), year, small counts |
| `INTEGER` | 4 bytes | Dynamic (1-8 bytes) | Unix timestamps, counts |
| `BIGINT` | 8 bytes | Dynamic (1-8 bytes) | File sizes |
| `REAL` | 4 bytes (float) | 8 bytes (double) | GPS coordinates |
| `CHAR(N)` | N bytes (fixed, padded) | Dynamic (no enforcement) | IDs, hashes (exact length) |
| `VARCHAR(N)` | ≤N bytes (enforced limit) | Dynamic (no enforcement) | Filenames, URLs, paths |

**Key Points:**

- **SQLite:** Ignores type sizes; uses dynamic typing based on actual value. Storage depends on value, not declared type.
- **PostgreSQL:** Enforces sizes and types strictly. `VARCHAR(N)` will reject values > N chars.
- **`CHECK` constraints:** Inline constraints work in both databases and provide value validation.

**Storage Estimate:**

- **media_items:** ~550 bytes per item (100k items = ~55 MB)
- **media_metadata:** ~280 bytes per item (50k items with sidecars = ~14 MB)
- **media_descriptions:** ~2100 bytes per item (5k items with descriptions = ~10 MB)
- **Total for 100k media items:** ~79 MB

### Data Integrity Constraints

All `CHECK` constraints are defined **inline** in the `CREATE TABLE` statement (see `media_items` table above) for SQLite compatibility. SQLite does not support `ALTER TABLE ... ADD CONSTRAINT ... CHECK`.

**Constraints enforce:**

- `media_type` must be 'photo' or 'video'
- `id` must be exactly 19 characters
- `file_crc32` must be exactly 8 characters
- `album_id` must be exactly 36 characters (UUID format)
- `geo_latitude` must be -90 to 90
- `geo_longitude` must be -180 to 180

**Note:** Generated columns (`year`, `month`, `day`) are NULL when `photo_taken_time = 0` to avoid storing incorrect dates (1970-01-01).

### App-Level Logic

The application code must handle these on insert:

- **Location flags:** Set `has_geo = 1` when `geoData` present in JSON, `has_geo_exif = 1` when `geoDataExif` present
- **Geo coordinates:** Only populate if `has_geo = 1`, otherwise leave as 0.0

This avoids ambiguity between "unknown location" and "Equator/Greenwich" (0.0, 0.0).

### Deferred Index Creation

**Strategy:** Create indexes **after** bulk load, not in the initial DDL.

**Why:** Creating indexes on empty tables and then inserting millions of rows is slow. Each insert must update all indexes. Creating indexes after bulk load is 5-10x faster.

**Implementation:**

1. **Initial schema:** Run DDL with all `CREATE INDEX` statements commented out (as shown above)
2. **Bulk load:** Insert all media items without indexes
3. **Post-load:** Uncomment and run all `CREATE INDEX` statements

```sql
-- Run these AFTER bulk load completes:
-- Essential compound indexes (create these first):
CREATE INDEX idx_media_timeline ON media_items(media_type, photo_taken_time);
CREATE INDEX idx_media_missing ON media_items(last_seen_batch_id, id);
CREATE INDEX idx_media_dedup ON media_items(file_size_bytes, file_crc32);
CREATE INDEX idx_media_original ON media_items(original_media_id) WHERE original_media_id != '';

-- Partial indexes for audit:
CREATE INDEX idx_media_suspect ON media_items(mime_suspect) WHERE mime_suspect = 1;
CREATE INDEX idx_media_status ON media_items(status) WHERE status = 1;

-- Album indexes:
CREATE INDEX idx_album_title ON albums(title);
CREATE INDEX idx_album_aliases_album ON album_aliases(album_id);  -- Already have PK on (alias_type, alias_value)
CREATE INDEX idx_album_items_album ON album_items(album_id);
CREATE INDEX idx_album_items_media ON album_items(media_id);

-- People tags:
CREATE INDEX idx_people_name ON people_tags(person_name);

-- Optional single-column indexes (create only if queries need them):
-- CREATE INDEX idx_media_timestamp ON media_items(photo_taken_time);
-- CREATE INDEX idx_media_date ON media_items(year, month, day);
-- CREATE INDEX idx_scan_log_timestamp ON scan_log(timestamp);
-- CREATE INDEX idx_scan_log_level ON scan_log(level);
```

**Note:** `UNIQUE` constraints and `PRIMARY KEY` indexes are created immediately (part of table definition).

### SQLite Pragmas Lifecycle

**During bulk import (reduced durability for speed):**

```sql
PRAGMA journal_mode=WAL;           -- Write-Ahead Logging for concurrent reads
PRAGMA synchronous=NORMAL;         -- Reduced durability (faster writes)
PRAGMA temp_store=MEMORY;          -- Keep temp tables in memory
PRAGMA mmap_size=268435456;        -- 256MB memory-mapped I/O (tune based on system)
PRAGMA busy_timeout=5000;          -- Wait up to 5 seconds for locks
PRAGMA cache_size=-64000;          -- 64MB page cache (negative = KB)
```

**After bulk load + index creation (restore durability):**

```sql
PRAGMA synchronous=FULL;           -- Full durability (safer, slower)
PRAGMA journal_mode=WAL;           -- Keep WAL mode
ANALYZE;                           -- Update query planner statistics
```

**Enforcement:** Open database with `check_same_thread=False` and `isolation_level=None` to allow manual transaction control.

**Batch Writer Strategy:**

- Use `BEGIN IMMEDIATE` to grab write lock early for each batch
- Use prepared statements with `executemany` for bulk inserts
- Flush every N items **or** every T milliseconds (whichever comes first)

**Index Creation Strategy:**

During fresh import:

1. Create tables without non-essential indexes
2. Bulk load data
3. Create all indexes
4. Run `ANALYZE` to update query planner statistics

This is much faster than inserting with all indexes active.

## Architecture

### Component Diagram

```text
┌─────────────────────────────────────────────────────────────┐
│                     Scan Orchestrator                       │
│  - Discovers all media files (I/O bound - threads OK)       │
│  - Fills work queue with files to process                   │
│  - Spawns worker threads for light work (JSON parsing)      │
│  - Spawns process pool for heavy work (EXIF, hashing)       │
│  - Spawns batch writer thread                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Work Queue     │ ← Thread-safe FIFO queue
                    │  (files to scan) │
                    └──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Worker Pool (N threads)                    │
│                                                             │
│  Each worker (light work):                                  │
│  1. Get file from work queue (blocks if empty)              │
│  2. Parse JSON metadata (fast, Python)                      │
│  3. Submit heavy work to process pool                       │
│  4. Receive result from process pool                        │
│  5. Combine JSON + heavy work results                       │
│  6. Put result in results queue (non-blocking)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Process Pool (M processes)                     │
│                                                             │
│  Heavy CPU-bound work (avoids GIL):                         │
│  - Extract EXIF data (via exiftool or Pillow)               │
│  - Calculate CRC32 (for deduplication)                      │
│  - Detect edited versions (filename analysis)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                   ┌───────────────────┐
                   │  Results Queue    │ ← Thread-safe FIFO queue
                   │ (processed items) │
                   └───────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Batch Writer (1 thread)                  │
│                                                             │
│  1. Get result from results queue (blocks if empty)         │
│  2. Accumulate results into batch                           │
│  3. When batch size reached (e.g., 100 items):              │
│     - Begin transaction                                     │
│     - Insert into media_items                               │
│     - Insert into media_metadata (if sidecar exists)        │
│     - Insert into media_descriptions (if description exists)│
│     - Insert into people_tags (if people tagged)            │
│     - Insert into album_items                               │
│     - Commit transaction                                    │
│  4. Log progress                                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLite Database                          │
│  - Write-Ahead Logging (WAL) mode                           │
│  - Concurrent reads during scan                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Points:**

- **Work Queue:** Thread-safe queue of files waiting to be processed
- **Results Queue:** Thread-safe queue of processed results waiting to be written
- **Thread Pool (N threads):** Light work - JSON parsing, coordination
- **Process Pool (M processes):** Heavy CPU-bound work - EXIF extraction, hashing (avoids Python GIL)
- **Non-blocking:** Workers don't wait for database writes; batch writer doesn't wait for workers
- **Parallelism:** N workers + M processes work concurrently; 1 batch writer serializes DB writes

**Why Process Pool for Heavy Work?**

Python's Global Interpreter Lock (GIL) prevents true parallel execution of Python bytecode in threads. CPU-intensive operations like EXIF parsing and CRC32 calculation can bottleneck with threads. Using a process pool bypasses the GIL, allowing true parallel CPU utilization.

### Processing Flow

#### Phase 1: Discovery (Orchestrator Thread)

1. Walk directory tree
2. Identify media files (by extension)
3. Identify JSON sidecars (`.supplemental-metadata.json`)
4. Build file pairs: `[(media_file, json_file), ...]`
5. Identify albums (folders with `metadata.json`)
6. Put each file pair into **work queue**
7. Spawn N worker threads
8. Spawn 1 batch writer thread

#### Phase 2: Worker Processing (N Worker Threads + M Processes)

**Worker Thread Loop (light work):**

```python
while True:
    # 1. Get work (blocks if queue empty)
    file_pair = work_queue.get()
    if file_pair is None:  # Shutdown signal
        break
    
    media_file, json_file = file_pair
    
    # 2. Parse JSON (fast, Python)
    json_data = parse_json(json_file) if json_file else {}
    
    # 3. Submit heavy work to process pool
    future = process_pool.submit(extract_heavy_data, media_file)
    heavy_data = future.result()  # Wait for completion
    
    # 4. Extract timestamp
    timestamp = extract_timestamp(json_data) or int(os.path.getmtime(media_file))
    
    # 5. Combine results (NO media_id - writer generates it)
    result = {
        'timestamp': timestamp,  # Writer will generate ID from this
        'original_title': json_data.get('title'),
        'relative_path': get_relative_path(media_file),
        'batch_id': current_batch_id,
        'file_size_bytes': heavy_data['file_size'],
        'file_crc32': heavy_data['crc32'],
        'media_type': heavy_data['media_type'],  # Required: 'photo' or 'video'
        'mime_type': heavy_data['mime_type'],    # Required: probed MIME type
        'mime_suspect': heavy_data['mime_suspect'],  # 1 if from extension fallback
        'is_edited': heavy_data['is_edited'],
        'exif_data': heavy_data['exif'],
        # ... JSON fields
        'metadata_filename': json_file.name if json_file else None,
        'description': json_data.get('description'),
        'people': json_data.get('people', []),
        'last_seen_batch_id': current_batch_id,
        'original_filename_for_linking': heavy_data['original_filename'],  # For edited file linking
    }
    
    # 6. Send to batch writer (non-blocking)
    results_queue.put(result)
```

**Process Pool Function (heavy work):**

```python
def extract_heavy_data(media_file, config):
    """
    CPU-bound work executed in separate process (avoids GIL).
    """
    mime_type, mime_suspect = probe_mime_type(media_file)  # Three-tier fallback
    media_type = 'video' if mime_type.startswith('video/') else 'photo'
    file_size = os.path.getsize(media_file)
    
    # EXIF only for images (not videos)
    exif = None
    if media_type == 'photo':
        exif = extract_exif(media_file)  # via exiftool or Pillow
    
    # Detect edited suffix and extract original filename
    is_edited, original_filename = detect_edited_suffix(media_file)
    
    return {
        'file_size': file_size,
        'crc32': calculate_crc32(media_file),  # Always calculate (fast) - returns zero-padded 8-char hex
        'mime_type': mime_type,
        'mime_suspect': mime_suspect,  # 1 if from extension fallback
        'media_type': media_type,
        'exif': exif,
        'is_edited': is_edited,  # Boolean: 1 if edited, 0 if not
        'original_filename': original_filename,  # For linking edited -> original
    }

def calculate_crc32(file_path: str) -> str:
    """
    Calculate CRC32 checksum of file.
    
    Returns:
        Zero-padded 8-character hex string (e.g., '0a1b2c3d')
    """
    crc = 0
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            crc = zlib.crc32(chunk, crc)
    return f'{crc & 0xffffffff:08x}'  # Zero-padded 8-char hex
```

#### Phase 3: Batch Writing (1 Batch Writer Thread - SOLE WRITER)

**Critical:** Only the writer thread opens a write connection. Workers never touch the DB.

```python
# Initialize writer thread (ONLY component that writes to DB)
def init_writer_thread(db_path: str, results_queue: Queue):
    """
    Single writer thread - the ONLY component that opens a write connection.
    Workers never touch the database.
    """
    # Open connection with manual transaction control
    conn = sqlite3.connect(
        db_path,
        check_same_thread=False,  # Allow use across threads (writer only)
        isolation_level=None       # Manual transaction control
    )
    conn.execute("PRAGMA journal_mode=WAL")
    
    batch = []
    while True:
        # 1. Get result (blocks if queue empty)
        result = results_queue.get()
        if result is None:  # Shutdown signal
            if batch:
                write_batch(conn, batch)  # Flush remaining
            break
        
        # 2. Accumulate
        batch.append(result)
        
        # 3. Write when batch full
        if len(batch) >= BATCH_SIZE:  # e.g., 100
            write_batch(conn, batch)
            batch = []
    
    conn.close()

def write_batch(conn, batch):
    """
    Write batch with BEGIN IMMEDIATE per batch.
    Writer generates IDs and inserts with retry.
    """
    conn.execute('BEGIN IMMEDIATE')  # Grab write lock early
    
    try:
        for item in batch:
            # Generate ID and insert with retry on collision
            media_id = insert_media_with_retry(conn, item)
            
            # Use the returned media_id for all child inserts
            # Insert into media_metadata (if sidecar exists)
            if item.get('metadata_filename'):
                conn.execute(
                    "INSERT INTO media_metadata(media_id, metadata_filename) VALUES (?, ?)",
                    (media_id, item['metadata_filename'])
                )
            
            # Insert into media_descriptions (if description exists)
            if item.get('description'):
                conn.execute(
                    "INSERT INTO media_descriptions(media_id, original_description) VALUES (?, ?)",
                    (media_id, item['description'])
                )
            
            # Insert into people_tags (if people tagged)
            for i, person in enumerate(item.get('people', [])):
                # Handle both dict {'name': 'Alice'} and string 'Alice' formats
                person_name = person['name'] if isinstance(person, dict) else person
                conn.execute(
                    "INSERT INTO people_tags(media_id, tag_order, person_name) VALUES (?, ?, ?)",
                    (media_id, i, person_name)
                )
            
            # Insert into album_items (determined from folder structure)
            if item.get('album_id'):
                conn.execute(
                    "INSERT INTO album_items(album_id, media_id) VALUES (?, ?)",
                    (item['album_id'], media_id)
                )
        
        conn.execute('COMMIT')
        log_progress(len(batch))
    except Exception as e:
        conn.execute('ROLLBACK')
        log_error(f"Batch write failed: {e}")
        raise
```

**Enforcement:**

- Workers never open DB connections
- Only writer thread has `conn` object
- `check_same_thread=False` + `isolation_level=None` for manual control
- `BEGIN IMMEDIATE` per batch to grab write lock early

#### Phase 4: Post-Processing (After All Workers Complete)

1. **Link edited versions to originals:**
   - Find pairs by matching filenames (handle localized suffixes: `-edited`, `-bearbeitet`, `-modifié`, etc.)
   - Set `original_media_id` on edited file in `media_items`
   - Set `has_edited_version = 1` on original file
2. **Mark missing files (resumability):**
   - Query all items where `last_seen_batch_id != current_batch_id`
   - Update `status = 1` for files not in current batch (deleted/moved)
3. **Generate statistics:** Total files, errors, duplicates detected, etc.

## User Override Detection

### Location Override

User-edited location takes precedence over original EXIF data.

**Logic:** Store both sets of coordinates; database computes `geo_user_edited` via generated column.

```python
def extract_geo_data(json_data):
    """
    Extract geo coordinates and determine presence flags.
    
    Returns: dict with geo fields for database insertion
    """
    geo = json_data.get('geoData', {})
    geo_exif = json_data.get('geoDataExif', {})
    
    # Extract coordinates (may be None if key missing)
    geo_lat = geo.get('latitude')
    geo_lon = geo.get('longitude')
    geo_alt = geo.get('altitude', 0.0)
    
    geo_exif_lat = geo_exif.get('latitude')
    geo_exif_lon = geo_exif.get('longitude')
    geo_exif_alt = geo_exif.get('altitude', 0.0)
    
    # Determine presence: exists AND non-zero
    has_geo = 1 if (geo_lat is not None and geo_lon is not None and 
                    (geo_lat != 0.0 or geo_lon != 0.0)) else 0
    
    has_geo_exif = 1 if (geo_exif_lat is not None and geo_exif_lon is not None and 
                         (geo_exif_lat != 0.0 or geo_exif_lon != 0.0)) else 0
    
    return {
        'has_geo': has_geo,
        'geo_latitude': geo_lat if has_geo else 0.0,
        'geo_longitude': geo_lon if has_geo else 0.0,
        'geo_altitude': geo_alt if has_geo else 0.0,
        
        'has_geo_exif': has_geo_exif,
        'geo_exif_latitude': geo_exif_lat if has_geo_exif else 0.0,
        'geo_exif_longitude': geo_exif_lon if has_geo_exif else 0.0,
        'geo_exif_altitude': geo_exif_alt if has_geo_exif else 0.0,
    }
```

**Database computes user edit:**

```sql
geo_user_edited GENERATED ALWAYS AS (
    CASE WHEN has_geo = 1 AND has_geo_exif = 1 
         AND (geo_latitude != geo_exif_latitude OR geo_longitude != geo_exif_longitude)
    THEN 1 ELSE 0 END
) STORED
```

**Result:**

- `geo_user_edited = 1` only if both exist, both non-zero, AND coordinates differ
- `geo_user_edited = 0` if either missing, or both present but identical
- Avoids false positives from None/0.0 comparisons

**Storage:**

- Store both `geo_*` (potentially user-edited) and `geo_exif_*` (original from camera)
- Database automatically sets `geo_user_edited` flag
- Sync tools can choose which coordinates to use

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

### Edited File Detection

Google Takeout uses localized suffixes for edited files.

**Extension-agnostic** - works for photos AND videos.

```python
# Known localized edited suffixes
EDITED_SUFFIXES = [
    '-edited',      # English
    '-bearbeitet',  # German
    '-modifié',     # French
    '-modificato',  # Italian
    '-editado',     # Spanish/Portuguese
    '-編集済み',     # Japanese
    '-편집됨',       # Korean
    '-已編輯',       # Chinese Traditional
    '-已编辑',       # Chinese Simplified
]

def detect_edited_suffix(filename: str) -> tuple[bool, str]:
    """
    Detect if filename has edited suffix (localized).
    Extension-agnostic: works for .jpg, .mp4, .mov, etc.
    
    Returns:
        (is_edited, original_filename)
    """
    name, ext = os.path.splitext(filename)
    
    for suffix in EDITED_SUFFIXES:
        if name.endswith(suffix):
            original_name = name[:-len(suffix)] + ext
            return (True, original_name)
    
    return (False, filename)

# Examples:
# IMG_1234-edited.jpg → (True, "IMG_1234.jpg")
# VID_5678-bearbeitet.mp4 → (True, "VID_5678.mp4")
# IMG_9999.jpg → (False, "IMG_9999.jpg")
```

**Sidecar Matching:**

Edited files share the same JSON sidecar as the original:

- `IMG_1234.jpg` → `IMG_1234.jpg.supplemental-metadata.json`
- `IMG_1234-edited.jpg` → `IMG_1234.jpg.supplemental-metadata.json` (same file!)
- `VID_5678.mp4` → `VID_5678.mp4.supplemental-metadata.json`
- `VID_5678-edited.mp4` → `VID_5678.mp4.supplemental-metadata.json` (same file!)

Must map edited file to original's sidecar.

### Sidecar Lookup Map (Discovery Phase)

**Critical:** Build sidecar lookup map during discovery for O(1) matching. **Do not** probe filesystem per-file.

Google Takeout truncates long sidecar filenames. Map must handle all documented variants.

**Truncation patterns:**

- Full: `.supplemental-metadata.json`
- Truncated: `.supplemental-metadat.json` (one char shorter)
- Truncated: `.supplemental-metad.json` (several chars shorter)
- Truncated: `.supplemental-me.json` (heavily truncated)
- Numbered duplicates: `photo.jpg(1).json` (not `photo.jpg(1).supplemental-metadata.json`)

**Build map during discovery (Phase 1):**

```python
def build_sidecar_map(takeout_root: str) -> dict:
    """
    Build sidecar lookup map during discovery.
    Returns: dict mapping media_path -> json_path
    """
    sidecar_map = {}
    
    for root, dirs, files in os.walk(takeout_root):
        for file in files:
            if '.json' in file and file != 'metadata.json':
                json_path = os.path.join(root, file)
                
                # Try all known sidecar patterns
                suffixes = [
                    '.supplemental-metadata.json',
                    '.supplemental-metadat.json',
                    '.supplemental-metad.json',
                    '.supplemental-me.json',
                    '.json',  # For numbered duplicates
                ]
                
                for suffix in suffixes:
                    if file.endswith(suffix):
                        media_name = file[:-len(suffix)]
                        media_path = os.path.join(root, media_name)
                        sidecar_map[media_path] = json_path
                        break
    
    return sidecar_map
```

**Use map in workers (O(1) lookup):**

```python
# In worker loop
json_path = sidecar_map.get(media_file)  # O(1) - no filesystem probing!
json_data = parse_json(json_path) if json_path else {}
```

**Performance:**

- **Without map:** 100k files × 5 `os.path.exists()` = 500k filesystem operations
- **With map:** O(1) dict lookup per file = 10-100x faster

### MIME Type Validation

Flag unknown or ambiguous MIME types for audit.

```python
def probe_mime_type(file_path: str) -> tuple[str, bool]:
    """
    Probe file's MIME type using three-tier fallback.
    
    Returns:
        (mime_type, mime_suspect) tuple:
        - mime_type: MIME type string (always non-null)
        - mime_suspect: True if from extension fallback (not magic bytes)
    """
    mime_suspect = False
    
    # Tier 1: Try python-magic (libmagic)
    try:
        import magic
        mime = magic.from_file(file_path, mime=True)
        if mime and mime not in ['application/octet-stream', 'text/plain']:
            return (mime, False)  # Success from magic bytes
    except (ImportError, Exception) as e:
        log_debug(f"Magic detection unavailable/failed for {file_path}: {e}")
    
    # Tier 2: Extension mapping
    ext = os.path.splitext(file_path)[1].lower()
    if ext in EXTENSION_TO_MIME:
        mime_suspect = True
        log_warning(f"MIME from extension fallback for {file_path}: {ext}")
        return (EXTENSION_TO_MIME[ext], True)
    
    # Tier 3: Unknown sentinel
    mime_suspect = True
    log_warning(f"Unknown MIME type for {file_path}, using sentinel")
    return ('application/octet-stream', True)

EXTENSION_TO_MIME = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.heic': 'image/heic',
    '.mp4': 'video/mp4',
    '.mov': 'video/quicktime',
    '.avi': 'video/x-msvideo',
    # ... more mappings
}
```

**Audit Report:**

Files with unknown MIME types should be logged to `scan_log` with level `WARNING` for manual review.

### Album Reconciliation

Albums are reconciled across exports using a UUID-based identity system with aliases.

```python
import uuid

def reconcile_album(album_path: str, metadata: dict, current_batch_id: str, db_cursor) -> str:
    """
    Find or create album, returning stable album_id (UUID).
    
    Args:
        album_path: Relative path to album folder
        metadata: Parsed album metadata.json
        current_batch_id: Current import batch ID
        db_cursor: Database cursor
    
    Returns:
        album_id (UUID string)
    """
    # Build metadata tuple for matching
    title = metadata.get('title', '')
    created_ts = str(metadata.get('date', {}).get('timestamp', ''))
    access = metadata.get('access', '')
    meta_tuple = f"{title}|{created_ts}|{access}"
    
    # Match order: metadata tuple → path → create new
    
    # 1. Try metadata tuple match
    result = db_cursor.execute(
        "SELECT album_id FROM album_aliases WHERE alias_type = 'meta_tuple' AND alias_value = ?",
        (meta_tuple,)
    ).fetchone()
    
    if result:
        album_id = result[0]
        # Update album with latest values
        db_cursor.execute(
            "UPDATE albums SET title = ?, description = ?, access_level = ?, scan_timestamp = ? WHERE album_id = ?",
            (title, metadata.get('description'), access, int(time.time()), album_id)
        )
        return album_id
    
    # 2. Try path match
    result = db_cursor.execute(
        "SELECT album_id FROM album_aliases WHERE alias_type = 'takeout_path' AND alias_value = ?",
        (album_path,)
    ).fetchone()
    
    if result:
        album_id = result[0]
        # Update album and add new meta_tuple alias
        db_cursor.execute(
            "UPDATE albums SET title = ?, description = ?, access_level = ?, scan_timestamp = ? WHERE album_id = ?",
            (title, metadata.get('description'), access, int(time.time()), album_id)
        )
        db_cursor.execute(
            "INSERT OR IGNORE INTO album_aliases (album_id, alias_type, alias_value, first_seen_batch_id) VALUES (?, 'meta_tuple', ?, ?)",
            (album_id, meta_tuple, current_batch_id)
        )
        return album_id
    
    # 3. Create new album
    album_id = str(uuid.uuid4())
    db_cursor.execute(
        "INSERT INTO albums (album_id, title, description, access_level, creation_timestamp, scan_timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (album_id, title, metadata.get('description'), access, metadata.get('date', {}).get('timestamp'), int(time.time()))
    )
    
    # Insert both aliases
    db_cursor.execute(
        "INSERT INTO album_aliases (album_id, alias_type, alias_value, first_seen_batch_id) VALUES (?, 'takeout_path', ?, ?)",
        (album_id, album_path, current_batch_id)
    )
    db_cursor.execute(
        "INSERT INTO album_aliases (album_id, alias_type, alias_value, first_seen_batch_id) VALUES (?, 'meta_tuple', ?, ?)",
        (album_id, meta_tuple, current_batch_id)
    )
    
    return album_id
```

**Why this works:**

- **Stable identity:** Album UUID never changes, even if title or path changes
- **Deterministic matching:** Metadata tuple match is preferred (more stable than path)
- **Path fallback:** Handles cases where metadata changed but path didn't
- **Alias tracking:** All observed identifiers are preserved for future reconciliation

## Unique ID Generation

Media IDs are generated from timestamps **in the writer thread** with collision handling.

**Format:** `YYYYMMDD_HHMMSS_NNN`

**Example:** `20200920_131207_000`

**Design:** Workers pass timestamp to writer; writer generates ID and retries on collision.

```python
def insert_media_with_retry(db_conn, item: dict, max_retries: int = 1000) -> str:
    """
    Generate ID and insert media item with DB-enforced uniqueness.
    Retry with incremented suffix on collision.
    
    Called ONLY by writer thread.
    
    Args:
        db_conn: Database connection
        item: Media item dict (contains 'timestamp', not 'media_id')
        max_retries: Max suffix attempts (000-999)
    
    Returns:
        Generated media_id
    
    Raises:
        RuntimeError: If all 1000 suffixes exhausted (extremely rare)
    """
    # Generate base ID from timestamp
    timestamp = item['timestamp']
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    base_id = dt.strftime("%Y%m%d_%H%M%S")
    
    # Try suffixes 000-999 until unique
    for n in range(max_retries):
        media_id = f"{base_id}_{n:03d}"
        try:
            db_conn.execute(
                "INSERT INTO media_items(id, /* all other cols */) VALUES (?, /* ... */)",
                (media_id, /* ... */)
            )
            return media_id  # Success
        except sqlite3.IntegrityError as e:
            if 'UNIQUE constraint failed' in str(e) and 'id' in str(e):
                continue  # Try next suffix
            else:
                raise  # Different integrity error
    
    raise RuntimeError(f"ID overflow: exhausted all suffixes for {base_id} (>1000 files in same second)")
```

**Properties:**

- **Length:** Always 19 chars (`YYYYMMDD_HHMMSS_NNN`)
- **Sortable:** By time (lexicographic sort = chronological sort)
- **Human-readable:** Date/time visible in ID
- **Collision handling:** Supports up to 1000 files per second (000-999 suffix)
- **Error on overflow:** Raises `ValueError` if > 1000 files/second (extremely rare)

## Resource Management

### Configuration

```python
@dataclass
class ScanConfig:
    # Worker settings
    num_threads: int = None  # Auto-detect: min(32, cpu_count + 4)
    num_processes: int = None  # Auto-detect: min(8, cpu_count)
    batch_size: int = 100    # Items per DB transaction
    work_queue_size: int = 1000   # Max items in work queue
    results_queue_size: int = 1000  # Max items in results queue
    
    # Batch ID
    batch_id: str = None  # Auto-generate: timestamp or UUID
    
    # Memory limits
    max_memory_mb: int = 2048  # Max memory per worker
    
    # Performance
    enable_exif: bool = True
    
    # Database
    db_path: str = "media_inventory.db"
    wal_mode: bool = True
    defer_indexes: bool = True  # Create indexes after bulk load
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "scan.log"
    progress_interval: int = 100  # Log every N files
```

### Batch ID Generation and Validation

**Critical:** `batch_id` identifies a **single Google Takeout export session**, not a scanner run. It must be stable across scanner restarts to enable resumability.

**Source:** Derived from Takeout archive filenames (e.g., `takeout-20231015-001.zip` → `batch_id = "takeout_20231015"`).

```python
import re
import glob
from pathlib import Path

def validate_and_generate_batch_id(takeout_folder: str) -> str:
    """
    Validate that folder contains archives from a SINGLE Takeout export.
    Generate stable batch_id from archive names.
    
    Args:
        takeout_folder: Path to folder containing takeout-*.zip files
    
    Returns:
        batch_id (e.g., "takeout_20231015")
    
    Raises:
        ValueError: If no archives found or mixed exports detected
    """
    # Find all takeout zip files
    zip_pattern = os.path.join(takeout_folder, "takeout-*.zip")
    zip_files = glob.glob(zip_pattern)
    
    if not zip_files:
        raise ValueError(f"No takeout-*.zip files found in {takeout_folder}")
    
    # Extract export dates from filenames
    # Expected format: takeout-YYYYMMDD-NNN.zip
    export_dates = set()
    for zip_file in zip_files:
        basename = os.path.basename(zip_file)
        match = re.match(r'takeout-(\d{8})-(\d{3})\.zip', basename)
        if match:
            export_dates.add(match.group(1))  # YYYYMMDD
        else:
            raise ValueError(f"Invalid Takeout archive name: {basename}. "
                           f"Expected format: takeout-YYYYMMDD-NNN.zip")
    
    # Ensure all archives are from same export
    if len(export_dates) == 0:
        raise ValueError(f"No valid Takeout archives found in {takeout_folder}")
    
    if len(export_dates) > 1:
        raise ValueError(
            f"Mixed Takeout exports detected in {takeout_folder}. "
            f"Found dates: {sorted(export_dates)}. "
            f"Folder must contain archives from a SINGLE export only."
        )
    
    # Generate stable batch_id
    export_date = export_dates.pop()
    batch_id = f"takeout_{export_date}"
    
    return batch_id
```

**Usage:**

```python
# At startup, before scanning
batch_id = validate_and_generate_batch_id("/path/to/takeout_folder")
config.batch_id = batch_id

# batch_id is now stable across restarts:
# - Same folder → same batch_id
# - Enables resumability and incremental scans
```

**Why this matters:**

- **Resumability:** If scanner crashes, restart uses same `batch_id` to detect incomplete scan
- **Incremental updates:** Can detect which files are new/changed since last scan
- **Multi-export tracking:** Different Takeout exports get different `batch_id` values

### Auto-Configuration

```python
def auto_configure(takeout_folder: str) -> ScanConfig:
    """Auto-detect optimal settings based on system resources."""
    config = ScanConfig()
    
    # Thread count (I/O + coordination)
    cpu_count = os.cpu_count() or 4
    config.num_threads = min(32, cpu_count + 4)
    
    # Process count (CPU-bound work)
    config.num_processes = min(8, cpu_count)
    
    # Adjust for available memory
    available_mb = psutil.virtual_memory().available // (1024 * 1024)
    if available_mb < 4096:
        config.num_threads = max(2, config.num_threads // 2)
        config.num_processes = max(2, config.num_processes // 2)
    
    # Generate stable batch ID from Takeout archive names
    config.batch_id = validate_and_generate_batch_id(takeout_folder)
    
    return config
```

**Defaults:**

- **Threads:** `min(32, CPU_count + 4)` for I/O and coordination
- **Processes:** `min(8, CPU_count)` for CPU-bound work (EXIF, hashing)
- **Batch size:** 100 items per transaction
- **Work queue size:** 1000 items (limits memory usage)
- **Results queue size:** 1000 items (prevents workers from getting too far ahead)
- **Memory limit:** 2 GB per worker
- **CRC32:** Always calculated (fast, both photos and videos)

**Queue Sizing:**

- **Small queues (100-500):** Lower memory usage, workers may block waiting for space
- **Large queues (1000+):** Higher memory usage, better throughput

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

- Localized edited version detection
- Album processing
- People tags extraction

### Phase 5: Optimization & Resumability

- Resume capability via `last_seen_batch_id`
- Incremental updates
- Deferred index creation
- Process pool for CPU-bound work
- Memory optimization

## Duplicate Handling

### Definition

**A duplicate is defined as:** Two media items with identical binary content.

**Detection criteria:**

- `file_size_bytes` are equal AND
- `file_crc32` are equal

All other fields may differ (path, filename, batch_id, albums, metadata).

### Storage Strategy

**All files are stored during import**, including duplicates. This preserves:

- Complete album membership information
- All file locations across exports
- Metadata variations between duplicates

### Use Cases

#### Use Case 1: Album Membership (No Action Needed)

**Scenario:** Same photo appears in multiple albums

```text
Photo A (crc32: abc123) in:
  - Album: "Vacation 2020"
  - Album: "Best Photos"
  - Album: "Family Memories"
```

**Behavior:** Each album reference is preserved in `album_items` table. Whether these point to one `media_items` row or multiple rows with same CRC32 doesn't matter for viewing albums.

**Action:** None required. Duplicates are transparent to album browsing.

#### Use Case 2: Space Optimization (Deduplication)

**Scenario:** Want to store one physical file, link from multiple albums

**Process:**

1. **Find duplicate groups:**

```sql
SELECT file_size_bytes, file_crc32, 
       COUNT(*) as duplicate_count,
       GROUP_CONCAT(id, ', ') as all_ids,
       GROUP_CONCAT(relative_path, '; ') as all_paths
FROM media_items
GROUP BY file_size_bytes, file_crc32
HAVING duplicate_count > 1
ORDER BY duplicate_count DESC;
```

2. **For each duplicate group, choose canonical version:**

```sql
-- Pick the first one (by ID) as canonical
SELECT MIN(id) as canonical_id, file_crc32
FROM media_items
GROUP BY file_size_bytes, file_crc32
HAVING COUNT(*) > 1;
```

3. **Consolidate album memberships:**

```sql
-- Move all album references to canonical version
UPDATE album_items 
SET media_id = :canonical_id
WHERE media_id IN (
    SELECT id FROM media_items 
    WHERE file_crc32 = :target_crc32 
    AND id != :canonical_id
);
```

4. **Mark or delete duplicates:**

```sql
-- Option A: Mark as duplicate (keep metadata)
UPDATE media_items 
SET is_duplicate = 1, canonical_media_id = :canonical_id
WHERE file_crc32 = :target_crc32 AND id != :canonical_id;

-- Option B: Delete duplicates (lose metadata)
DELETE FROM media_items 
WHERE file_crc32 = :target_crc32 AND id != :canonical_id;
```

5. **Physical file system:** Delete duplicate files, keep only canonical version

### Schema Support for Deduplication

**Optional fields** (add if implementing space optimization):

```sql
ALTER TABLE media_items ADD COLUMN is_duplicate SMALLINT DEFAULT 0;
ALTER TABLE media_items ADD COLUMN canonical_media_id CHAR(19);
CREATE INDEX idx_media_canonical ON media_items(canonical_media_id);
```

**Queries:**

```sql
-- Get all unique photos (excluding duplicates)
SELECT * FROM media_items WHERE is_duplicate = 0;

-- Get canonical version of a duplicate
SELECT * FROM media_items WHERE id = (
    SELECT canonical_media_id FROM media_items WHERE id = :duplicate_id
);

-- Count total duplicates and space savings
SELECT 
    COUNT(*) as duplicate_files,
    SUM(file_size_bytes) as wasted_bytes,
    SUM(file_size_bytes) / 1024 / 1024 / 1024 as wasted_gb
FROM media_items 
WHERE is_duplicate = 1;
```

### Notes

- **CRC32 collision risk:** With small libraries (<100k files), false positives are rare. Manual verification recommended before deleting files.
- **Metadata conflicts:** If duplicates have different descriptions/tags, merge or choose preferred version before consolidation.
- **Reversibility:** Keep `is_duplicate` flag instead of deleting to preserve ability to restore duplicates.

## Performance Targets

**For 100,000 files (50% photos, 50% videos):**

- **Scan time:** < 10 minutes (with EXIF and CRC32)
- **Memory usage:** < 4 GB total
- **Database size:** ~79 MB
- **CPU usage:** 80-90% during scan (process pool utilization)

**Bottlenecks:**

- Disk I/O (reading files) → **mitigated by parallel workers**
- EXIF extraction (CPU-bound, images only) → **mitigated by process pool**
- CRC32 calculation (CPU-bound, all files) → **mitigated by process pool**
- SQLite writes (lock contention) → **mitigated by batch writes + WAL mode**

**Optimizations:**

- Process pool for CPU-bound work (bypasses GIL)
- Thread pool for I/O and coordination
- Batch writes with `BEGIN IMMEDIATE`
- Deferred index creation
- EXIF only for images (skip videos)
- WAL mode for concurrent reads

## Post-Scan Processing

After bulk import completes, update status for files missing in latest batch:

```python
def mark_missing_files(current_batch_id: str, db_cursor):
    """
    Mark files not seen in current batch as missing.
    Run this after scan completes.
    """
    db_cursor.execute("""
        UPDATE media_items 
        SET status = 1 
        WHERE last_seen_batch_id != ? AND status = 0
    """, (current_batch_id,))
    
    missing_count = db_cursor.rowcount
    log_info(f"Marked {missing_count} files as missing (not in batch {current_batch_id})")
```

**Query missing files:**

```sql
-- Find all files missing in latest batch
SELECT id, original_title, relative_path, last_seen_batch_id
FROM media_items
WHERE status = 1
ORDER BY last_seen_batch_id DESC;
```

## Design Review Changes

This architecture incorporates feedback from the design review:

### ✅ Implemented

1. **Generated columns** - `year/month/day` (NULL when timestamp=0) and `geo_user_edited` use `GENERATED ALWAYS AS` (SQLite 3.31+)
2. **Length constraints** - Added `CHECK(length(id)=19)`, `CHECK(length(file_crc32)=8)`, `CHECK(length(album_id)=36)`
3. **Album identity with aliases** - UUID-based albums with `album_aliases` table for reconciliation across exports
4. **People tags PK fixed** - Primary key is `(media_id, tag_order)` instead of `(media_id, person_name)`
5. **Edited links removed** - Redundant table removed; use `original_media_id` field + partial index
6. **MIME three-tier fallback** - Magic bytes → extension map → sentinel, with `mime_suspect` flag
7. **Compound indexes** - `(media_type, photo_taken_time)`, `(last_seen_batch_id, id)`, `(file_size_bytes, file_crc32)`
8. **Partial indexes** - `WHERE mime_suspect = 1`, `WHERE status = 1`, `WHERE original_media_id != ''`
9. **Pragma lifecycle** - Restore `PRAGMA synchronous=FULL` and run `ANALYZE` after bulk load
10. **Status field** - Added `status` column (0=present, 1=missing_in_latest) for resumability
11. **Single writer enforcement** - Only writer thread opens DB connection; workers never touch DB
12. **ID collision handling** - DB-enforced uniqueness with retry on `IntegrityError`
13. **No foreign keys** - All referential integrity enforced by application logic
14. **No NULLs** - All fields have reasonable defaults (0, 0.0, '') instead of NULL
15. **File location tracking** - Added `relative_path`, `batch_id`, `last_seen_batch_id`
16. **Content signatures** - Added `file_crc32` for deduplication
17. **Process pool for CPU work** - Bypasses GIL for EXIF/CRC32 calculation
18. **Localized edited suffixes** - Comprehensive list of known variants
19. **Deferred indexes** - Create after bulk load for speed
20. **Batch writer strategy** - `BEGIN IMMEDIATE` + manual transaction control
21. **PostgreSQL-compatible types** - Sized VARCHAR/CHAR for portability
22. **EXIF only for images** - Explicit guard to skip EXIF extraction for videos
23. **Extension-agnostic edited detection** - Works for both photos and videos
24. **Sidecar truncation handling** - Tries all documented truncation variants

### ⚠️ Important Optimizations (Recommended)

**1. Sidecar lookup map** - Build dict during discovery for O(1) resolution

- **Without:** O(n × m) filesystem calls (100k files × 5 variants = 500k lookups)
- **With:** O(1) dict lookup per file
- **Impact:** 10-100x faster sidecar matching on large libraries
- **Breaking?** No, but very slow without it

**2. I/O semaphore** - Bounded semaphore for file reads

- **Without:** All processes open files simultaneously (thrashing on HDD/NAS)
- **With:** Limit concurrent file reads (e.g., max 4 open files)
- **Impact:** Prevents disk thrashing on HDD, prevents NAS timeouts
- **Breaking?** Yes on HDD/NAS, fine on SSD

**Recommendation:** Implement both for production use

### 🎯 Design Decisions

**SQLite-Focused (with notes for portability):**

- **Primary target:** SQLite 3.31+ (for generated columns)
- **Schema portability:** Types and constraints are PostgreSQL-compatible
- **Implementation:** Uses SQLite-specific features (PRAGMAs, `strftime()`, `sqlite3` module)
- **To port:** Would need abstraction layer for generated columns, PRAGMAs, and connection handling

**No Foreign Keys:**

- All referential integrity enforced by application logic
- Simplifies schema, improves write performance
- Comments indicate relationships (e.g., "References albums.album_id (application enforced)")

**No NULLs (Reasonable Defaults with Exceptions):**

- **Most fields use defaults instead of NULL:**
  - Strings: Empty string `''` instead of NULL
  - Integers: `0` instead of NULL
  - Floats: `0.0` instead of NULL
- **Exception:** Generated columns (`year`, `month`, `day`) are NULL when `photo_taken_time = 0` to avoid incorrect dates (1970-01-01)
- **Benefits:** Simpler queries (no NULL checks), consistent behavior, smaller index size
- **Sentinel values:**
  - `0` for timestamps means "unknown"
  - `''` for IDs means "not linked"
  - `has_geo = 0` means "no location" (avoids ambiguity with real 0.0/0.0 coordinates at Equator/Greenwich)

### 📝 Noted but Deferred

1. **Video-specific fields** - Skipped (requires ffprobe analysis beyond export data)
2. **Perceptual hashing** - Optional future enhancement for near-dupe detection
3. **WITHOUT ROWID** - Benchmark needed to determine benefit
4. **Full-text search** - Deferred (database-specific: FTS5 for SQLite, tsvector for PostgreSQL)

### 🔍 Implementation Details Needed

1. **Duplicate handling** - `(1)`, `(2)` suffix matching for files with duplicate names
2. **Golden corpus testing** - Curated test set covering edge cases
3. **MIME type library** - Choose between `python-magic`, `filetype`, or `mimetypes`

## Error Recovery Strategy

### Error Classification

**Recoverable Errors** (log and continue):

- Missing JSON sidecar → use EXIF-only data
- Corrupted EXIF data → skip EXIF fields, use JSON
- Invalid JSON format → skip metadata, use file properties only
- CRC32 calculation failure → log warning, set to sentinel value
- Permission denied on individual file → skip file, log warning
- Unknown MIME type → use sentinel value, flag with `mime_suspect=1`

**Fatal Errors** (stop processing):

- Database connection failure → cannot proceed
- Disk full → cannot write
- Permission denied on database file → cannot write
- Out of memory → risk of data corruption
- Corrupted database → cannot recover

### Recovery Mechanisms

#### 1. Graceful Degradation

- If JSON missing → extract what we can from EXIF
- If EXIF fails → use JSON only
- If both fail → store file with minimal metadata (path, size, timestamps from filesystem)

#### 2. Batch-Level Isolation

- Each batch write is atomic (transaction)
- If batch fails → rollback, log error, continue with next batch
- Failed items logged to `scan_log` for manual review

#### 3. Worker-Level Isolation

- Worker exceptions don't crash other workers
- Failed items go to error queue for retry or logging
- Process pool crashes are isolated (other processes continue)

#### 4. Resumability

- Track `last_seen_batch_id` per file
- On restart, can detect incomplete batch and resume
- Post-scan reconciliation marks missing files

### Error Logging

**Three-tier logging:**

1. **stdout** - Structured output only (JSON, return codes) for Unix pipeline compatibility
2. **stderr** - Progress messages, warnings, errors (human-readable)
3. **Log file** - All warnings and errors with full context
4. **Database** (`scan_log` table) - Structured error records for querying

**Output separation (Unix pipeline compatible):**

- **stdout** - Clean, parseable output (final statistics as JSON, return code)
- **stderr** - Progress bars, status messages, errors (doesn't interfere with pipes)

**What to log:**

- File path
- Error type (recoverable/fatal)
- Error message
- Timestamp
- Batch ID
- Recovery action taken

## Orchestration & Lifecycle

### Startup Sequence

1. **Validate environment**

   - Check database exists or create schema
   - Verify takeout directory accessible
   - Check available memory/disk space

2. **Initialize database**

   - Set bulk import PRAGMAs (`synchronous=NORMAL`, WAL mode)
   - Validate and generate batch ID from Takeout archive names
   - Check for incomplete batch (resumability - see below)
   - Record scan start in `scan_metadata`

3. **Discovery phase**

   - Build sidecar lookup map (O(n) scan)
   - Find all media files
   - Reconcile albums (UUID assignment)
   - Associate files with albums

4. **Spawn workers**

   - Create work queue (bounded)
   - Create results queue (bounded)
   - Spawn N worker threads
   - Spawn M process pool workers
   - Spawn 1 writer thread

5. **Feed work queue**

   - Orchestrator puts files into work queue
   - Blocks if queue full (backpressure)

### Shutdown Sequence

**Critical:** Drain writer **first** to prevent deadlock with bounded queues.

**Problem:** If both `work_queue` and `results_queue` are full, workers are blocked trying to `put()` results. If orchestrator tries to `put(None)` into `work_queue`, it blocks forever → deadlock.

**Solution:** Signal writer first, let it drain `results_queue`, then signal workers.

```python
def shutdown_pipeline(work_queue, results_queue, workers, writer_thread, process_pool):
    """
    Gracefully shutdown all components.
    Order matters: drain writer first to prevent deadlock.
    """
    # 1. Signal writer to stop (this never blocks - writer is always consuming)
    results_queue.put(None)
    
    # 2. Wait for writer to drain results_queue and flush final batch
    writer_thread.join(timeout=60)
    if writer_thread.is_alive():
        log_error("Writer thread did not stop within timeout")
    
    # 3. NOW workers can put() results (queue has space)
    # Signal workers to stop
    for _ in range(len(workers)):
        work_queue.put(None)  # Safe now - queues are draining
    
    # 4. Wait for workers to finish
    for worker in workers:
        worker.join(timeout=30)
        if worker.is_alive():
            log_warning(f"Worker {worker.name} did not stop within timeout")
    
    # 5. Shutdown process pool
    process_pool.shutdown(wait=True, timeout=30)
    
    # 6. Post-processing (after all workers stopped)
    link_edited_files_to_originals(db_conn, batch_id)
    mark_missing_files(db_conn, batch_id)
    create_deferred_indexes(db_conn)
    db_conn.execute("ANALYZE")
    
    # 7. Finalize database
    db_conn.execute("PRAGMA synchronous=FULL")  # Restore durability
    record_scan_completion(db_conn, batch_id)
    generate_statistics(db_conn, batch_id)
```

**Key points:**

- **Writer first:** Drains `results_queue`, unblocks workers
- **No data loss:** Writer flushes all remaining items before exiting
- **Timeouts:** Detect stuck threads, log warnings
- **Process pool:** Shutdown after workers (workers may have pending futures)

### Progress Reporting

**What to report:**

- Files discovered (total count)
- Files processed (current/total)
- Processing rate (files/sec)
- Estimated time remaining
- Errors encountered (count by type)
- Current phase (discovery/processing/post-processing)

**How to report:**

- Console progress bar (tqdm or custom)
- Periodic log messages (every N files)
- Database updates (`scan_metadata` table)

## Critical Implementation Gaps

### 1. Orchestrator Shutdown Logic (MUST HAVE)

**What:** Gracefully stop all workers and writer thread

**Why:** Without this, threads hang on exit, database may be left in inconsistent state

**Approach:**

- Send `None` sentinels to queues
- Join threads with timeout
- Handle stuck threads (log warning, force exit)

### 2. Album Discovery Algorithm (MUST SPECIFY)

**What:** How to find albums and associate files with them

**Why:** Not currently specified in detail

**Approach:**

- Walk directory tree, find folders with `metadata.json`
- Parse album metadata, reconcile via UUID + aliases
- Associate files with albums based on path containment
- Handle files in multiple albums (path matches multiple album folders)

### 3. Edited File Linking Algorithm (MUST SPECIFY)

**What:** How to link edited files to originals in post-processing

**Why:** Currently says "find pairs by matching filenames" but no algorithm

**Approach:**

- Query all files with `is_edited=1`
- For each edited file, extract original filename
- Look up original by path (same directory + original filename)
- If found, link via `original_media_id` and set `has_edited_version=1`
- If not found, log warning (original may have been deleted)

### 4. Resumability Logic

**What:** Detect and handle interrupted scans for the same Takeout export.

**Why:** Large libraries (100k+ files) may take 10+ minutes. Scanner crashes, power loss, or user interruption should not require full re-scan.

**Implementation:**

```python
def check_resumability(db_conn, batch_id: str) -> tuple[bool, int]:
    """
    Check if batch_id already exists in database (incomplete scan).
    
    Returns:
        (is_incomplete, existing_count) tuple
    """
    # Check if batch_id exists
    result = db_conn.execute(
        "SELECT COUNT(*) FROM media_items WHERE batch_id = ?",
        (batch_id,)
    ).fetchone()
    
    existing_count = result[0] if result else 0
    
    # Check if scan was marked complete
    completion_status = db_conn.execute(
        "SELECT value FROM scan_metadata WHERE key = ?",
        (f"batch_{batch_id}_complete",)
    ).fetchone()
    
    is_complete = completion_status is not None
    is_incomplete = existing_count > 0 and not is_complete
    
    return (is_incomplete, existing_count)

def handle_incomplete_batch(db_conn, batch_id: str, existing_count: int):
    """
    Handle incomplete batch: prompt user for action.
    """
    print(f"⚠️  Incomplete scan detected for batch_id='{batch_id}'")
    print(f"   Found {existing_count} existing records in database.")
    print(f"   Options:")
    print(f"     1. Delete and re-scan (recommended)")
    print(f"     2. Validate and continue (experimental)")
    print(f"     3. Abort")
    
    choice = input("Choose [1/2/3]: ").strip()
    
    if choice == "1":
        # Delete all records for this batch_id
        db_conn.execute("DELETE FROM media_items WHERE batch_id = ?", (batch_id,))
        db_conn.execute("DELETE FROM album_items WHERE album_id IN (SELECT album_id FROM albums WHERE scan_timestamp IN (SELECT scan_timestamp FROM media_items WHERE batch_id = ?))", (batch_id,))
        # ... delete from other tables
        db_conn.commit()
        print(f"✓ Deleted {existing_count} records. Starting fresh scan.")
        return "rescan"
    
    elif choice == "2":
        print(f"⚠️  Validation mode not yet implemented. Use option 1.")
        sys.exit(1)
    
    else:
        print("Aborted.")
        sys.exit(0)
```

**Usage at startup:**

```python
# After generating batch_id
batch_id = validate_and_generate_batch_id(takeout_folder)

# Check for incomplete scan
is_incomplete, existing_count = check_resumability(db_conn, batch_id)

if is_incomplete:
    action = handle_incomplete_batch(db_conn, batch_id, existing_count)
    if action == "rescan":
        # Proceed with fresh scan
        pass

# Mark scan as started (not complete)
db_conn.execute(
    "INSERT OR REPLACE INTO scan_metadata (key, value) VALUES (?, ?)",
    (f"batch_{batch_id}_start", str(int(time.time())))
)
```

**Mark scan complete:**

```python
# At end of shutdown_pipeline()
db_conn.execute(
    "INSERT OR REPLACE INTO scan_metadata (key, value) VALUES (?, ?)",
    (f"batch_{batch_id}_complete", str(int(time.time())))
)
```

**Key points:**

- **Stable batch_id:** Same Takeout export always generates same `batch_id`
- **Detection:** Check if `batch_id` exists in DB but not marked complete
- **User choice:** Delete and re-scan (simple, reliable) or validate (complex, future work)
- **Completion marker:** Record in `scan_metadata` when scan finishes successfully

## Implementation Action Plan

### Phase 0: Foundation

**Goal:** Set up project structure and testing framework

- [ ] Create database schema DDL (all tables, no indexes)
- [ ] Write schema creation script with PRAGMA setup
- [ ] Set up pytest framework with fixtures
- [ ] Create golden corpus test set (10-20 representative files)
- [ ] Document test file coverage (localized edits, truncated sidecars, videos, etc.)

### Phase 1: Discovery

**Goal:** Find all files and build lookup structures

- [ ] Implement sidecar lookup map builder
- [ ] Implement album discovery and reconciliation
- [ ] Implement file-to-album association
- [ ] Test with golden corpus
- [ ] Benchmark on 10k files

### Phase 2: Worker Pipeline

**Goal:** Process files in parallel

- [ ] Implement JSON parser with error handling
- [ ] Implement MIME type probing (three-tier fallback)
- [ ] Implement edited suffix detection (all localized variants)
- [ ] Implement worker thread loop
- [ ] Implement process pool for EXIF/CRC32
- [ ] Test with golden corpus

### Phase 3: Batch Writer

**Goal:** Write to database efficiently

- [ ] Implement batch writer thread
- [ ] Implement ID generation with collision retry
- [ ] Implement error recovery (per-item and per-batch)
- [ ] Implement database logging (`scan_log`)
- [ ] Test transaction isolation and rollback

### Phase 4: Orchestration

**Goal:** Coordinate all components

- [ ] Implement startup sequence
- [ ] Implement shutdown sequence (sentinels + joins)
- [ ] Implement progress reporting
- [ ] Implement error aggregation and reporting
- [ ] Test graceful shutdown under load

### Phase 5: Post-Processing

**Goal:** Link relationships and finalize

- [ ] Implement edited file linking
- [ ] Implement missing file detection
- [ ] Implement deferred index creation
- [ ] Implement statistics generation
- [ ] Test resumability (interrupted scan)

### Phase 6: Optimization

**Goal:** Performance tuning

- [ ] Benchmark with 100k files
- [ ] Profile bottlenecks
- [ ] Tune queue sizes, batch sizes, worker counts
- [ ] Add I/O semaphore if needed (HDD/NAS)
- [ ] Verify < 10 minute target for 100k files

### Phase 7: Production Readiness

**Goal:** Polish and documentation

- [ ] Add comprehensive error messages
- [ ] Add user-facing progress reporting
- [ ] Write operator documentation
- [ ] Add configuration validation
- [ ] Add dry-run mode (no database writes)

## Decision Log

### Decisions Made

1. **CRC32 for deduplication** - Fast, acceptable collision risk with manual verification
2. **Single writer pattern** - Eliminates SQLite lock contention
3. **Process pool for CPU work** - Bypasses GIL for EXIF/CRC32
4. **Deferred indexes** - 5-10x faster bulk load
5. **No NULLs** - Simpler queries, consistent behavior
6. **UUID for albums** - Stable identity across exports
7. **Batch writes** - Amortizes transaction overhead
8. **WAL mode** - Allows concurrent reads during scan

### Decisions Pending

1. **EXIF library** - exiftool (comprehensive) vs Pillow (fast, limited)
2. **ID generation location** - Workers vs writer (recommend writer)
3. **Resumability approach** - Delete incomplete vs resume incomplete
4. **Progress reporting UI** - Console only vs web dashboard
5. **I/O semaphore** - Always enabled vs auto-detect (HDD vs SSD)

### Trade-offs Accepted

1. **CRC32 collisions** - Rare, mitigated by manual verification before deletion
2. **Process pool overhead** - Serialization cost, but worth it for GIL bypass
3. **Memory usage** - Bounded queues limit throughput but prevent OOM
4. **No foreign keys** - Manual integrity checks, but simpler schema and faster writes

## Next Steps

1. Implement database schema with all new fields
2. Build file discovery with sidecar matching (all truncations)
3. Create thread pool + process pool framework
4. Implement JSON parsing
5. Add batch writer with `BEGIN IMMEDIATE`
6. Integrate EXIF extraction (decide: exiftool vs Pillow)
7. Add localized edited suffix detection (extension-agnostic)
8. Implement sidecar matching with all truncation variants
9. Add MIME type probing with unknown type flagging
10. Add EXIF extraction guard (images only, skip videos)
11. Implement post-processing (link edited files, mark missing)
12. Performance testing with 100k files
13. Create golden corpus test suite (include videos, long filenames, localized edits)

## Design Review Updates

### Critical Additions

1. **Batch ID Validation and Generation** (lines 1111-1190)
   - `batch_id` now derived from Takeout archive names, not runtime timestamp
   - Validates that folder contains archives from **single** Takeout export only
   - Stable across scanner restarts (enables resumability)
   - Format: `takeout_YYYYMMDD` from archive names like `takeout-20231015-001.zip`

2. **Shutdown Deadlock Prevention** (lines 1717-1770)
   - **Critical fix:** Drain writer first to prevent deadlock with bounded queues
   - Explicit shutdown sequence: writer → workers → process pool → post-processing
   - No data loss: writer flushes all remaining items before exiting
   - Timeouts and error handling for stuck threads

3. **Resumability Logic** (lines 1830-1933)
   - Detect incomplete scans using stable `batch_id`
   - User choice: delete and re-scan (recommended) or validate (future work)
   - Completion markers in `scan_metadata` table
   - Handles scanner crashes, power loss, user interruption

### Key Design Clarifications

- **Single writer pattern:** Confirmed correct - SQLite enforces UNIQUE at INSERT time, not COMMIT
- **isolation_level=None:** Confirmed correct - autocommit mode still allows explicit transactions
- **Cross-batch linking:** Not needed for full scans (original and edited in same batch)
- **No data loss on shutdown:** Writer processes all queued items before exiting

## References

- [Google_Takeout_Structure.md](./Google_Takeout_Structure.md) - Detailed takeout format documentation
- [SQLite WAL Mode](https://www.sqlite.org/wal.html) - Write-Ahead Logging
- [Python multiprocessing](https://docs.python.org/3/library/multiprocessing.html) - Parallel processing
