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
- Uses file modification time comparison for efficient skip logic

### 2. Parallel Processing

- CPU-bound work (hashing, EXIF) uses process pool for true parallelism
- I/O-bound work (file reading, JSON parsing) uses thread pool
- Configurable with reasonable defaults

### 3. Duplicate Tolerance

- All file instances are cataloged (duplicates detected by file size + CRC32)
- Deduplication is a query-time concern, not a storage constraint

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

### Component Overview

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
│  - Identify media files and their sidecars                  │
│  - Identify albums                                          │
│  - Build work queue                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Processing Phase                        │
│  - Extract metadata from JSON sidecars                      │
│  - Extract EXIF data from media files                       │
│  - Calculate content hashes (for deduplication)             │
│  - Detect edited versions                                   │
│  - Process in parallel (configurable workers)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Storage Phase                          │
│  - Batch writes to database                                 │
│  - Single writer thread (SQLite constraint)                 │
│  - Transactional integrity                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Post-Processing Phase                     │
│  - Link edited versions to originals                        │
│  - Build album relationships                                │
│  - Generate statistics                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Media Database                           │
│  - Queryable catalog of all media                           │
│  - Supports multiple reconstruction strategies              │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```text
Takeout Folder
    │
    ▼
Discovery Thread (I/O-bound)
    ├─> Walk directory tree
    ├─> Build sidecar lookup map
    ├─> Identify albums
    └─> Put (media_file, json_file, album_id) into Work Queue
    
Work Queue (bounded, thread-safe)
    │
    ▼
Worker Threads (N threads, light work)
    ├─> Get work from queue
    ├─> Parse JSON sidecar (fast, Python)
    ├─> Submit to Process Pool for heavy work
    └─> Combine results → Results Queue
    
Process Pool (M processes, CPU-bound)
    ├─> EXIF extraction (images only)
    ├─> Content hashing (CRC32)
    └─> MIME type detection (magic bytes)
    
Results Queue (bounded, thread-safe)
    │
    ▼
Batch Writer Thread (single writer)
    ├─> Accumulate results into batch
    ├─> BEGIN IMMEDIATE transaction
    ├─> Insert into database tables
    └─> COMMIT transaction
    
SQLite Database (WAL mode)
```

## Database Design Principles

### Entity Model

**Core Entities:**

1. **Media Items** - Individual media files with all their metadata
2. **Albums** - Album metadata and identity (UUID-based)
   - Fields: `album_id` (UUID), `folder_path` (e.g., "Chair yoga"), `title`, `description`, `creation_timestamp`, `access_level`, `scan_timestamp`
3. **People Tags** - Face tags associated with media items
   - Fields: `media_item_id` (UUID), `person_name` (e.g., "Alice"), `tag_order` (position in array)

**Supporting Entities:**

1. **Scan Metadata** - Tracking information for resumability
2. **Scan Log** - Audit trail of scanning operations

### Key Design Decisions

#### 1. Catalog Everything, Deduplicate Later

- Store all instances of a file, even if they're duplicates
- Use content hash (CRC32) and file size for duplicate detection
- Deduplication is a query concern, not a storage constraint
- This enables flexible reconstruction strategies:
  - **Strategy A:** Keep only originals (no edited versions)
  - **Strategy B:** Keep edited versions where they exist, originals otherwise
  - **Strategy C:** Keep both originals and edited versions
  - **Strategy D:** Keep files from specific albums only

#### 2. File Lifecycle and Resumability

**Tracked fields:**

- `first_seen_timestamp` - when file first entered database
- `last_seen_timestamp` - updated every time we see the file during a scan
- `file_mtime` - filesystem modification time
- `status` - 'present', 'deleted', 'moved' (or similar)

**Scan algorithm:**

- For each file in filesystem:
  - Get `current_file_mtime` from filesystem
  - Query database for this file path
  - If file exists in DB AND `stored_file_mtime == current_file_mtime`:
    - File unchanged → skip full processing
    - Update: `last_seen_timestamp` = now
  - Otherwise (file is new or modified):
    - Full processing (extract metadata, hash, EXIF, etc.)
    - Update: `file_mtime` = `current_file_mtime`
    - Update: `last_seen_timestamp` = now
    - Update: `first_seen_timestamp` = now (only if new file)

**Deletion detection:**

- After scan completes: files with `last_seen_timestamp` older than scan start time are marked as deleted/moved

**Note:** Full history tracking (all changes over time) is post-MVP

#### 3. No Foreign Keys (Application-Enforced Integrity)

- Simplifies schema migrations
- Improves write performance
- Referential integrity enforced by application logic
- Easier to port to different databases

#### 4. Separate User Edits from Originals

- Store both original EXIF data and Google Photos metadata
- Detect when users edited timestamps or locations
- Preserve both versions for user choice during reconstruction

## Media Item Fields

For each file instance, store:

- **`relative_path`** - Full path within Takeout (e.g., `Google Photos/Chair yoga/IMG_123.jpg`)
- **`album_id`** - UUID of the album (generated during discovery)
- **`title`** - From JSON metadata (may differ from filename)
- **`file_size`** + **`crc32`** - For duplicate detection
- **Lifecycle timestamps** - `first_seen_timestamp`, `last_seen_timestamp`, `file_mtime`, `status`
- **Other metadata** - From JSON sidecar and EXIF

## Parallel Processing

**Architecture:** See Data Flow diagram above

**Thread pool (I/O):** File traversal, JSON parsing, coordination

**Process pool (CPU):** EXIF extraction, CRC32 hashing, MIME detection (bypasses Python GIL)

**Single writer:** Only writer thread touches database (SQLite constraint)

## Scan State Management

**Scan Metadata Table:**

- `current_scan_id` - Unique ID for current scan run (for tracking/logging)
- `scan_status` - 'in_progress', 'completed', 'failed'
- `current_scan_start_time` - When current scan started
- `last_completed_scan_time` - When last successful scan finished
- `total_files_scanned` - Progress counter

**Interruption Handling:**

- Graceful shutdown on SIGINT/SIGTERM
- Flush pending writes before exit
- Update `scan_status` to reflect final state
- Next run checks status and resumes if 'in_progress'

## Album Handling

**Two types:**

1. **User Albums** - Folders with `metadata.json` (have title, description, creation date, access level)
2. **Synthetic Albums** - `Photos from YYYY/` folders (chronological organization)

**Discovery:**

- Scan folders under `Google Photos/`
- Generate UUID for each unique folder path
- Store `folder_path` in albums table

**Note:** Google Takeout does not provide stable album IDs, so folder renames between exports create new album records

**Query:**

```sql
SELECT * FROM media_items WHERE album_id = :album_uuid
```

## Next Steps

This document establishes the high-level architecture and principles. The following sections will be added incrementally:

- [ ] **Detailed Database Schema** - Table definitions, indexes, constraints
- [ ] **Processing Pipeline Details** - Worker implementation, queue management
- [ ] **Resumability Mechanics** - State machine, recovery procedures
- [ ] **Duplicate Resolution Algorithms** - Query patterns, ranking logic
- [ ] **Album Reconciliation** - Handling multiple Takeout sessions
- [ ] **Error Handling** - Failure modes, retry logic, logging
- [ ] **Performance Tuning** - Batch sizes, worker counts, SQLite pragmas
- [ ] **Testing Strategy** - Unit tests, integration tests, test data
- [ ] **File Change Detection** - Track moved, deleted, and modified files (post-MVP)
- [ ] **Configuration Management** - Config file format, environment variables, defaults
- [ ] **Logging Strategy** - Log levels, log rotation, structured logging

---

**Document History:**

- 2025-10-12: Initial high-level architecture and principles
