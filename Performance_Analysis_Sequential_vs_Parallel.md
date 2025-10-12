# Performance Analysis: Sequential vs Parallel Media Scanning

**Status:** 📊 Analysis - Design Phase

This document compares the performance characteristics of two scanning approaches for Google Photos Takeout media libraries.

## Table of Contents

- [Architecture Comparison](#architecture-comparison)
- [Performance Model](#performance-model)
- [Cost Analysis by Library Size](#cost-analysis-by-library-size)
- [Implementation Details](#implementation-details)

---

## Architecture Comparison

### Sequential (Single-threaded)

```text
┌─────────────────────────────────────────────┐
│         MAIN PYTHON PROCESS                 │
│                                             │
│  Main Thread (does everything):             │
│    1. Walk filesystem                       │
│    2. For each file:                        │
│       • Read JSON sidecar                   │
│       • Extract EXIF                        │
│       • Calculate CRC32                     │
│       • Detect MIME type                    │
│       • Write to database                   │
│    3. Done                                  │
└─────────────────────────────────────────────┘
```

**Characteristics:**

- Simple, straightforward code
- No parallelism overhead
- Blocked by I/O and CPU sequentially
- Minimal memory footprint

### Parallel (Multi-threaded + Multi-process)

```text
┌─────────────────────────────────────────────┐
│         MAIN PYTHON PROCESS                 │
│                                             │
│  • Orchestrator (startup/shutdown)          │
│  • N Worker Threads (I/O + coordination)    │
│  • 1 Batch Writer Thread (DB writes)        │
│  • 2 Queues (work, results)                 │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│         SEPARATE PROCESS POOL               │
│                                             │
│  • M Worker Processes (CPU-bound work)      │
│  • EXIF, CRC32, MIME detection              │
└─────────────────────────────────────────────┘
```

**Characteristics:**

- Complex coordination
- Parallelism overhead (startup, IPC)
- I/O and CPU work happen concurrently
- Higher memory footprint

---

## Performance Model

### Assumptions

**Hardware:**

- CPU: 8 cores (typical modern machine)
- Disk: SSD with ~500 MB/s read speed
- RAM: 16 GB available

**File characteristics:**

- Average image size: 3 MB
- Average video size: 50 MB
- Image:Video ratio: 90:10
- Average file size: 7.7 MB
- JSON sidecar: ~2 KB per file

**Operation timings (per file):**

| Operation | Time | Type |
|-----------|------|------|
| Read JSON sidecar | 0.5 ms | I/O |
| Parse JSON | 0.2 ms | CPU (light) |
| Read file for EXIF | 2 ms | I/O |
| Extract EXIF | 5 ms | CPU |
| Read file for CRC32 | 15 ms | I/O |
| Calculate CRC32 | 10 ms | CPU |
| MIME detection | 1 ms | CPU |
| DB write (batched) | 0.1 ms | I/O |
| **Total per file** | **~34 ms** | |

**Parallel configuration:**

- N = 16 worker threads
- M = 8 worker processes
- Batch size = 100 records

### Cost Breakdown

#### Sequential Architecture

**Startup cost:**

- Open database connection: 10 ms
- **Total startup: ~10 ms**

**Per-file cost:**

- All operations sequential: 34 ms/file

**Shutdown cost:**

- Close database: 5 ms
- **Total shutdown: ~5 ms**

**Memory:**

- Base Python process: ~50 MB
- Database connection: ~10 MB
- File buffers: ~10 MB
- **Total: ~70 MB**

#### Parallel Architecture

**Startup cost:**

- Create process pool (M=8): 200 ms (spawn 8 Python interpreters)
- Create queues: 1 ms
- Start N+1 threads: 5 ms
- Open database connection: 10 ms
- **Total startup: ~216 ms**

**Per-file cost (with parallelism):**

- I/O operations can overlap with CPU operations
- Multiple files processed simultaneously
- Effective throughput: ~4-5 ms/file (8x speedup on CPU, limited by I/O)

**Shutdown cost:**

- Signal threads: 1 ms
- Join threads: 10 ms
- Close process pool: 50 ms
- Close database: 5 ms
- **Total shutdown: ~66 ms**

**Memory:**

- Base Python process: ~50 MB
- M processes (8 × 80 MB): ~640 MB
- N threads (16 × 2 MB): ~32 MB
- Queues (2 × 10 MB): ~20 MB
- Database connection: ~10 MB
- **Total: ~736 MB**

---

## Cost Analysis by Library Size

### Small Library (1,000 files, ~7.7 GB)

#### Sequential

```text
Startup:     0.01 s
Processing:  34.0 s  (1,000 × 34 ms)
Shutdown:    0.005 s
─────────────────────
Total:       34.0 s
Memory:      70 MB
```

#### Parallel

```text
Startup:     0.22 s
Processing:  5.0 s   (1,000 × 5 ms effective)
Shutdown:    0.07 s
─────────────────────
Total:       5.3 s
Memory:      736 MB
Speedup:     6.4x
```

**Analysis:**

- Parallel wins significantly despite overhead
- Startup/shutdown overhead is 5% of total time
- Memory cost: 10.5x higher

---

### Medium Library (10,000 files, ~77 GB)

#### Sequential (Medium Library)

```text
Startup:     0.01 s
Processing:  340 s   (10,000 × 34 ms)
Shutdown:    0.005 s
─────────────────────
Total:       340 s (5.7 min)
Memory:      70 MB
```

#### Parallel (Medium Library)

```text
Startup:     0.22 s
Processing:  50 s    (10,000 × 5 ms effective)
Shutdown:    0.07 s
─────────────────────
Total:       50.3 s (0.8 min)
Memory:      736 MB
Speedup:     6.8x
```

**Analysis:**

- Parallel wins decisively
- Startup/shutdown overhead is <1% of total time
- Memory cost: 10.5x higher (still acceptable)

---

### Large Library (100,000 files, ~770 GB)

#### Sequential (Large Library)

```text
Startup:     0.01 s
Processing:  3,400 s  (100,000 × 34 ms)
Shutdown:    0.005 s
─────────────────────
Total:       3,400 s (56.7 min)
Memory:      70 MB
```

#### Parallel (Large Library)

```text
Startup:     0.22 s
Processing:  500 s    (100,000 × 5 ms effective)
Shutdown:    0.07 s
─────────────────────
Total:       500.3 s (8.3 min)
Memory:      736 MB
Speedup:     6.8x
```

**Analysis:**

- Parallel wins massively
- Startup/shutdown overhead is negligible (<0.1%)
- Memory cost: 10.5x higher (still reasonable for modern systems)
- Time savings: 48 minutes

---

### Very Large Library (500,000 files, ~3.85 TB)

#### Sequential (Very Large Library)

```text
Startup:     0.01 s
Processing:  17,000 s  (500,000 × 34 ms)
Shutdown:    0.005 s
─────────────────────
Total:       17,000 s (4.7 hours)
Memory:      70 MB
```

#### Parallel (Very Large Library)

```text
Startup:     0.22 s
Processing:  2,500 s   (500,000 × 5 ms effective)
Shutdown:    0.07 s
─────────────────────
Total:       2,500 s (41.7 min)
Memory:      736 MB
Speedup:     6.8x
```

**Analysis:**

- Parallel wins overwhelmingly
- Startup/shutdown overhead is negligible
- Memory cost: 10.5x higher (acceptable)
- Time savings: 4 hours

---

## Summary Table

| Library Size | Files | Sequential Time | Parallel Time | Speedup | Memory Cost |
|--------------|-------|-----------------|---------------|---------|-------------|
| **Small** | 1K | 34 s | 5.3 s | 6.4x | 10.5x (736 MB) |
| **Medium** | 10K | 5.7 min | 50 s | 6.8x | 10.5x (736 MB) |
| **Large** | 100K | 56.7 min | 8.3 min | 6.8x | 10.5x (736 MB) |
| **Very Large** | 500K | 4.7 hours | 41.7 min | 6.8x | 10.5x (736 MB) |

---

## Key Insights

### When Sequential Makes Sense

- **Tiny libraries** (<100 files): Overhead dominates, sequential is simpler
- **Memory-constrained environments**: <1 GB RAM available
- **Debugging**: Simpler to reason about and debug

### When Parallel Makes Sense

- **Any library >1,000 files**: Speedup justifies complexity
- **Large libraries**: Time savings are massive (hours)
- **Modern hardware**: 8+ cores, 8+ GB RAM (typical today)
- **Production use**: Worth the implementation complexity

### Bottleneck Analysis

**Sequential:**

- Bottleneck: Everything is sequential, no parallelism
- Limited by: Sum of all operation times

**Parallel:**

- Bottleneck: I/O bandwidth (disk read speed)
- CPU work happens in parallel while waiting for I/O
- Effective speedup: ~6-7x (not 8x due to I/O limits)

### Optimization Opportunities

**Sequential:**

- Minimal - already simple
- Could batch DB writes (small gain)

**Parallel:**

- Tune N (worker threads) based on I/O concurrency
- Tune M (worker processes) based on CPU cores
- Adjust batch size for DB writes
- Could achieve 7-8x speedup with tuning

---

## Implementation Details

### Thread vs Process: What They Are

**Thread:**

- Lightweight execution unit that runs **inside** a Python process
- Shares memory with other threads in the same process
- Can access the same variables, queues, database connections
- Limited by Python's GIL (Global Interpreter Lock) for CPU work
- Created with: `threading.Thread(target=function)`

**Process:**

- Completely separate Python interpreter with its own memory
- Cannot directly access variables from other processes
- Must communicate via serialization (pickle data, send, receive)
- NOT limited by GIL - can do true parallel CPU work
- Created with: `multiprocessing.Process()` or `multiprocessing.Pool()`

### Orchestrator Responsibilities

#### At Startup

```python
import threading
import multiprocessing
import queue

# 1. Create Process Pool (M separate Python processes start up)
process_pool = multiprocessing.Pool(processes=M)  # ~200ms for M=8

# 2. Create queues (shared between threads in main process)
work_queue = queue.Queue(maxsize=1000)
results_queue = queue.Queue(maxsize=1000)

# 3. Start Worker Threads (N threads in main process)
worker_threads = []
for i in range(N):
    t = threading.Thread(
        target=worker_function, 
        args=(work_queue, results_queue, process_pool)
    )
    t.start()
    worker_threads.append(t)

# 4. Start Batch Writer Thread
writer_thread = threading.Thread(
    target=writer_function, 
    args=(results_queue, db)
)
writer_thread.start()

# 5. Walk filesystem and populate work_queue
for file in walk_filesystem():
    work_queue.put(file)
```

**Cost:** ~216 ms (one-time)

#### During Execution

The orchestrator **waits** - all work happens in threads and processes:

- **Worker Threads**: Pull from work_queue, call process_pool, put in results_queue
- **Process Pool**: Handles CPU work when called
- **Writer Thread**: Pulls from results_queue, writes to DB

**Cost:** 0 (orchestrator is idle)

#### At Shutdown

```python
# 1. Signal workers to stop
for i in range(N):
    work_queue.put(None)

# 2. Wait for worker threads
for t in worker_threads:
    t.join()

# 3. Signal writer to stop
results_queue.put(None)
writer_thread.join()

# 4. Shutdown process pool
process_pool.close()
process_pool.join()
```

**Cost:** ~66 ms (one-time)

---

## Recommendation

**Use parallel architecture for any library >1,000 files.**

**Rationale:**

- 6-7x speedup on realistic workloads
- Memory cost (736 MB) is acceptable on modern systems
- Startup/shutdown overhead becomes negligible at scale
- Time savings are substantial (minutes to hours)

**Configuration:**

- N = 2-4x CPU cores for worker threads (e.g., 16-32 for 8-core CPU)
  - Threads do I/O work and block waiting, so oversubscribe
- M = CPU cores for process pool (e.g., 8 for 8-core CPU)
  - Processes do CPU work, match core count for true parallelism
- Batch size = 100-500 (tune based on DB performance)

**Trade-offs accepted:**

- 10x memory usage (70 MB → 736 MB)
- Implementation complexity
- Startup/shutdown overhead (~282 ms total)

---

## Appendix: Visual Architecture Comparison

### Main Process vs Process Pool

```text
┌─────────────────────────────────────────────────────────────┐
│              MAIN PYTHON PROCESS                            │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ Thread 1 │  │ Thread 2 │  │ Thread 3 │  │ Thread N │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
│                                                             │
│  All threads share:                                         │
│  • Same memory space                                        │
│  • Same variables                                           │
│  • Same queues                                              │
│  • Same database connection                                 │
└─────────────────────────────────────────────────────────────┘

                         │ (calls)
                         ▼

┌─────────────────────────────────────────────────────────────┐
│              SEPARATE PROCESS POOL                          │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │Process 1 │  │Process 2 │  │Process 3 │  │Process M │     │
│  │          │  │          │  │          │  │          │     │
│  │Own memory│  │Own memory│  │Own memory│  │Own memory│     │
│  │Own Python│  │Own Python│  │Own Python│  │Own Python│     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
│                                                             │
│  Each process has:                                          │
│  • Separate memory space                                    │
│  • Separate Python interpreter                              │
│  • Cannot access main process variables directly            │
└─────────────────────────────────────────────────────────────┘
```

### Worker Thread Example

```python
def worker_function(work_queue, results_queue, process_pool):
    """Worker thread that coordinates I/O and CPU work"""
    while True:
        # 1. Get work (I/O-bound, thread is fine)
        work_item = work_queue.get()
        if work_item is None:  # Sentinel
            break
        
        # 2. Parse JSON (I/O-bound, thread is fine)
        json_data = parse_json(work_item.json_file)
        
        # 3. Submit CPU work to process pool
        future = process_pool.apply_async(
            cpu_intensive_work,  # This runs in a separate process
            args=(work_item.file_path,)
        )
        
        # 4. Wait for result (thread blocks, but that's OK)
        cpu_result = future.get()  # Blocks until process returns
        
        # 5. Combine results and put in results queue
        combined = {**json_data, **cpu_result}
        results_queue.put(combined)

def cpu_intensive_work(file_path):
    """This runs in a separate process"""
    exif = extract_exif(file_path)  # CPU-intensive
    crc32 = calculate_crc32(file_path)  # CPU-intensive
    mime = detect_mime(file_path)  # CPU-intensive
    return {'exif': exif, 'crc32': crc32, 'mime': mime}
```
