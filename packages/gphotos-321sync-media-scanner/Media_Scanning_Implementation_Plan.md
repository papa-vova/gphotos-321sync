# Media Scanning Implementation Plan

**Status:** 🚧 Planning Phase  
**Architecture Reference:** [Media_Scanning_Architecture.md](./Media_Scanning_Architecture.md)  
**Performance Reference:** [Performance_Analysis_Sequential_vs_Parallel.md](./Performance_Analysis_Sequential_vs_Parallel.md)

## Overview

This document provides a step-by-step implementation plan for the media scanning system. Each step is atomic, testable, and builds incrementally on previous steps.

**Key Principles:**

- **Minimal atomic steps** - Each step is independently testable
- **Test-driven** - Tests written before or alongside implementation
- **Incremental** - Each step adds working functionality
- **Trackable** - Progress tracked in this document

**Dependencies:**

- **Common Package:** This implementation uses `gphotos-321sync-common` for:
  - Configuration management (`ConfigLoader`)
  - Structured logging (`setup_logging`, `get_logger`, `LogContext`)
  - Base error classes (`GPSyncError`)

---

## Progress Tracking

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: Foundation | ✅ | 8/8 |
| Phase 2: Database Layer | ✅ | 6/6 |
| Phase 3: Metadata Extraction | ✅ | 5/5 |
| Phase 4: Discovery & Processing | ⬜ | 0/4 |
| Phase 5: Parallel Scanner | ⬜ | 0/6 |
| Phase 6: Post-Scan & Validation | ⬜ | 0/2 |
| Phase 7: Edge Cases | ⬜ | 0/2 |
| **Total** | **58%** | **19/33** |

**Legend:** ⬜ Not Started | 🔄 In Progress | ✅ Completed | ⚠️ Blocked | ❌ Failed

---

## Phase 1: Foundation (8 steps)

**Goal:** Set up project structure, dependencies, basic utilities, and error handling/logging infrastructure.

### 1.1 Project Structure Setup

- **Status:** ✅
- **Tasks:**
  - Create `src/gphotos_321sync/media_scanner/` directory
  - Create `tests/` directory
  - Add `__init__.py` files
- **Tests:** Import verification
- **Acceptance:** Python can import `gphotos_321sync.media_scanner`

### 1.2 Dependencies Installation

- **Status:** ✅
- **Tasks:**
  - Add to `requirements.txt`:
    - `gphotos-321sync-common` (for config, logging, errors)
    - `pillow>=10.0.0`
    - `filetype>=1.2.0`
    - `platformdirs>=3.0.0`
  - Install and verify imports
- **Tests:** `test_common_import()`, `test_pillow_import()`, `test_filetype_import()`, `test_platformdirs_import()`
- **Acceptance:** All dependencies import successfully

### 1.3 Path Utilities

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/path_utils.py`
- **Functions:**
  - `should_scan_file(path: Path) -> bool` (excludes only system/hidden/temp files)
  - `is_hidden(path: Path) -> bool` (cross-platform hidden file detection)
- **Tests:** File filtering, hidden file detection
- **Acceptance:** All path tests pass
- **CRITICAL:** Does NOT filter by extension! MIME detection determines if file is media.
  - Files without extensions: scanned ✅
  - Files with wrong extensions: scanned ✅
  - Actual media detection: via `detect_mime_type()` only

### 1.4 Fingerprint Utilities

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/fingerprint.py`
- **Functions:**
  - `compute_content_fingerprint(file_path: Path, file_size: int) -> str` (SHA-256 head+tail)
- **Tests:** Small/large file handling, change detection
- **Performance:** Fingerprint ~2-5ms
- **Acceptance:** Detects file changes correctly

### 1.5 Configuration Module

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/config.py`
- **Classes:** (Pydantic BaseModel)
  - `LoggingConfig`: `level` (INFO), `format` (json)
  - `ScannerConfig`: `worker_threads` (2×CPU), `worker_processes` (CPU), `batch_size` (100), `queue_maxsize` (1000)
  - `MediaScannerConfig`: Root config with `logging` and `scanner` sections
- **Usage:** Use `ConfigLoader` from `gphotos_321sync.common.config`

  ```python
  from gphotos_321sync.common import ConfigLoader
  from .config import MediaScannerConfig
  
  APP_NAME = "gphotos-321sync-media-scanner"
  loader = ConfigLoader(app_name=APP_NAME, config_class=MediaScannerConfig)
  config = loader.load(defaults_path=args.config)  # Optional defaults.toml path
  ```

- **Tests:** Default values, CPU auto-detection, config loading from TOML
- **Acceptance:** Config loads with sensible defaults using common package utilities
- **Reference:** See `takeout_extractor/config.py` for structure pattern

### 1.6 Error Classification

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/errors.py`
- **Classes:** (all inherit from `gphotos_321sync.common.errors.GPSyncError`)
  - `ScannerError` (base scanner error, inherits from GPSyncError)
  - `PermissionDeniedError`
  - `CorruptedFileError`
  - `IOError`
  - `ParseError`
  - `UnsupportedFormatError`
  - `ToolNotFoundError`
- **Example:**

  ```python
  from gphotos_321sync.common import GPSyncError
  
  class ScannerError(GPSyncError):
      """Base error for media scanner."""
      pass
  
  class CorruptedFileError(ScannerError):
      """File is corrupted or unreadable."""
      pass
  ```

- **Function:** `classify_error(exception: Exception) -> str`
- **Tests:** Error classification for different exception types
- **Acceptance:** Errors classified correctly, inherit context support from GPSyncError
- **Reference:** See `takeout_extractor/errors.py` for inheritance pattern

### 1.7 Logging Setup

- **Status:** ✅ (Uses common package)
- **File:** No separate file needed - use `gphotos_321sync.common.logging`
- **Tasks:**
  - Use `setup_logging()` from common package for initialization (call once in CLI/main)
  - Use `logging.getLogger(__name__)` for module-level loggers
  - Use `LogContext` for adding structured fields: `scan_run_id`, `file_path`, `error_type`
  - Configure via config: log level, format type (simple/detailed/json), log file path
- **Example:**

  ```python
  # In CLI/main entry point:
  from gphotos_321sync.common import setup_logging
  
  config = loader.load()
  setup_logging(level=config.logging.level, format_type=config.logging.format)
  
  # In modules:
  import logging
  logger = logging.getLogger(__name__)
  
  logger.info(f"Processing file: {file_path}")
  logger.debug(f"Extracted metadata: {metadata}")
  logger.error(f"Failed to process {file_path}: {error}")
  ```

- **Tests:** Logger initialization, structured fields via LogContext, log file rotation
- **Acceptance:** Structured logging works using common package utilities
- **Reference:** See `takeout_extractor/cli.py` (lines 167, 55) and `extractor.py` (line 20) for usage pattern

### 1.8 Tool Availability Checker

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/tool_checker.py`
- **Functions:**
  - `check_tool_availability() -> dict` (ffprobe, exiftool) - detects availability
  - `check_required_tools(use_ffprobe, use_exiftool)` (logs status, raises error if enabled but missing)
- **Tests:** Tool detection, missing tool handling, config integration
- **Decision:** Tool usage controlled by config (`use_ffprobe`, `use_exiftool`). Log status at INFO level, never block.
- **Acceptance:** Detects tool availability at startup, logs clear status messages
- **Integration Points:**
  - **Scanner initialization (Phase 5):** Call `check_required_tools(config.scanner.use_ffprobe, config.scanner.use_exiftool)`
  - Logs at INFO level: tool availability + what metadata will/won't be extracted
- **Note:** Must run before any metadata extraction

---

## Phase 2: Database Layer (6 steps)

**Goal:** Implement database schema, migrations, and CRUD operations including albums.

### 2.1 Database Schema Definition

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/schema/001_initial_schema.sql`
- **Tables:** `schema_version`, `scan_runs`, `media_items`, `albums`, `people`, `people_tags`, `processing_errors`
- **Tests:** SQL validity, table creation
- **Acceptance:** Schema matches architecture document

### 2.2 Database Connection Manager

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/database.py`
- **Class:** `DatabaseConnection` with:
  - `connect(db_path: Path) -> Connection`
  - Apply PRAGMAs: WAL mode, busy_timeout=5000, synchronous=NORMAL
  - Context manager for transactions
- **Tests:** Connection, PRAGMA verification, transaction handling
- **Acceptance:** SQLite configured correctly

### 2.3 Migration System

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/migrations.py`
- **Class:** `MigrationRunner` with:
  - `get_current_version() -> int`
  - `apply_migrations(target_version: Optional[int] = None)`
- **Tests:** Initial migration, idempotency
- **Acceptance:** Migrations apply correctly and track version

### 2.4 Data Access Layer - Scan Runs

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/dal/scan_runs.py`
- **Class:** `ScanRunDAL` with:
  - `create_scan_run() -> str`
  - `update_scan_run(scan_run_id: str, **fields)`
  - `complete_scan_run(scan_run_id: str, status: str)`
  - `get_scan_run(scan_run_id: str) -> dict`
- **Tests:** CRUD operations, UUID generation
- **Acceptance:** Scan runs managed correctly

### 2.5 Data Access Layer - Albums

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/dal/albums.py`
- **Class:** `AlbumDAL` with:
  - `insert_album(album: dict) -> str` (returns album_id)
  - `get_album_by_path(folder_path: str) -> Optional[dict]`
  - `update_album(album_id: str, **fields)`
  - `generate_album_id(folder_path: str) -> str` (UUID5 from path)
- **Tests:** Album creation, UUID5 generation, path-based lookup
- **Acceptance:** Albums managed correctly, deterministic IDs
- **Note:** Every folder is an album (album_id is NOT NULL for media items)

### 2.6 Data Access Layer - Media Items & Errors

- **Status:** ✅
- **Files:**
  - `src/gphotos_321sync/media_scanner/dal/media_items.py`
  - `src/gphotos_321sync/media_scanner/dal/processing_errors.py`
- **Class:** `MediaItemDAL` with:
  - `insert_media_item(item: dict) -> str` (requires album_id)
  - `update_media_item(media_item_id: str, **fields)`
  - `get_media_item_by_path(relative_path: str) -> Optional[dict]`
  - `mark_files_missing(scan_run_id: str) -> int`
  - `mark_files_inconsistent(scan_run_id: str, scan_start_time: datetime) -> int`
- **Class:** `ProcessingErrorDAL` with:
  - `insert_error(scan_run_id: str, relative_path: str, error_type: str, error_category: str, error_message: str)`
  - `get_errors_by_scan(scan_run_id: str) -> list[dict]`
- **Tests:** Insert, query, batch updates, error recording
- **Acceptance:** Media items and errors managed correctly

---

## Phase 3: Metadata Extraction (5 steps)

**Goal:** Extract metadata from files and JSON sidecars.

**Note:** Tool availability checker (Step 1.8) must be completed first.

### 3.1 JSON Sidecar Parser

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/metadata/json_parser.py`
- **Function:** `parse_json_sidecar(json_path: Path) -> dict`
- **Extracts:** `title`, `description`, `photoTakenTime`, `geoData`, `people`
- **Tests:** Complete JSON, missing fields, invalid JSON
- **Acceptance:** Parses Google Takeout JSON correctly

### 3.2 EXIF Extractor

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/metadata/exif_extractor.py`
- **Functions:**
  - `extract_exif(file_path: Path) -> dict` (Pillow for JPEG/PNG/HEIC)
  - `extract_exif_with_exiftool(file_path: Path) -> dict` (ExifTool for RAW formats)
  - `extract_exif_smart(file_path: Path, use_exiftool: bool) -> dict` (Smart routing based on MIME type)
  - `extract_resolution(file_path: Path) -> tuple[int, int]`
- **RAW Support:** CR2, NEF, ARW, DNG, RW2, ORF, PEF, RAF, etc. via ExifTool
- **Routing:** Known formats (JPEG/PNG/HEIC) → Pillow (fast), Unknown formats → ExifTool (if enabled)
- **Tests:** JPEG with/without EXIF, GPS extraction, resolution extraction, IFDRational handling
- **Performance:** ~5ms per file (Pillow), ~50-100ms per file (ExifTool)
- **Acceptance:** Extracts EXIF and resolution correctly from standard and RAW formats

### 3.3 MIME Type Detector

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/mime_detector.py`
- **Functions:**
  - `detect_mime_type(file_path: Path) -> str` (filetype library - pure Python)
  - `is_image_mime_type(mime_type: str) -> bool`
  - `is_video_mime_type(mime_type: str) -> bool`
  - `is_unknown_mime_type(mime_type: str) -> bool` (detects when filetype returns generic type)
- **Tests:** JPEG, PNG, MP4, unknown files
- **Performance:** ~1ms per file
- **Acceptance:** Detects MIME types correctly
- **Note:** Uses `filetype` library (reads magic bytes) instead of libmagic for cross-platform compatibility. Most RAW formats return `application/octet-stream` (generic/unknown type) and are handled by ExifTool when enabled.

### 3.4 Video Metadata Extractor

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/metadata/video_extractor.py`
- **Functions:**
  - `extract_video_metadata(file_path: Path) -> dict` (ffprobe subprocess)
  - `is_video_file(mime_type: str) -> bool`
- **Extracts:** duration, resolution, frame_rate
- **Tests:** Video extraction, non-video handling
- **Performance:** ~50-100ms per video
- **Acceptance:** Extracts video metadata correctly

### 3.5 Metadata Aggregator

- **Status:** ✅
- **File:** `src/gphotos_321sync/media_scanner/metadata/aggregator.py`
- **Function:** `aggregate_metadata(file_path: Path, json_metadata: dict, exif_data: dict, video_data: dict) -> dict`
- **Precedence:** JSON > EXIF > filename > NULL
- **Tests:** Precedence rules, conflict resolution
- **Acceptance:** Metadata merged correctly with proper precedence

---

## Phase 4: Discovery & Processing (4 steps)

**Goal:** Implement file/album discovery and processing logic (used by parallel scanner).

### 4.1 File Discovery

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/discovery.py`
- **Function:** `discover_files(root_path: Path) -> Iterator[FileInfo]`
- **Tasks:**
  - Walk directory tree
  - Identify media files and JSON sidecars
  - Pair files with sidecars
  - Yield `FileInfo` objects (includes parent folder for album_id)
- **Tests:** Directory walking, file pairing, filtering
- **Acceptance:** Discovers all media files and sidecars

### 4.2 Album Discovery & Processing

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/album_discovery.py`
- **Function:** `discover_albums(root_path: Path) -> Iterator[AlbumInfo]`
- **Tasks:**
  - Find folders with `metadata.json` (user albums)
  - Parse album metadata (handle errors gracefully)
  - Create year-based albums for `Photos from YYYY/` folders
  - Generate UUID5 album IDs from folder paths
  - Insert albums into database via `AlbumDAL`
- **Tests:** User albums, year-based albums, metadata parsing errors, album_id generation
- **Acceptance:** All albums discovered, parsed, and stored in database
- **Note:** Must run BEFORE file processing (media items need album_id)

### 4.3 File Processor (CPU Work)

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/file_processor.py`
- **Function:** `process_file_cpu_work(file_path: Path) -> dict`
- **Tasks:**
  - EXIF extraction
  - Resolution extraction
  - Video metadata (if video)
  - CRC32 calculation
  - MIME detection
  - Content fingerprint
  - Error handling (wrap in try/except, return error details)
- **Tests:** Complete processing, partial metadata, error handling
- **Acceptance:** CPU-bound work isolated, can run in process pool
- **Note:** This runs in separate process in parallel architecture

### 4.4 Metadata Coordinator (I/O Work)

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/metadata_coordinator.py`
- **Function:** `coordinate_metadata(file_info: FileInfo, cpu_result: dict, album_id: str) -> MediaItemRecord`
- **Tasks:**
  - Parse JSON sidecar (I/O)
  - Combine with CPU results
  - Apply metadata aggregation (precedence rules)
  - Create `MediaItemRecord` with album_id
  - Error handling (log and record errors)
- **Tests:** Metadata combination, precedence, album_id assignment
- **Acceptance:** Metadata coordinated correctly, album_id always present
- **Note:** This runs in worker thread in parallel architecture

---

## Phase 5: Parallel Scanner (6 steps)

**Goal:** Implement multi-threaded + multi-process parallel scanner.

**Note:** This is the ONLY scanner implementation (no sequential version).

### 5.1 Worker Thread

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/parallel/worker_thread.py`
- **Function:** `worker_thread_main(work_queue: Queue, results_queue: Queue, process_pool: Pool)`
- **Tasks:**
  - Pull from work queue
  - Parse JSON sidecar (I/O)
  - Submit CPU work to process pool
  - Wait for result
  - Put result in results queue
- **Tests:** Queue operations, process pool interaction
- **Acceptance:** Worker thread coordinates I/O and CPU work

### 5.2 Batch Writer Thread

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/parallel/writer_thread.py`
- **Function:** `writer_thread_main(results_queue: Queue, db: DatabaseConnection, batch_size: int)`
- **Tasks:**
  - Pull from results queue
  - Batch writes (100-500 records)
  - Explicit BEGIN...COMMIT transactions
  - Update scan_runs.files_processed every 100 files
- **Tests:** Batch writing, transaction handling, progress updates
- **Acceptance:** Single writer thread handles all DB writes

### 5.3 Queue Management

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/parallel/queue_manager.py`
- **Class:** `QueueManager` with:
  - Create work queue (maxsize=1000)
  - Create results queue (maxsize=1000)
  - Backpressure handling
- **Tests:** Queue creation, backpressure
- **Acceptance:** Queues provide backpressure correctly

### 5.4 Progress Tracking

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/progress.py`
- **Class:** `ProgressTracker` with:
  - `update(files_processed: int, total_files: int)`
  - `get_progress() -> dict` (percentage, rate, ETA)
  - Log progress every 100 files
- **Tests:** Progress calculation, ETA estimation, logging
- **Acceptance:** Progress tracked and logged during scan

### 5.5 Parallel Scanner Orchestrator

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/parallel_scanner.py`
- **Class:** `ParallelScanner` with:
  - `scan(root_path: Path) -> ScanResult`
  - Startup: create process pool (M=CPU cores), queues (maxsize=1000), threads (N=2×CPU cores)
  - Album discovery: process albums first, store in database
  - File discovery: populate work queue with FileInfo (includes album_id from parent folder)
  - Change detection: check (path+size+fingerprint) before full processing
  - Shutdown: signal threads, join, close pool
  - Error handling: fatal errors abort gracefully
- **Tests:** Full parallel scan, startup/shutdown, change detection, album processing
- **Acceptance:** Complete parallel scan works end-to-end
- **Note:** See Performance_Analysis doc for expected throughput

### 5.6 Process Pool Saturation

- **Status:** ⬜
- **File:** Update `worker_thread.py`
- **Tasks:**
  - Use `pool.imap_unordered()` instead of `apply_async() + get()`
  - Batch submissions to keep pool saturated
  - Drain results asynchronously
- **Tests:** Pool utilization, throughput
- **Acceptance:** Process pool stays saturated during scan

---

## Phase 6: Post-Scan & Validation (2 steps)

**Goal:** Post-scan validation and summary reporting.

### 6.1 Post-Scan Validation

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/post_scan.py`
- **Function:** `validate_scan(scan_run_id: str, scan_start_time: datetime)`
- **Tasks:**
  - Mark inconsistent files (current scan_run_id, old timestamp)
  - Mark missing files (old scan_run_id, status='present')
  - Verify all present files have current scan_run_id
  - Log validation results
- **Tests:** Inconsistency detection, deletion detection, verification
- **Acceptance:** Post-scan validation works correctly

### 6.2 Scan Summary Report

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/summary.py`
- **Function:** `generate_summary(scan_run_id: str) -> dict`
- **Tasks:**
  - Query scan_runs table for statistics
  - Query processing_errors for error breakdown
  - Format summary (JSON + human-readable)
- **Tests:** Summary generation
- **Acceptance:** Summary includes all key metrics

---

## Phase 7: Edge Cases (2 steps)

**Goal:** Handle special cases and complex scenarios.

**Note:** Duplicates are cataloged, not deduplicated. Per architecture: "All file instances are cataloged (duplicates detected by file_size + CRC32). Deduplication is a query-time concern, not a storage constraint. Same photo in multiple albums = multiple database entries."

### 7.1 Live Photos

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/edge_cases/live_photos.py`
- **Function:** `detect_live_photo_pairs(files: list[FileInfo]) -> list[tuple[FileInfo, FileInfo]]`
- **Tasks:**
  - Match HEIC + MOV pairs by base name
  - Link via `live_photo_pair_id`
  - Store as separate media items
- **Tests:** Pair detection, linking
- **Acceptance:** Live Photos detected and linked

### 7.2 Edited Variants

- **Status:** ⬜
- **File:** `src/gphotos_321sync/media_scanner/edge_cases/edited_variants.py`
- **Function:** `detect_edited_variants(files: list[FileInfo]) -> dict[str, str]`
- **Tasks:**
  - Match files with `-edited` suffix to originals
  - Link via `original_media_item_id`
  - Store as separate media items
- **Tests:** Variant detection, linking
- **Acceptance:** Edited variants detected and linked

---

## Testing Strategy

### Unit Tests

- **Coverage target:** >80%
- **Run:** `pytest tests/media_scanner/ -v --cov=src/gphotos_321sync/media_scanner`
- **Focus:** Individual functions and classes

### Integration Tests

- **Scope:** End-to-end scan with test fixtures
- **Fixtures:**
  - Small library (10 files)
  - Medium library (1,000 files)
  - Edge cases (Live Photos, edited variants, missing metadata)
- **Run:** `pytest tests/media_scanner/integration/ -v`

### Performance Tests

- **Benchmarks:**
  - Sequential vs parallel comparison
  - Throughput measurement (files/sec)
  - Memory usage tracking
- **Run:** `pytest tests/media_scanner/test_performance.py -v`

### Test Fixtures

- **Location:** `tests/fixtures/`
- **Contents:**
  - Sample images (JPEG, PNG, HEIC)
  - Sample videos (MP4, MOV)
  - JSON sidecars
  - Album metadata.json files

---

## Implementation Order

**Recommended sequence:**

1. **Phase 1** (Foundation) - Infrastructure: errors, logging, tools, utilities
2. **Phase 2** (Database) - Schema, migrations, DAL (including albums)
3. **Phase 3** (Metadata) - Extraction logic for all metadata types
4. **Phase 4** (Discovery & Processing) - File/album discovery, processing logic
5. **Phase 5** (Parallel Scanner) - Orchestrator with threads + processes
6. **Phase 6** (Post-Scan) - Validation and reporting
7. **Phase 7** (Edge Cases) - Special cases and polish

**Rationale:** Build infrastructure first (errors/logging needed for debugging), then implement parallel scanner directly (no sequential version needed per performance analysis).

---

## Architecture Updates

As implementation progresses, update architecture documents:

- **Media_Scanning_Architecture.md** - Design decisions, schema changes
- **Performance_Analysis_Sequential_vs_Parallel.md** - Actual vs estimated performance
- **Media_Scanning_Implementation_Plan.md** (this file) - Progress tracking, blockers, lessons learned

---

## Document History

- 2025-10-13: Initial implementation plan created
- 2025-10-15: Phase 2 (Database Layer) completed with schema improvements
  - Added CHECK constraints for numeric sanity (all counters, dimensions, GPS bounds)
  - Added timestamp consistency checks (end >= start, last_seen >= first_seen)
  - Added hash format validation (CRC32: 8 hex chars, SHA-256: 64 hex chars)
  - Added EXIF orientation validation (1-8), tag_order validation (>= 0)
  - Added performance indexes: content_fingerprint, (album_id, capture_timestamp), relationship fields, error timestamps
  - See SCHEMA_IMPROVEMENTS.md for detailed documentation
