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
- Change detection: `(relative_path, file_size)` → if match, verify with content fingerprint
- Content fingerprint: SHA-256 of last 8KB (calculated lazily, only when path+size match)
- Tracks scan sessions in `scan_runs` table with progress cursor
- Filesystem mtime is unreliable (gets overwritten during extraction)

### 2. Parallel Processing

- CPU-bound work (EXIF, fingerprinting, MIME detection) uses process pool for true parallelism
- I/O-bound work (file reading, JSON parsing, DB writes) uses thread pool
- Configuration: N=16 threads (2x CPU cores), M=8 processes (match CPU cores)
- Single-pass read per file in process pool

### 3. Duplicate Tolerance

- All file instances are cataloged (duplicates detected by file size + CRC32)
- Deduplication is a query-time concern, not a storage constraint
- Same photo in multiple albums = multiple database entries (correct for Takeout structure)

### 4. Database Portability

- Primary implementation uses SQLite
- Schema design is SQL-standard compatible (mostly PostgreSQL-ready)
- No database-specific features that prevent migration

### 5. Metadata Preservation

- All metadata from Google Takeout is preserved
- Original filenames, paths, and relationships are maintained
- User edits (location, timestamps) are tracked separately from originals

### 6. Configuration and Error Handling

- Configuration stored separately from code (config file or environment variables)
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
│                      Discovery Phase                        │
│  - Walk directory tree                                      │
│  - Identify albums                                          │
│  - Identify media files and their sidecars                  │
│  - Build work queue                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Processing Phase                        │
│  - Extract metadata from JSON sidecars                      │
│  - Stream the full file once:                               │
│    • EXIF reads headers from stream                         │
│    • CRC32 processes entire stream                          │
│    • MIME detects from initial bytes                        │
│  - Calculate content fingerprint (last 8KB, lazy/on-demand) │
│  - Process in parallel (N=16 threads, M=8 processes)        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Storage Phase                          │
│  - Batch writes to database (100-500 records per commit)    │
│  - Single writer thread (SQLite WAL mode)                   │
│  - Progress cursor for crash recovery                       │
│  - Update last_seen_timestamp for each file                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Post-Processing Phase                     │
│  - Link edited versions to originals (match filenames)      │
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
║  │ Each thread (N=16, 2x CPU cores for I/O):                      │ ║
║  │   • Get work from queue (maxsize=1000)                         │ ║
║  │   • Parse JSON sidecar                                         │ ║
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
║  │ CPU work (M=8, match CPU cores):                             │   ║
║  │ • Stream file once (7.7 MB avg):                             │   ║
║  │   - EXIF extraction from headers (Pillow)                    │   ║
║  │   - CRC32 calculation (full stream)                          │   ║
║  │   - MIME detection (initial bytes)                           │   ║
║  │ • Content fingerprint (last 8KB, lazy/on-demand)             │   ║
║  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘   ║
║                                                                     ║
║                          (returns result to caller)                 ║
╚═════════════════════════════════════════════════════════════════════╝
```

## Database Schema

### Entities

#### 1. Media Items

- `media_item_id` (UUID) - Primary key, random UUID (no stable ID in Takeout)
- `relative_path` (UNIQUE, normalized NFC) - Full path within Takeout
- `album_id` - UUID of the album
- `title` - From JSON metadata
- `file_size` + `crc32` - For duplicate detection
- `crc32` - CRC32 of full file (for finding duplicates)
- `content_fingerprint` - SHA-256 of last 8KB (for change detection, calculated lazily)
- `capture_timestamp` - When photo was taken (JSON > EXIF > filename > NULL)
- `first_seen_timestamp` - When file first entered database
- `last_seen_timestamp` - When file was last seen in a scan
- `status` - CHECK('present', 'missing')
- `original_media_item_id` - For edited variants (-edited suffix)
- `live_photo_pair_id` - For Live Photos (HEIC+MOV pairs)
- Other metadata from JSON sidecar and EXIF

#### 2. Albums

- `album_id` - UUID5(namespace, folder_path) for deterministic IDs
- `folder_path` (UNIQUE, normalized NFC) - Path to album folder
- `title`, `description`, `creation_timestamp`, `access_level`
- Two types: User Albums (with metadata.json) and Synthetic Albums (Photos from YYYY/)
- Note: Google Takeout does not provide stable album IDs, we derive from path

#### 3. People

- `person_id` (UUID) - Generated by us
- `person_name` (unique) - From JSON metadata (e.g., "Alice")
- Note: Google Takeout does not provide stable person IDs
- Algorithm: Look up name, if exists use that person_id, else insert new row

#### 4. People Tags

- `media_item_id` (UUID) - References Media Items
- `person_id` (UUID) - References People
- `tag_order` - Position in array (0-based)
- UNIQUE(media_item_id, person_id)

#### 5. Scan Runs

- `scan_id` (UUID) - Primary key
- `start_timestamp` - When scan started
- `end_timestamp` - When scan completed (NULL if in progress)
- `last_processed_path` - Progress cursor for resume
- `files_processed` - Count of files processed
- `status` - CHECK('running', 'completed', 'failed')

#### 6. Schema Version

- `version` (INTEGER) - Current schema version
- Single row table for migration tracking

### Design Principles

#### Catalog everything, deduplicate later

- Store all file instances (duplicates detected by file size + CRC32)
- Deduplication is a query concern, not a storage constraint
- Same photo in multiple albums = multiple rows (correct for Takeout)

#### Resumability

- Track file lifecycle with timestamps
- Skip unchanged files:
  1. Check `(relative_path, file_size)` in DB
  2. If match: calculate content fingerprint (last 8KB) to verify unchanged
  3. If fingerprint matches: skip, update `last_seen_timestamp`
  4. If no match: process fully (new file or changed)
- Detect deletions: files with old `last_seen_timestamp` marked as `status='missing'`
- Progress cursor in `scan_runs` table for crash recovery

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

- **Batch size:** 100-500 records per commit
- **Retry policy:** Exponential backoff, max 3 retries on lock
- **Progress tracking:** Update `scan_runs.last_processed_path` after each batch
- **Queue size:** Results queue maxsize=1000 (backpressure)

## Metadata Extraction

### Tools

- **Images:** Pillow (PIL) for JPEG, PNG, HEIC
- **Complex formats:** exiftool for RAW, maker notes
- **Videos:** ffprobe (from ffmpeg) for video metadata

### Metadata Precedence

1. **Google JSON sidecar** (`photoTakenTime`, `geoData`, `description`, `people`)
2. **EXIF/IPTC** from media file (`DateTimeOriginal`, `GPSInfo`)
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

### Recoverable Errors (skip file, log, continue)

- I/O errors (permission denied, file locked)
- Corrupted EXIF (malformed headers)
- Missing JSON sidecar
- Unsupported format

### Fatal Errors (abort scan)

- Database connection lost (after retries exhausted)
- Disk full
- Schema version mismatch

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
- EXIF extraction errors
- Database lock retries
- Progress: % complete, ETA

### Structured Logging

```json
{
  "timestamp": "2025-10-12T21:30:00Z",
  "files_processed": 1500,
  "files_per_sec": 12.3,
  "work_queue_depth": 234,
  "results_queue_depth": 45,
  "exif_errors": 2
}
```

## Next Steps

- [ ] **Full Schema DDL** - CREATE TABLE statements with indexes
- [ ] **Test Fixtures** - Edge cases (Live Photos, edited variants, missing EXIF)
- [ ] **Migration Scripts** - Numbered SQL files (001_initial.sql, etc.)
- [ ] **Implementation** - Worker threads, process pool, writer

---

**Document History:**

- 2025-10-12: Initial architecture
- 2025-10-12: Added SQLite config, metadata extraction, edge cases, error handling, hardware profiles
