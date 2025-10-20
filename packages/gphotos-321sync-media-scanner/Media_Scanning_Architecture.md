# Media Scanning Architecture

**Status:** 🚧 Draft - Design Phase

This document outlines the architecture for scanning and cataloging Google Photos Takeout media files into a queryable database.

## Problem Statement

**Input:** A folder containing unpacked archives from a Google Takeout session

- We don't know the session ID
- Files are organized in Google's Takeout structure
- Media files may have accompanying JSON sidecars with metadata
- Albums are represented as folders with metadata.json files

**Goal:** Build and maintain a media database that:

- Catalogs all media files with their metadata
- Tracks album associations
- Handles duplicate files (same content, different locations)
- Supports querying by various criteria (date, album, location, etc.)
- Enables multiple reconstruction strategies for the target gallery

## Core Principles

### 1. Resumability

- Scanning can be interrupted and resumed without duplicate work
- Change detection (optimized three-tier approach):
  1. **Fast check:** `(relative_path, file_size)` [path relative to scan root, excludes Takeout/Google Photos] used only as an index lookup shortcut.
  2. **Content verification:** On every rescan, the scanner **always recomputes** the head+tail SHA-256 fingerprint and compares it with the stored value before deciding to skip. No early "continue" is allowed prior to this step.
  3. **Sidecar verification:** If a JSON sidecar exists, compute its SHA-256 fingerprint and compare with stored value. File is unchanged only if BOTH content and sidecar fingerprints match.
  4. If both fingerprints match: skip all expensive processing (EXIF extraction, video metadata, JSON parsing)
  5. If either fingerprint differs: full reprocessing (detects in-place edits, metadata changes, sidecar updates)

```python
# Pseudocode (optimized rescan)
normalized_path = normalize_path(relative_path)
content_fp = compute_head_tail_sha256(file_path, file_size)
sidecar_fp = compute_sha256(sidecar_path) if sidecar_exists else None

if db.check_file_unchanged(normalized_path, content_fp, sidecar_fp):
    # File and sidecar unchanged - skip ALL expensive work
    skip_processing()
else:
    # File or sidecar changed - do full processing
    extract_exif()
    extract_video_metadata()
    parse_json_sidecar()
    insert_or_update_db()
```

- Tracks scan sessions in `scan_runs` table with statistics
- **Design Decision:** Filesystem modification time is unreliable (gets overwritten during extraction), that's why we need fingerprinting instead of relying on mtime alone
- **Note:** Files <128KB are hashed entirely; larger files use head+tail to detect changes anywhere in the file

### 2. Parallel Processing

- CPU-bound work (EXIF extraction, fingerprinting, MIME detection) uses a process pool for true parallelism
- I/O-bound work (file reading, JSON parsing, DB writes) uses worker threads
- Configuration is tunable via `ParallelScanner` constructor:
  - `worker_processes`: defaults to `max(1, int(cpu_count * 0.75))`
  - `worker_threads`: defaults to `max(2, cpu_count)`
  - `batch_size`: defaults to 100 media items per transaction
  - `queue_maxsize`: defaults to 1000 items for backpressure
- All parameters can be overridden to scale up or down per hardware profile
- **Note:** EXIF extraction includes timestamps, GPS, camera info, orientation (all available fields); resolution (width × height) extracted for all media; video metadata (duration, frame rate) extracted via ffprobe

### 3. Duplicate Tolerance

- All file instances are cataloged (duplicates detected by `file_size + CRC32`)
- **Duplicate resolution strategy:** `file_size + CRC32` for fast candidate detection; on collision, compute SHA-256 to confirm
- Deduplication is a query-time concern, not a storage constraint
- Same photo in multiple albums = multiple database entries
- Path parsing handles Google Takeout's specific folder structure (Takeout/Google Photos/Album Name/...)
- **Rationale:** CRC32 is fast (~1-2 GB/s) vs SHA-256 (~100-200 MB/s); collisions are rare, resolved on-demand

### 4. Database Portability

- Primary implementation uses SQLite
- Schema design is SQL-standard compatible (mostly PostgreSQL-ready)
- No database-specific features that prevent migration

### 5. Metadata Preservation

- All metadata from Google Takeout is preserved
- Original filenames, paths, and relationships are maintained
- User edits (location, timestamps) are tracked separately from originals

### 6. Configuration and Error Handling

- **Configuration storage:** Cross-platform using `platformdirs` library
  - Desktop: `~/.config/gphotos-321sync/config.yaml` (Linux/Mac) or `%APPDATA%/gphotos-321sync/config.yaml` (Windows)
  - Cloud: Environment variables (12-factor app pattern)
  - Priority: Environment variables override config file
- Comprehensive error handling with graceful degradation
- Detailed logging for debugging and audit trail
- Reasonable defaults for all configurable parameters

## High-Level Architecture

### Processing Pipeline

```text
┌─────────────────────────────────────────────────────────────┐
│                    Input: Takeout Folder                    │
│  - Album folders (with metadata.json)                       │
│  - Media files (photos, videos)                             │
│  - JSON sidecars (.supplemental-metadata.json)              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│             Phase 1: Album Discovery (Main Thread)          │
│  - Walk directory tree                                      │
│  - Process folders with metadata.json                       │
│  - Insert/update album rows (deterministic album_id)        │
│  - Build `album_map: {album_folder_path -> album_id}`       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│             Phase 2: File Discovery (Main Thread)           │
│  - Identify media files and optional JSON sidecars          │
│  - Build list of `FileInfo` objects                         │
│  - Pair each `FileInfo` with album_id via `album_map`       │
│  - Enqueue `(FileInfo, album_id)` work items                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│             Phase 3: Parallel Processing                    │
│  - Extract metadata from JSON sidecars                      │
│  - Stream the full file once:                               │
│    • EXIF extraction (timestamps, GPS, camera, orientation) │
│    • Resolution extraction (width × height)                 │
│    • Video metadata (duration, frame rate)                  │
│    • MIME/content type detection from initial bytes         │
│    • CRC32 processes entire stream                          │
│  - Calculate content fingerprint (first 64KB + last 64KB)   │
│  - On error: record in processing_errors table + logs       │
│  - Process in parallel (configurable threads/processes)     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Storage Phase                          │
│  - Batch writes to database (100-500 records per commit)    │
│  - Single writer thread (SQLite WAL mode)                   │
│  - Update last_seen_timestamp for each file                 │
│  - Update files_processed count every 100 files             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Post-Processing Phase                     │
│  - Link edited versions to originals (match filenames)      │
│  - Mark inconsistent: current scan_run_id + old timestamp   │
│  - Mark missing: old scan_run_id (files deleted from disk)  │
│  - Verify: all present files have current scan_run_id       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Media Database                           │
│  - Queryable catalog of all media                           │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```text
╔═════════════════════════════════════════════════════════════════════╗
║                    MAIN PYTHON PROCESS                              ║
╠═════════════════════════════════════════════════════════════════════╣
║                                                                     ║
║  ┌───────────────────────────────────────────────────────────────┐  ║
║  │ Orchestrator (main thread)                                    │  ║
║  │ • Spawns threads and processes                                │  ║
║  │ • Walks filesystem, builds Work Queue                         │  ║
║  └───────────────────────────────────────────────────────────────┘  ║
║                            │                                        ║
║                            ▼                                        ║
║  ┌───────────────────────────────────────────────────────────────┐  ║
║  │ Work Queue                                                    │  ║
║  └───────────────────────────────────────────────────────────────┘  ║
║                            │                                        ║
║                            ▼                                        ║
║  ┌────────────────────────────────────────────────────────────────┐ ║
║  │ Worker Thread 1  │  Worker Thread 2  │  ...  │ Worker Thread N │ ║
║  │                                                                │ ║
║  │ Each thread (N=16, 2× CPU cores for I/O):                      │ ║
║  │   • Get work from queue (maxsize=1000)                         │ ║
║  │   • Parse JSON sidecar                                         │ ║
║  │   • Check if file changed (path+size heuristic)                │ ║
║  │   • Submit file path to Process Pool ──┐                       │ ║
║  │   • Wait for result (blocks on I/O)    │                       │ ║
║  │   • Put result in Results Queue        │                       │ ║
║  └────────────────────────────────────────┼───────────────────────┘ ║
║                            │              │                         ║
║                            ▼              │                         ║
║  ┌────────────────────────────────────────┼───────────────────────┐ ║
║  │ Results Queue                          │                       │ ║
║  └────────────────────────────────────────┼───────────────────────┘ ║
║                            │              │                         ║
║                            ▼              │                         ║
║  ┌────────────────────────────────────────┼───────────────────────┐ ║
║  │ Batch Writer Thread                    │                       │ ║
║  │ • Reads from Results Queue             │                       │ ║
║  │ • Writes to SQLite                     │                       │ ║
║  └────────────────────────────────────────┼───────────────────────┘ ║
║                            │              │                         ║
║                            ▼              │                         ║
║  ┌────────────────────────────────────────┼───────────────────────┐ ║
║  │ SQLite Database (WAL mode)             │                       │ ║
║  └────────────────────────────────────────┼───────────────────────┘ ║
║                                           │                         ║
╚═══════════════════════════════════════════│═════════════════════════╝
                                            │
                                            │ (calls)
                                            ▼
╔═════════════════════════════════════════════════════════════════════╗
║              SEPARATE PROCESS POOL                                  ║
╠═════════════════════════════════════════════════════════════════════╣
║                                                                     ║
║  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐   ║
║  │ Process 1   │  │ Process 2   │  │ Process 3   │  │ Process M │   ║
║  │             │  │             │  │             │  │           │   ║
║  │ CPU work (M=8, 1× CPU cores):                                │   ║
║  │ • Stream file once (7.7 MB avg):                             │   ║
║  │   - EXIF extraction (timestamps, GPS, camera, orientation)   │   ║
║  │   - Resolution extraction (width × height)                   │   ║
║  │   - Video metadata (duration, frame rate via ffprobe)        │   ║
║  │   - MIME/content type detection (magic bytes, filetype lib)  │   ║
║  │   - CRC32 calculation (full stream)                          │   ║
║  │ • Content fingerprint (first 64KB + last 64KB, SHA-256)      │   ║
║  │ • On error: return error details for database recording      │   ║
║  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘   ║
║                                                                     ║
║                          (returns result to caller)                 ║
╚═════════════════════════════════════════════════════════════════════╝
```

## Database Schema

### Indexes

**Critical indexes for performance:**

```sql
CREATE INDEX idx_media_items_path ON media_items(relative_path);
CREATE INDEX idx_media_items_scan_run ON media_items(scan_run_id);
CREATE INDEX idx_media_items_status ON media_items(status);
CREATE INDEX idx_media_items_last_seen ON media_items(last_seen_timestamp);
CREATE INDEX idx_errors_scan_run ON processing_errors(scan_run_id);
CREATE INDEX idx_errors_path ON processing_errors(relative_path);
```

### Entities

#### 1. Media Items

- `media_item_id` (UUID5) - Primary key, deterministic UUID based on canonical tuple (relative_path, photoTakenTime, file_size, creationTime) - ensures same media item gets same ID on re-imports
- `relative_path` (UNIQUE, normalized NFC, indexed) - Path relative to scan root (e.g., "Photos from 2023/IMG_1234.jpg") [excludes Takeout/Google Photos prefix]
- `album_id` (NOT NULL) - UUID5 of the album (every file is in a folder, every folder is an album)
- `google_media_item_id` (UNIQUE) - Google Photos API media item ID (NULL for Takeout-only, populated during API sync)
- `title` - From JSON metadata (precedence: JSON > filename)
- `mime_type` - MIME/content type (e.g., image/jpeg, video/mp4)
- `file_size` - File size in bytes
- `crc32` - CRC32 of full file (for fast duplicate candidate detection)
- `content_fingerprint` - SHA-256 of (first 64KB + last 64KB) for change detection (always verified on rescans)
- `sidecar_fingerprint` - SHA-256 of JSON sidecar file (NULL if no sidecar) for detecting sidecar changes without re-parsing
- **Duplicate detection:** Query by `file_size + CRC32` for candidates; on collision, compute SHA-256 to confirm
- **Rescan optimization:** Query by `(relative_path, content_fingerprint, sidecar_fingerprint)` to skip unchanged files
- `width` - Image/video width in pixels
- `height` - Image/video height in pixels
- `duration_seconds` - Video duration (NULL for images)
- `frame_rate` - Video frame rate (NULL for images)
- `capture_timestamp` - When photo was taken (JSON > EXIF > filename > NULL)
- `first_seen_timestamp` - When file first entered database
- `last_seen_timestamp` - When file was last seen in a scan
- `scan_run_id` - UUID of the scan run that last processed this file (for debugging/audit trail)
- `status` - CHECK('present', 'missing', 'error', 'inconsistent')
- `original_media_item_id` - For edited variants (-edited suffix)
- `live_photo_pair_id` - For Live Photos (HEIC+MOV pairs)
- EXIF metadata (timestamps, GPS coordinates, camera info, orientation, and all other available fields)
- Other metadata from JSON sidecar

**Lookup Strategy:**

- `media_item_id`: UUID5 (deterministic), generated from canonical tuple (relative_path [relative to scan root], photoTakenTime, file_size, creationTime) - same file always gets same ID
- File lookup: Query by `relative_path` [relative to scan root, excludes Takeout/Google Photos] (UNIQUE, indexed) to check if file exists in database
- Re-import behavior: Same media item from repeated Takeout exports produces identical UUID5, enabling idempotent imports

#### 2. Albums

- `album_id` - UUID5(namespace, album_name) for deterministic IDs [album_name is just folder name, e.g., "Photos from 2023"]
- `album_folder_path` (UNIQUE, normalized NFC) - Path relative to scan root (e.g., "Photos from 2023") [excludes Takeout/Google Photos prefix]
- `google_album_id` (UNIQUE) - Google Photos API album ID (NULL for Takeout-only, populated during API sync)
- `title`, `description`, `creation_timestamp`, `access_level`
- `status` - CHECK('present', 'error', 'missing')
- Two types: User Albums (with metadata.json) and Year-based Albums (Photos from YYYY/)
- **Album creation logic:**
  - Every folder is an album (album record always created)
  - User albums: Parse metadata.json for title, description, etc.
  - Year-based albums: Derive title from folder name (e.g., "Photos from 2023")
  - If metadata.json parsing fails: `status='error'`, record error in `processing_errors` table
- **Note:** Google Takeout does not provide stable album IDs, we derive from path
- **TODO:** Album identity across Takeout exports is complex (no stable IDs, path changes, merges/splits possible). Requires dedicated design session to handle rename detection, merge detection, and identity reconciliation

#### 3. People

- `person_id` (UUID4) - Generated by us
- `person_name` (unique) - From JSON metadata (e.g., "Alice")
- **Note**: Google Takeout does not provide stable person IDs
- **Design decision:** `person_name` is unique (conscious choice). Limitation: same name = same person. Acceptable for personal photo libraries.
- Algorithm: Look up name, if exists use that person_id, else insert new row

#### 4. People Tags

- `media_item_id` (UUID) - References Media Items
- `person_id` (UUID) - References People
- `tag_order` - Position in array (0-based)
- UNIQUE(media_item_id, person_id)

#### 5. Scan Runs

- `scan_run_id` (UUID4) - Primary key
- `start_timestamp` - When scan started
- `end_timestamp` - When scan completed (NULL if in progress)
- `status` - CHECK('running', 'completed', 'failed')

**Statistics:**

- `total_files_discovered` - Total files found on disk
- `media_files_discovered` - Media files (photos/videos)
- `metadata_files_discovered` - JSON sidecar files
- `files_processed` - Count of files processed
- `new_files` - Files added since last scan
- `unchanged_files` - Files skipped (path+size match)
- `changed_files` - Files reprocessed (path or size changed)
- `missing_files` - Files marked as status='missing'
- `error_files` - Files that failed to process
- `inconsistent_files` - Files with current scan_run_id but old timestamp
- `albums_total` - Total number of albums
- `files_in_albums` - Files associated with albums

**Performance:**

- `duration_seconds` - Total scan duration
- `files_per_second` - Processing rate

#### 6. Processing Errors

- `error_id` (INTEGER) - Primary key (autoincrement)
- `scan_run_id` (UUID) - References Scan Runs
- `relative_path` (TEXT) - Path relative to scan root for the file that failed [excludes Takeout/Google Photos prefix]
- `error_type` - CHECK('media_file', 'json_sidecar', 'album_metadata')
- `error_category` - CHECK('permission_denied', 'corrupted', 'io_error', 'parse_error', 'unsupported_format')
- `error_message` (TEXT) - Detailed error message
- `timestamp` (TIMESTAMP) - When error occurred

**Error Types:**

- `media_file` - Failed to process photo/video file
- `json_sidecar` - Failed to parse JSON metadata sidecar
- `album_metadata` - Failed to process album metadata.json (during discovery phase)

**Indexes:**

- `idx_errors_scan_run` on `scan_run_id`
- `idx_errors_path` on `relative_path`

**Note:** Errors are recorded in both database (for querying) and logs (for real-time monitoring)

#### 7. Schema Version

- `version` (INTEGER) - Current schema version
- Single row table for migration tracking

### Design Principles

#### Catalog everything, deduplicate later

- Store all file instances (duplicates detected by file size + CRC32)
- Deduplication is a query concern, not a storage constraint
- Same photo in multiple albums = multiple rows

#### Resumability

- Track file lifecycle with timestamps
- Skip unchanged files (verified change detection):
  1. Check `(relative_path [relative to scan root, excludes Takeout/Google Photos], file_size)` in DB
  2. If both match: compute content fingerprint (first 64KB + last 64KB)
  3. Compare fingerprint with stored value:
     - **Match:** Skip full processing (metadata extraction)
     - **Mismatch:** Full reprocessing (detects in-place edits, metadata tweaks, lossless rotations)
  4. If path or size differs: full reprocessing (new file or changed)
- Content fingerprint always computed on rescans (cheap: ~2-5ms for head+tail read)
- **Critical:** Every file seen in current scan gets `scan_run_id = current` and `last_seen_timestamp = now`, regardless of whether full processing or skipped
- Detect deletions and inconsistencies after scan completes:
  1. **Inconsistent data**: Files with `scan_run_id = current` BUT `last_seen_timestamp < scan_start_time` → `status='inconsistent'`
  2. **Missing files**: Files with `scan_run_id != current` AND `status='present'` → `status='missing'` (deleted from disk)
  3. **Verification**: All files with `status='present'` must have `scan_run_id = current`
- Progress tracking: `files_processed` count in `scan_runs` table for percentage calculation

#### No foreign keys

- Application-enforced integrity
- Simpler migrations, better write performance

#### Preserve user edits

- Store both original EXIF and Google Photos metadata
- Detect edited timestamps/locations
- Link edited variants via `original_media_item_id`

## SQLite Configuration

### Required PRAGMAs

```sql
PRAGMA journal_mode=WAL;        -- Write-Ahead Logging for concurrency
PRAGMA busy_timeout=5000;       -- Wait 5 seconds on lock contention
PRAGMA synchronous=NORMAL;      -- Balance safety and performance
PRAGMA cache_size=-64000;       -- 64MB cache
PRAGMA temp_store=MEMORY;       -- Temp tables in RAM
```

### Writer Configuration

- **Transaction batching:** Explicit `BEGIN...COMMIT` per batch (100-500 records)
- **Single-writer invariant:** Exactly one writer thread performs all database commits. Retries with exponential backoff are purely defensive; no concurrent writers exist.
- **WAL checkpointing:** `PRAGMA wal_autocheckpoint=1000` (checkpoint every 1000 pages)
- **Manual checkpoint:** Run `PRAGMA wal_checkpoint(TRUNCATE)` after scan completes
- **Retry policy:** Exponential backoff, max 3 retries on lock
- **Progress tracking:** Update `scan_runs.files_processed` every 100 files
- **Queue sizing:** Results queue maxsize=1000 (backpressure)
- **TODO:** Implement memory-aware queue throttling. Track total bytes buffered across queues, apply backpressure if exceeds threshold (e.g., 100MB). Design at implementation time.

## Metadata Extraction

### Tools

- **EXIF extraction:**
  - **Pillow (PIL)** - Always available, supports:
    - JPEG, PNG, GIF, WebP, BMP, TIFF (primary, covers 95%+ of exports)
  - **ExifTool** - Optional, required for:
    - HEIC/HEIF (Apple photos) - without ExifTool, EXIF and resolution will not be extracted
    - RAW formats (DNG, CR2, NEF, ARW, etc.) - without ExifTool, EXIF and resolution will not be extracted
  - Extract: timestamps, GPS coordinates, camera info, orientation, and all other available EXIF fields
- **Image metadata:** Resolution (width × height) for all images (via PIL or ExifTool fallback)
- **Video metadata:**
  - **FFprobe** - Optional, required for:
    - All video formats (MP4, MOV, AVI, MKV, 3GP, WebM, etc.)
    - Extracts: duration, resolution (width × height), and frame rate
  - **Note:** ffprobe process spawn + I/O adds ~50-100ms per video (not 2ms CPU-only)
  - Videos reduce effective throughput; adjust M (process pool size) if video-heavy library
- **MIME/content type detection:** `filetype` library (pure Python, reads magic bytes from file headers)
- **Tool availability check:**
  - **ffprobe (optional):** If missing, warn user that video metadata (duration, resolution, frame rate) will not be extracted
  - **exiftool (optional):** If missing, warn user that HEIC/HEIF and RAW formats will have missing EXIF data and resolution
  - User can proceed without either tool or cancel to install them
  - Files are still cataloged even without these tools, but with limited metadata

### Metadata Precedence

1. **Google JSON sidecar** (`photoTakenTime`, `geoData`, `description`, `people`)
2. **EXIF/IPTC** from media file (`DateTimeOriginal`, `GPSInfo`, camera info)
3. **Filename parsing** (e.g., `IMG_20130608_143022.jpg` → 2013-06-08 14:30:22)
4. **NULL** (unknown)

### Path Normalization

- All paths normalized to **NFC** (Unicode Canonical Composition)
- Forward slashes for database storage
- Use `pathlib.Path` for OS-agnostic handling

## Edge Cases

### Live Photos

- HEIC + MOV pairs with matching base name (e.g., `IMG_1234.HEIC` + `IMG_1234.MOV`)
- Store as separate media items
- Link via `live_photo_pair_id`

### Edited Variants

- Files with `-edited` suffix
- Store as separate media item
- Link to original via `original_media_item_id`

### Missing Metadata

- Some videos have no EXIF: rely on JSON sidecar
- Multiple JSON sidecars: match by closest filename similarity
- Missing timestamps: use precedence order, fallback to NULL

## Error Handling

### File Status Values

- **`present`**: File exists on disk, successfully processed in current scan
- **`missing`**: File was in database but not found in current scan (deleted from disk)
- **`error`**: File exists on disk but failed to process (permission denied, corrupted, etc.)
- **`inconsistent`**: File has current `scan_run_id` but old `last_seen_timestamp`
  - Indicates data anomaly (timing issue, incomplete transaction, or bug)
  - Not a critical error - user can investigate or ignore
  - Future: build reconciliation UI for inconsistent records
  - For now: log, mark, continue scan

### Recoverable Errors (record in database + logs, continue scan)

- **I/O errors:** Permission denied, file locked
- **Corrupted data:** Malformed EXIF, corrupted file headers
- **Missing metadata:** Missing JSON sidecar (file still processed)
- **Unsupported format:** Unknown file type

**Handling:**

```python
try:
    process_file(file)
    db.update_media_item(status='present', scan_run_id=current_scan_run_id, last_seen_timestamp=now())
except Exception as e:
    logger.error(f"Failed to process {file.path}: {e}", exc_info=True)
    db.insert_error(scan_run_id, file.path, 'media_file', classify_error(e), str(e))
    db.insert_or_update_media_item(status='error', scan_run_id=current_scan_run_id, last_seen_timestamp=now())
```

**Result:** File recorded in database with `status='error'`, error details in `processing_errors` table

### Post-Scan Validation

**After scan completes, detect inconsistencies and deletions:**

```python
# 1. Mark data inconsistencies
inconsistent_count = db.execute("""
    UPDATE media_items 
    SET status = 'inconsistent'
    WHERE last_seen_timestamp < ? AND scan_run_id = ?
""", (scan_start_time, current_scan_run_id))

if inconsistent_count > 0:
    logger.error(f"INCONSISTENCY: {inconsistent_count} files have current scan_run_id but old timestamp")

# 2. Mark deletions (normal operation)
deleted_count = db.execute("""
    UPDATE media_items 
    SET status = 'missing'
    WHERE scan_run_id != ? AND status = 'present'
""", (current_scan_run_id,))

logger.info(f"Marked {deleted_count} files as missing")

# 3. Verification: all present files should have current scan_run_id
verification = db.query("""
    SELECT COUNT(*) FROM media_items 
    WHERE status = 'present' AND scan_run_id != ?
""", (current_scan_run_id,))

if verification > 0:
    logger.error(f"VERIFICATION FAILED: {verification} present files have old scan_run_id")
```

### Fatal Errors (abort scan)

- Database connection lost or corrupted (SQLite: file locks, corruption, disk full)
- Disk full
- Schema version mismatch

**SQLite Error Handling:**

- Connection validation on startup
- Retry on `SQLITE_BUSY` with exponential backoff (max 3 retries)
- For local SQLite, connection loss is rare but possible (antivirus locks, network drives, corruption)

## Worker Pool Optimization

### Process Pool Saturation

**Problem:** Using `apply_async()` + immediate `future.get()` blocks worker threads, underutilizing the process pool.

**Solution:** Use `pool.imap_unordered()` or collect futures and drain asynchronously:

```python
# BAD: Blocks on each job
future = pool.apply_async(cpu_work, (file,))
result = future.get()  # Blocks thread, pool underutilized

# GOOD: Saturate pool with pending work
futures = []
for file in work_batch:
    futures.append(pool.apply_async(cpu_work, (file,)))

# Drain results asynchronously
for future in futures:
    result = future.get()  # Pool stays saturated
    results_queue.put(result)

# BETTER: Use imap_unordered for automatic saturation
for result in pool.imap_unordered(cpu_work, work_batch, chunksize=10):
    results_queue.put(result)
```

## Hardware Profiles

### Local NVMe (best case)

- N = 16 worker threads
- M = 8 worker processes
- Expected: ~1.7x speedup (I/O bound on NVMe, CPU fully overlapped)
- Bottleneck: Disk I/O bandwidth (500 MB/s)

### NAS/Synology (realistic)

- N = 4-8 worker threads (avoid overwhelming network)
- M = 8 worker processes
- Expected: ~1.5x speedup (network I/O bound, slower than local disk)
- Bottleneck: Network I/O bandwidth (typically <200 MB/s)

### Laptop/Resource-Constrained

- N = 4 worker threads
- M = 4 worker processes
- Expected: ~1.5x speedup (I/O bound, fewer workers)
- CPU cap: 50-75% max
- Monitor memory usage, throttle if needed

## Observability

### Metrics (logged every 100 files)

- Files/sec, bytes/sec
- Work queue depth, results queue depth
- Writer commit latency
- EXIF/MIME extraction errors
- Database lock retries
- Progress: % complete, ETA

**Implementation:** Simple counter in processing loop: `if counter % 100 == 0: log.info(...)`

### Progress Tracking

**Real-time (during scan):**

- Total files discovered (from filesystem walk)
- Media files vs metadata files breakdown
- Files processed so far (updated every 100 files)
- Progress percentage: `(files_processed / total_files_discovered) × 100`
- Processing rate (files/sec)
- Estimated time remaining: `(total_files - processed) / rate`

**Summary (after scan):**

- New files added
- Unchanged files (skipped via fingerprint match - early exit optimization)
- Changed files (reprocessed due to content or sidecar changes)
- Missing files (deleted from disk)
- Error files (failed to process)
- Inconsistent files (current scan_run_id but old timestamp)
- Error breakdown by category

### Structured Logging

**During scan (every 100 files):**

```json
{
  "timestamp": "2025-10-12T21:30:00Z",
  "total_files_discovered": 125000,
  "media_files": 100000,
  "metadata_files": 25000,
  "files_processed": 45000,
  "files_skipped": 42000,
  "progress_percent": 45.0,
  "files_per_sec": 12.3,
  "work_queue_depth": 234,
  "results_queue_depth": 45,
  "exif_errors": 2,
  "eta_seconds": 4472
}
```

**After scan completes:**

```json
{
  "timestamp": "2025-10-12T22:15:00Z",
  "scan_run_id": "abc-123-def",
  "status": "completed",
  "duration_seconds": 2700,
  "total_discovered": 100000,
  "new_files": 1500,
  "unchanged_files": 97500,
  "changed_files": 800,
  "missing_files": 200,
  "error_files": 50,
  "inconsistent_files": 0,
  "albums_total": 450,
  "files_in_albums": 85000,
  "files_per_second": 37.0,
  "error_breakdown": {
    "permission_denied": 25,
    "corrupted": 15,
    "io_error": 8,
    "parse_error": 2
  }
}
```
