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
║  │ Worker Thread 1  │  Worker Thread 2  │  ...  │  Worker Thread N│ ║
║  │                                                                │ ║
║  │ Each thread:                                                   │ ║
║  │   • Get work from queue                                        │ ║
║  │   • Parse JSON                                                 │ ║
║  │   • Submit file to Process Pool (below) ──┐                    │ ║
║  │   • Wait for result                       │                    │ ║
║  │   • Put result in Results Queue           │                    │ ║
║  └───────────────────────────────────────────┼────────────────────┘ ║
║                            │                 │                      ║
║                            ▼                 │                      ║
║  ┌────────────────────────────────────────────────────────────────┐ ║
║  │ Results Queue                             │                    │ ║
║  └───────────────────────────────────────────┼────────────────────┘ ║
║                            │                 │                      ║
║                            ▼                 │                      ║
║  ┌────────────────────────────────────────────────────────────────┐ ║
║  │ Batch Writer Thread                       │                    │ ║
║  │ • Reads from Results Queue                │                    │ ║
║  │ • Writes to SQLite                        │                    │ ║
║  └───────────────────────────────────────────┼────────────────────┘ ║
║                            │                 │                      ║
║                            ▼                 │                      ║
║  ┌────────────────────────────────────────────────────────────────┐ ║
║  │ SQLite Database (WAL mode)                │                    │ ║
║  └───────────────────────────────────────────┼────────────────────┘ ║
║                                              │                      ║
╚══════════════════════════════════════════════│══════════════════════╝
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
║  │ CPU work:   │  │ CPU work:   │  │ CPU work:   │  │ CPU work: │   ║
║  │ • EXIF      │  │ • EXIF      │  │ • EXIF      │  │ • EXIF    │   ║
║  │ • CRC32     │  │ • CRC32     │  │ • CRC32     │  │ • CRC32   │   ║
║  │ • MIME      │  │ • MIME      │  │ • MIME      │  │ • MIME    │   ║
║  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘   ║
║                                                                     ║
║                          (returns result to caller)                 ║
╚═════════════════════════════════════════════════════════════════════╝
```

## Database Schema

### Entities

#### 1. Media Items

- `media_item_id` (UUID) - Primary key, generated during scanning
- `relative_path` - Full path within Takeout
- `album_id` - UUID of the album
- `title` - From JSON metadata
- `file_size` + `crc32` - For duplicate detection
- `first_seen_timestamp` - When file first entered database
- `last_seen_timestamp` - When file was last seen in a scan
- `file_mtime` - Filesystem modification time
- `status` - present, missing (if not seen in latest scan)
- Other metadata from JSON sidecar and EXIF

#### 2. Albums

- `album_id` (UUID), `folder_path`, `title`, `description`, `creation_timestamp`, `access_level`, `scan_timestamp`
- Two types: User Albums (with metadata.json) and Synthetic Albums (Photos from YYYY/)
- Note: Google Takeout does not provide stable album IDs

#### 3. People

- `person_id` (UUID) - Generated by us
- `person_name` (unique) - From JSON metadata (e.g., "Alice")
- Note: Google Takeout does not provide stable person IDs
- Algorithm: Look up name, if exists use that person_id, else insert new row

#### 4. People Tags

- `media_item_id` (UUID) - References Media Items
- `person_id` (UUID) - References People
- `tag_order` - Position in array (0-based)

### Design Principles

#### Catalog everything, deduplicate later

- Store all file instances (duplicates detected by file size + CRC32)
- Deduplication is a query concern, not a storage constraint

#### Resumability

- Track file lifecycle with timestamps
- Skip unchanged files (compare `file_mtime`)
- Detect deletions (files with old `last_seen_timestamp`) as `status`

#### No foreign keys

- Application-enforced integrity
- Simpler migrations, better write performance

#### Preserve user edits

- Store both original EXIF and Google Photos metadata
- Detect edited timestamps/locations

## Next Steps

This document establishes the high-level architecture and principles. The following sections will be added incrementally:

- [ ] **Detailed Database Schema** - Table definitions, indexes, constraints
- [ ] **Basic Tests** - Cover happy paths first, then major edge cases
- [ ] **Processing Pipeline Details** - Worker implementation, queue management
- [ ] **Error Handling** - Failure modes, retry logic
- [ ] **Performance Tuning** - Batch sizes, worker counts, SQLite pragmas

---

**Document History:**

- 2025-10-12: Initial high-level architecture and principles
