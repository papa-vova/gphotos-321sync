# Media Processing Logic

## Overview

This document describes the complete processing flow, failure modes, and guarantees of the parallel media scanner. For an architectural overview and design context, see `Media_Scanning_Architecture.md`.

---

## Work Item Definition

A **work item** is a tuple of `(FileInfo, album_id)`:

### FileInfo Structure

`FileInfo` is a dataclass containing metadata about a discovered media file:

```python
@dataclass
class FileInfo:
    file_path: Path           # ABSOLUTE path to the media file on disk
    relative_path: Path       # Path relative to scan root (stored in DB, excludes Takeout/Google Photos)
    album_folder_path: Path   # Path relative to scan root (for album_id lookup, excludes Takeout/Google Photos)
    json_sidecar_path: Optional[Path]  # ABSOLUTE path to JSON sidecar if exists, or None
    file_size: int            # Size of the file in bytes
```

**Example:**

If scanning target_media_path=`/mnt/photos/` with Takeout structure:

- Scan root: `/mnt/photos/Takeout/Google Photos/` (where albums live)
- File: `/mnt/photos/Takeout/Google Photos/Photos from 2023/IMG_1234.jpg`

```python
FileInfo(
    file_path=Path("/mnt/photos/Takeout/Google Photos/Photos from 2023/IMG_1234.jpg"),  # ABSOLUTE
    relative_path=Path("Photos from 2023/IMG_1234.jpg"),  # relative to scan root
    album_folder_path=Path("Photos from 2023"),  # relative to scan root
    json_sidecar_path=Path("/mnt/photos/Takeout/Google Photos/Photos from 2023/IMG_1234.jpg.json"),  # ABSOLUTE or None
    file_size=2048576  # bytes
)
album_id="uuid-for-photos-from-2023"  # Looked up from album_map["Photos from 2023"]
```

**Field Purposes:**

- **`file_path`**: ABSOLUTE path - used to read the actual media file for processing
- **`relative_path`**: Path relative to scan root - stored in database, portable
- **`album_folder_path`**: Path relative to scan root - used to lookup album
- **`json_sidecar_path`**: ABSOLUTE path or None - Google Takeout metadata file
- **`file_size`**: File size in bytes - used for change detection

### Album Relationship

**`album_folder_path` is NOT the album title** - it's the folder path used to lookup the album.

**How it works:**

1. **Phase 1** creates albums from folders and builds `album_map`:

   ```python
   album_map = {
       "2023/Vacation": "uuid-for-vacation-album",
       "2023/Birthday": "uuid-for-birthday-album",
   }
   ```

2. **Phase 3** uses `album_folder_path` to lookup the `album_id`:

   ```python
   file_info.album_folder_path = Path("2023/Vacation")  # RELATIVE path
   album_id = album_map[str(file_info.album_folder_path)]  # "uuid-for-vacation-album"
   ```

**Album metadata** (stored separately in `albums` table):

```python
AlbumInfo(
    album_id="uuid-for-vacation-album",
    album_folder_path=Path("2023/Vacation"),  # Relative path
    title="Summer Vacation 2023",       # From metadata.json OR folder name
    description="Trip to Hawaii",       # From metadata.json (optional)
    creation_timestamp=datetime(...),   # From metadata.json (optional)
    is_user_album=True,                 # True if has metadata.json
    metadata_path=Path("2023/Vacation/metadata.json")
)
```

**Title determination:**

- **If `metadata.json` exists**: `title` comes from JSON (e.g., "Summer Vacation 2023")
- **If folder name is "Photos from 2023"**: `title = "Photos from 2023"` (year-based album)
- **Otherwise**: `title = album_folder_path.name` (e.g., "Vacation")

**Key point:** `album_folder_path` is just a lookup key. The actual album title and metadata are stored in the `albums` table.

---

## Processing Phases

### Phase 1: Album Discovery (Sequential)

**Runs in main thread before any parallel work:**

1. Discover all folders in directory tree
2. Create album records in database
3. Build `album_map: {album_folder_path -> album_id}`

**Why sequential:** Albums must exist before files can reference them.

### Phase 2: File Discovery (Sequential)

**Runs in main thread:**

1. Scan directory tree
2. Build list of `FileInfo` objects
3. Count total files for progress tracking

### Phase 3: Parallel Processing

**Multi-threaded + multi-process pipeline:**

```text
Main Thread → Work Queue → Worker Threads → Process Pool → Results Queue → Writer Thread → Database
```

---

## Complete Processing Flow

### Step-by-Step Execution

```text
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: Album Discovery (Sequential, Main Thread)          │
│ - Discover folders → Create albums in DB → Build album_map  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: File Discovery (Sequential, Main Thread)           │
│ - Scan directory tree → Build list of FileInfo objects      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: Parallel Processing                                │
│                                                             │
│ Step 1: Main thread puts (FileInfo, album_id) on work_queue │
│         work_queue.put((file_info, album_id))               │
│                                                             │
│ Step 2: Worker thread gets item from work_queue             │
│         item = work_queue.get()  # BLOCKS until available   │
│                                                             │
│ Step 3: Worker thread submits CPU work to process pool      │
│         future = pool.apply_async(process_file_cpu_work)    │
│         cpu_result = future.get()  # BLOCKS until done      │
│                                                             │
│ Step 4: Worker thread parses JSON sidecar (I/O)             │
│         metadata = coordinate_metadata(file_info,           │
│         cpu_result)                                         │
│                                                             │
│ Step 5: Worker thread puts result on results_queue          │
│         results_queue.put({"type": "media_item", ...})      │
│         work_queue.task_done()  # Mark work item complete   │
│                                                             │
│ Step 6: Writer thread gets batch from results_queue         │
│         result = results_queue.get()  # BLOCKS until        │
│         available                                           │
│                                                             │
│ Step 7: Writer thread batches results (100 items)           │
│         batch.append(result)                                │
│                                                             │
│ Step 8: Writer thread writes batch to DB                    │
│         conn.execute("BEGIN")                               │
│         for item in batch: insert_media_item(item)          │
│         conn.commit()  # ← PERSISTENCE POINT                │
│         results_queue.task_done()  # Mark result processed  │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**Main Thread:**

- Orchestrates the scan
- Populates work queue
- Waits for completion
- Handles shutdown

**Worker Threads (N threads, default = CPU count):**

- I/O-bound work: read files, parse JSON
- Submit CPU work to process pool
- Coordinate results
- Put results on results queue

**Process Pool (M processes, default = 75% of CPU cores):**

- CPU-bound work: EXIF extraction, fingerprinting, CRC32
- True parallelism (separate processes)
- Returns results to worker threads

**Writer Thread (1 thread):**

- Single writer for all database operations
- Batches writes (100-500 records per transaction)
- Explicit BEGIN...COMMIT transactions
- Updates progress every 100 files

---

## Queue Lifecycle

### When is a Work Item "Done"?

Work items are removed from queues at two points:

1. **From work_queue:** After `work_queue.task_done()` is called (Step 5)
2. **From results_queue:** After `results_queue.task_done()` is called (Step 8)

**Fully "done":** After database `COMMIT` succeeds (Step 8)

### Queue Backpressure

Both queues have `maxsize=1000` to prevent memory exhaustion:

- If work_queue is full, main thread blocks
- If results_queue is full, worker threads block
- This provides natural flow control

---

## Persistence Guarantees

### Data Durability by Stage

| Stage | In Memory? | On Disk? | Recoverable? |
|-------|-----------|----------|--------------|
| In work_queue | ✅ Yes | ❌ No | ❌ Lost on crash |
| In worker thread | ✅ Yes | ❌ No | ❌ Lost on crash |
| In process pool | ✅ Yes | ❌ No | ❌ Lost on crash |
| In results_queue | ✅ Yes | ❌ No | ❌ Lost on crash |
| In writer batch | ✅ Yes | ❌ No | ❌ Lost on crash |
| After BEGIN | ✅ Yes | ❌ No | ❌ Lost on crash |
| **After COMMIT** | ✅ Yes | **✅ Yes** | **✅ Recoverable** |

**Critical Point:** If the process crashes at ANY point before `COMMIT`, that work is **lost** and must be redone.

### Transaction Guarantees

**Atomicity:**

- Either **all items in a batch** are written, or **none** are
- If item #50 fails, items #1-49 are rolled back

**Example:**

- Batch of 100 media items
- Item #73 fails (corrupted data)
- **Result:** All 100 items rolled back, none written
- Batch can be retried or items processed individually

**Implementation:**

```python
# writer_thread.py
conn.execute("BEGIN")
try:
    for result in batch:
        if result["type"] == "media_item":
            media_dal.insert_media_item(record)
        elif result["type"] == "error":
            error_dal.insert_error(...)
    conn.commit()  # All or nothing
except Exception as e:
    conn.rollback()  # Undo all changes
    raise
```

---

## Failure Scenarios

### A) Worker Thread Dies

**What happens:**

```python
# worker_thread.py
try:
    while not shutdown_event.is_set():
        item = work_queue.get(timeout=0.1)
        # ... process item ...
        results_queue.put(result)
        work_queue.task_done()
except Exception as e:
    logger.error(f"Worker thread {thread_id} crashed: {e}")
    # Thread exits, work item is LOST
```

**Impact:**

- Work item in progress is **LOST** (not in queue, not in DB)
- Other worker threads continue normally
- Main thread doesn't detect the failure
- **Result:** Some files never get processed

**Current protection:** ❌ None - silent failure

### B) CPU Process Dies

**What happens:**

```python
# worker_thread.py
cpu_result = cpu_future.get()  # Blocks waiting for process
# If process crashes, this raises an exception
```

**Impact:**

- Worker thread catches exception, logs error
- Work item is **LOST**
- Thread continues with next item

**Current protection:** ❌ Exception logged, but work lost

### C) Writer Thread Dies

**What happens:**

```python
# writer_thread.py
try:
    while not shutdown_event.is_set() or not results_queue.empty():
        result = results_queue.get(timeout=0.1)
        # ... batch and write ...
except Exception as e:
    logger.error(f"Writer thread crashed: {e}")
    # Thread exits, ALL pending results are LOST
```

**Impact:**

- All items in results_queue are **LOST**
- All items in current batch are **LOST** (rolled back)
- Worker threads keep producing results (queue fills up)
- Eventually work_queue blocks (backpressure)

**Current protection:** ❌ None - catastrophic failure

### D) Main Process Crash

**What happens:**

- All threads and processes terminate immediately
- All in-flight work is lost
- Database may have partial results (only committed batches)

**Impact:**

- Must restart scan from beginning
- Already-processed files will be detected via change detection
- Wasted work for items that were in-flight

**Current protection:** ❌ No crash recovery mechanism

---

## Race Conditions Analysis

### ✅ No Race Conditions Between

**Worker Threads:**

- Each thread has its own work item
- No shared state between threads
- Queue operations are thread-safe (Python's `Queue` class)

**Worker Processes:**

- Each process works independently
- No shared memory
- Process pool handles synchronization

**Writer Thread:**

- Single writer (no concurrent DB writes)
- SQLite WAL mode allows concurrent reads
- No race conditions possible

### ⚠️ Potential Issues

**1. Queue Ordering:**

- Results may arrive out of order
- File #100 might be written before File #50
- **Impact:** None (each file is independent)

**2. Shutdown Race:**

- Main thread signals shutdown
- Worker threads may be mid-processing
- **Current handling:** Graceful shutdown with sentinel values

**3. Database Contention:**

- Multiple scan runs could run simultaneously
- **Current handling:** Each scan has unique `scan_run_id`
- **Note:** SQLite WAL mode prevents write conflicts

---

## Resource Management

### Default Configuration (4-core laptop)

- **Worker Processes:** 3 (75% of 4 cores)
- **Worker Threads:** 4 (100% of 4 cores)
- **Writer Thread:** 1
- **Total Threads:** 6 (4 workers + 1 writer + 1 main)

### CPU Usage

- **Core 1:** Main process + worker threads (mostly idle, waiting on I/O)
- **Core 2:** Worker process 1 (CPU-bound work)
- **Core 3:** Worker process 2 (CPU-bound work)
- **Core 4:** Worker process 3 (CPU-bound work)

**Result:** ~75% CPU usage (leaves 25% headroom for system)

### Why More Threads Than Processes?

Worker threads are often blocked on I/O:

- Reading files from disk
- Parsing JSON sidecars
- Waiting for process pool results

Having 4 threads for 3 processes ensures the process pool stays saturated:

- When thread 1 is waiting on disk, threads 2-4 can submit work
- Process pool always has work to do

---

## Current Guarantees

### ✅ What Works

**Correctness:**

- Transactional batches (all-or-nothing)
- Thread-safe queue operations
- No race conditions in normal operation
- Atomic database writes

**Performance:**

- True parallelism via multiprocessing
- Efficient batching (100-500 records per transaction)
- Backpressure prevents memory exhaustion
- Resource-friendly defaults (75% CPU)

**Observability:**

- Progress logging every 100 files
- Error logging for all failures
- Final summary with statistics

### ❌ Current Gaps

**Resilience:**

- No persistence until DB commit
- Lost work on thread/process death
- No crash recovery
- No health monitoring

**Reliability:**

- No retry mechanism for failed items
- Transient errors cause permanent loss
- Silent failures (dead threads)

**Resumability:**

- Can't resume interrupted scan
- Must start from scratch
- No progress checkpointing

---

## Future Improvements

For production use, consider adding:

1. **Worker Health Monitoring**
   - Detect dead threads/processes
   - Restart failed workers
   - Requeue lost work items

2. **Failed Item Retry Queue**
   - Retry transient errors (network, disk)
   - Exponential backoff
   - Dead letter queue for permanent failures

3. **Progress Checkpointing**
   - Persist scan state periodically
   - Resume from last checkpoint
   - Track processed files

4. **Graceful Degradation**
   - Continue with fewer workers if some die
   - Reduce parallelism on resource pressure
   - Adaptive batch sizing

5. **Metrics & Monitoring**
   - Queue depths
   - Processing rates
   - Error rates
   - Resource utilization

---

## Architecture Comparison

### Takeout Extractor vs Media Scanner

**Takeout Extractor (Sequential):**

```text
Processes: 1 (single-threaded)
Threads: 1 (main thread only)
CPU Usage: ~10-25% (single core, I/O bound)
Bottleneck: Disk I/O (unzipping)
```

**Why sequential works:** Extraction is I/O bound. Running multiple extractions in parallel would saturate disk I/O without improving throughput.

**Media Scanner (Parallel):**

```text
Processes: 6 (on 8-core system) - 75% of cores
Threads: 8 (on 8-core system) - 100% of cores
CPU Usage: ~60-75% (leaves headroom)
Bottleneck: CPU (EXIF, fingerprinting, MIME detection)
```

**Why parallel is needed:** Media scanning is CPU bound. Multiple cores are required to achieve acceptable throughput.

---

## Summary

The parallel media scanner is a **"best effort" implementation**:

- ✅ Fast and correct in the happy path
- ✅ Efficient resource usage
- ✅ Good observability
- ❌ Not resilient to failures
- ❌ No crash recovery

This is appropriate for:

- Interactive use (user can restart if needed)
- Reliable environments (stable hardware/software)
- Non-critical workloads

For production/enterprise use, additional resilience features would be recommended.
