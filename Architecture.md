# Architecture Documentation — MOSTLY WIP! CHECK THE CODE

## Overview

gphotos-321sync is designed as a modular, pipeline-based application for processing Google Photos Takeout archives. The architecture supports three deployment modes: local (desktop), hybrid (local + cloud), and cloud-only.

## High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                     Web UI (Browser)                        │
│                  React/Svelte + TailwindCSS                 │
└─────────────────────────────────────────────────────────────┘
                              │
                         HTTP/WebSocket
                              │
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                      │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │  REST API    │  │  WebSocket   │  │   Config     │      │
│   │  Endpoints   │  │  (Progress)  │  │   Routes     │      │
│   └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                    Python Function Calls
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Core Processing Layer                    │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │  Ingestion   │  │   Scanner    │  │  Normalizer  │      │
│   │   Pipeline   │  │   Pipeline   │  │   Pipeline   │      │
│   └──────────────┘  └──────────────┘  └──────────────┘      │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │   Gallery    │  │   Export     │  │    Sync      │      │
│   │   Builder    │  │   Module     │  │   Module     │      │
│   └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Data Access Layer                        │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │  Database    │  │  File System │  │   Cache      │      │
│   │  (SQLite/PG) │  │   Handler    │  │   Layer      │      │
│   └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Backend

- **Language:** Python 3.11+
- **Web Framework:** FastAPI
- **ASGI Server:** Uvicorn
- **ORM:** SQLAlchemy 2.0
- **Database:** SQLite (local), PostgreSQL (cloud)
- **Configuration:** TOML + Pydantic
- **Logging:** Python logging with structured JSON output

### Frontend (Planned)

- **Framework:** Svelte/SvelteKit
- **Styling:** TailwindCSS
- **Components:** shadcn-svelte
- **Icons:** Lucide

### Media Processing

- **Images:** Pillow (PIL), piexif, exifread
- **Videos:** ffmpeg-python
- **Archives:** py7zr, zipfile, tarfile

### Cloud (Optional)

- **Storage:** boto3 (S3), google-cloud-storage (GCS)
- **Task Queue:** Celery + Redis/SQS
- **Deployment:** Docker, Kubernetes

## Core Design Principles

### 1. Zero Hardcoded Configuration

- All configuration externalized to TOML files
- Environment variable overrides
- Multi-source configuration hierarchy
- Cross-platform path handling with `platformdirs`

### 2. Structured Logging

- No `print()` statements
- JSON-formatted logs for machine parsing
- Contextual fields (job_id, component, file paths)
- Multiple formatters (JSON, detailed, simple)
- Rotating file handlers

### 3. Pipeline Architecture

- Components implement `PipelineComponent[TInput, TOutput]`
- Async generators for streaming data
- Composable and chainable
- Context propagation through `PipelineContext`
- Each component is independently testable

### 4. Explicit Error Handling

- Custom exception hierarchy
- No silent failures or automatic fallbacks
- Errors propagate to caller for decision
- Rich context in exceptions
- Structured error logging

### 5. Resource Management

- Adaptive throttling based on system load
- Configurable CPU/memory limits
- Automatic worker pool sizing
- Disk I/O rate limiting
- Zero-configuration defaults

## Component Architecture

### Configuration System

**Location:** `src/gphotos_321sync/config/`

- **schema.py** - Pydantic models for type-safe configuration
- **loader.py** - Multi-source configuration loader
- **defaults.toml** - Default configuration shipped with app

**Features:**

- Path variable expansion (`${USER_DATA}`, etc.)
- Auto-detection of system resources
- Validation with Pydantic
- Environment variable overrides

### Logging Infrastructure

**Location:** `src/gphotos_321sync/logging_config.py`

**Components:**

- `StructuredFormatter` - JSON output
- `DetailedFormatter` - Human-readable detailed logs
- `SimpleFormatter` - Minimal console output
- `LogContext` - Context manager for structured fields

### Pipeline System

**Location:** `src/gphotos_321sync/pipeline/`

**Base Classes:**

- `PipelineComponent` - Abstract base for all components
- `Pipeline` - Orchestrator for chaining components
- `PipelineContext` - Shared context across pipeline stages
- `PipelineStage` - Enum for stage identification

**Key Features:**

- Type-safe with generics (`TInput`, `TOutput`)
- Async generators for memory efficiency
- Automatic logging and error handling
- Composable and reusable

### Error Handling

**Location:** `src/gphotos_321sync/errors.py`

**Exception Hierarchy:**

```text
GPSyncError (base)
├── ConfigurationError
├── ArchiveError
│   ├── ExtractionError
│   ├── CorruptedArchiveError
│   └── UnsupportedArchiveError
├── ScanError
├── MetadataError
│   ├── CorruptedFileError
│   └── MissingMetadataError
├── DatabaseError
├── StorageError
└── PipelineError
```

## Data Flow

### Typical Processing Pipeline

```text
1. Ingestion
   User uploads/selects Takeout archive
   ↓
2. Extraction
   Archive → Extracted files (temp directory)
   ↓
3. Scanning
   Discover all media files recursively
   ↓
4. Metadata Extraction
   Extract EXIF + Parse Google JSON
   ↓
5. Database Storage
   Save metadata to SQLite/PostgreSQL
   ↓
6. Normalization (optional)
   Embed metadata into files
   ↓
7. Gallery Building
   Organize by year/month/album
   ↓
8. Export/Sync (optional)
   Upload to cloud storage
```

### Pipeline Example

```python
pipeline = Pipeline("TakeoutProcessing")
pipeline.add_component(ArchiveExtractorComponent())
pipeline.add_component(FileScannerComponent())
pipeline.add_component(MetadataExtractorComponent())
pipeline.add_component(DatabaseWriterComponent())

context = PipelineContext(job_id=uuid.uuid4(), metadata={...})
async for result in pipeline.run(archive_path, context):
    # Process results
```

## API Endpoints (Current)

### Health & Configuration

- `GET /api/health` - Health check
- `GET /api/config` - Get current configuration (sanitized)

### Planned Endpoints

- `POST /api/scan/start` - Start scanning
- `GET /api/scan/status/{job_id}` - Get scan progress
- `WS /ws/progress/{job_id}` - Real-time progress updates
- `GET /api/gallery/years` - Get media grouped by year
- `GET /api/gallery/albums` - Get all albums

## Performance Considerations

### Parallelism Strategy

- **Process Pool** - CPU-bound tasks (EXIF extraction, hashing)
- **Thread Pool** - I/O-bound tasks (file reading, DB writes)
- **Async I/O** - Coordination and network operations

### Resource Limits

- Default: 70% CPU, 50% memory
- Adaptive throttling based on system load
- Configurable worker pool sizes
- Disk I/O rate limiting

### Scalability

- Streaming pipeline (memory-efficient)
- Batch processing for database operations
- Incremental processing (resume from interruption)
- Cloud mode: horizontal scaling with workers

## Security Considerations

### Sensitive Data

- Passwords via environment variables only
- API sanitizes sensitive config values
- No secrets in configuration files
- Cloud mode: authentication required

### File Safety

- Original files never modified without backup
- Integrity verification (checksums)
- Atomic operations where possible
- Transaction-based database updates
