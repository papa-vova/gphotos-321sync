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

## Database Schema

### Entities

#### 1. Media Items

- `relative_path` - Full path within Takeout
- `album_id` - UUID of the album
- `title` - From JSON metadata
- `file_size` + `crc32` - For duplicate detection
- `first_seen_timestamp`, `last_seen_timestamp`, `file_mtime`, `status` - Lifecycle tracking
- Other metadata from JSON sidecar and EXIF

#### 2. Albums

- `album_id` (UUID), `folder_path`, `title`, `description`, `creation_timestamp`, `access_level`, `scan_timestamp`
- Two types: User Albums (with metadata.json) and Synthetic Albums (Photos from YYYY/)
- Note: Google Takeout does not provide stable album IDs

#### 3. People Tags

- `media_item_id`, `person_name`, `tag_order`

#### 4. Scan Metadata

- `current_scan_id`, `scan_status`, `current_scan_start_time`, `last_completed_scan_time`, `total_files_scanned`

#### 5. Scan Log

- Audit trail of scanning operations

### Design Principles

#### Catalog everything, deduplicate later

- Store all file instances (duplicates detected by file size + CRC32)
- Deduplication is a query concern, not a storage constraint

#### Resumability

- Track file lifecycle with timestamps
- Skip unchanged files (compare `file_mtime`)
- Detect deletions (files with old `last_seen_timestamp`)

#### No foreign keys

- Application-enforced integrity
- Simpler migrations, better write performance

#### Preserve user edits

- Store both original EXIF and Google Photos metadata
- Detect edited timestamps/locations

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
