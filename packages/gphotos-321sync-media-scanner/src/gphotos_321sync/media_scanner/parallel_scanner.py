"""Parallel media scanner orchestrator.

Coordinates all parallel processing components:
- Process pool for CPU work
- Worker threads for I/O coordination
- Writer thread for database writes
- Progress tracking
"""

import logging
import multiprocessing
import threading
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path
from typing import Optional

from .album_discovery import discover_albums
from .dal.albums import AlbumDAL
from .dal.media_items import MediaItemDAL
from .dal.scan_runs import ScanRunDAL
from .database import DatabaseConnection
from .discovery import discover_files
from .parallel.queue_manager import QueueManager
from .parallel.worker_thread import worker_thread_main
from .parallel.writer_thread import writer_thread_main
from .progress import ProgressTracker

logger = logging.getLogger(__name__)


class ParallelScanner:
    """Parallel media scanner with multi-threading and multi-processing.
    
    Architecture:
    - M worker processes (CPU-bound work: EXIF, fingerprinting, MIME detection)
    - N worker threads (I/O-bound work: file reading, JSON parsing)
    - 1 writer thread (database writes with batching)
    - Queues for backpressure control
    
    Configuration:
    - worker_processes: M = CPU cores (default)
    - worker_threads: N = 2 × CPU cores (default)
    - batch_size: Records per database transaction (default: 100)
    - queue_maxsize: Queue size limit for backpressure (default: 1000)
    """
    
    def __init__(
        self,
        db_path: Path,
        worker_processes: Optional[int] = None,
        worker_threads: Optional[int] = None,
        batch_size: int = 100,
        queue_maxsize: int = 1000,
        use_exiftool: bool = False,
        use_ffprobe: bool = False,
    ):
        """Initialize parallel scanner.
        
        Args:
            db_path: Path to SQLite database
            worker_processes: Number of worker processes (default: CPU count)
            worker_threads: Number of worker threads (default: 2 × CPU count)
            batch_size: Database batch size
            queue_maxsize: Queue size limit
            use_exiftool: Whether to use exiftool for EXIF
            use_ffprobe: Whether to use ffprobe for video metadata
        """
        self.db_path = db_path
        self.batch_size = batch_size
        self.queue_maxsize = queue_maxsize
        self.use_exiftool = use_exiftool
        self.use_ffprobe = use_ffprobe
        
        # Auto-detect CPU count with resource-friendly defaults
        # Use 75% of CPU cores to avoid maxing out the system
        cpu_count = multiprocessing.cpu_count()
        default_processes = max(1, int(cpu_count * 0.75))  # 75% of cores, minimum 1
        default_threads = max(2, cpu_count)  # 1× CPU count for I/O, minimum 2
        
        self.worker_processes = worker_processes or default_processes
        self.worker_threads = worker_threads or default_threads
        
        # Components (initialized during scan)
        self.queue_manager: Optional[QueueManager] = None
        self.process_pool: Optional[Pool] = None
        self.worker_thread_list: list = []
        self.writer_thread: Optional[threading.Thread] = None
        self.shutdown_event: Optional[threading.Event] = None
        self.progress_tracker: Optional[ProgressTracker] = None
        
        logger.info(
            f"ParallelScanner initialized: "
            f"processes={self.worker_processes}, threads={self.worker_threads}, "
            f"batch_size={batch_size}, queue_maxsize={queue_maxsize}"
        )
    
    def scan(self, target_media_path: Path) -> dict:
        """Scan directory tree and catalog media files.
        
        Args:
            target_media_path: Target media directory to scan
            
        Returns:
            Scan result summary dict
        """
        logger.info(f"Starting parallel scan of: {target_media_path}")
        
        # Create scan run
        db_conn = DatabaseConnection(self.db_path)
        conn = db_conn.connect()
        scan_run_dal = ScanRunDAL(conn)
        album_dal = AlbumDAL(conn)
        
        scan_run_id = scan_run_dal.create_scan_run()
        scan_start_time = datetime.now()
        
        logger.info(f"Created scan run: {scan_run_id}")
        
        try:
            # Phase 1: Album discovery (must run before file processing)
            logger.info("Phase 1: Discovering albums...")
            album_count = 0
            album_map = {}  # album_folder_path -> album_id
            
            for album_info in discover_albums(target_media_path, album_dal, scan_run_id):
                album_map[str(album_info.album_folder_path)] = album_info.album_id
                album_count += 1
            
            logger.info(f"Discovered {album_count} albums")
            
            # Phase 2: File discovery
            logger.info("Phase 2: Discovering files...")
            files_to_process = list(discover_files(target_media_path))
            total_files = len(files_to_process)
            
            logger.info(f"Discovered {total_files} files to process")
            
            if total_files == 0:
                logger.warning("No files found to process")
                scan_run_dal.complete_scan_run(scan_run_id, "completed")
                conn.close()
                return {
                    "scan_run_id": scan_run_id,
                    "status": "completed",
                    "total_files": 0,
                    "files_processed": 0,
                }
            
            # Phase 3: Parallel processing
            logger.info("Phase 3: Processing files in parallel...")
            
            # Initialize components
            self._initialize_components(total_files)
            
            # Start worker threads and writer thread
            self._start_workers(scan_run_id)
            
            # Populate work queue
            self._populate_work_queue(files_to_process, album_map, target_media_path)
            
            # Wait for completion
            self._wait_for_completion()
            
            # Shutdown workers
            self._shutdown_workers()
            
            # Final progress log
            self.progress_tracker.log_final_summary()
            
            # Complete scan run
            scan_run_dal.complete_scan_run(scan_run_id, "completed")
            
            # Get final statistics
            scan_run = scan_run_dal.get_scan_run(scan_run_id)
            
            logger.info(f"Scan completed: {scan_run_id}")
            
            return {
                "scan_run_id": scan_run_id,
                "status": "completed",
                "total_files": total_files,
                "files_processed": scan_run.get("files_processed", 0),
                "duration_seconds": scan_run.get("duration_seconds", 0),
            }
            
        except Exception as e:
            logger.error(f"Scan failed: {e}", exc_info=True)
            scan_run_dal.complete_scan_run(scan_run_id, "failed")
            raise
        
        finally:
            conn.close()
    
    def _initialize_components(self, total_files: int) -> None:
        """Initialize parallel processing components."""
        # Queue manager
        self.queue_manager = QueueManager(
            work_queue_maxsize=self.queue_maxsize,
            results_queue_maxsize=self.queue_maxsize,
        )
        self.queue_manager.create_queues()
        
        # Process pool
        self.process_pool = Pool(processes=self.worker_processes)
        logger.info(f"Created process pool with {self.worker_processes} processes")
        
        # Shutdown event
        self.shutdown_event = threading.Event()
        
        # Progress tracker
        self.progress_tracker = ProgressTracker(total_files=total_files)
    
    def _start_workers(self, scan_run_id: str) -> None:
        """Start worker threads and writer thread."""
        work_queue, results_queue = (
            self.queue_manager.work_queue,
            self.queue_manager.results_queue,
        )
        
        # Start worker threads
        for i in range(self.worker_threads):
            thread = threading.Thread(
                target=worker_thread_main,
                args=(
                    i,
                    work_queue,
                    results_queue,
                    self.process_pool,
                    scan_run_id,
                    self.use_exiftool,
                    self.use_ffprobe,
                    self.shutdown_event,
                ),
                name=f"Worker-{i}",
            )
            thread.start()
            self.worker_thread_list.append(thread)
        
        logger.info(f"Started {self.worker_threads} worker threads")
        
        # Start writer thread
        self.writer_thread = threading.Thread(
            target=writer_thread_main,
            args=(
                results_queue,
                str(self.db_path),
                scan_run_id,
                self.batch_size,
                self.shutdown_event,
            ),
            name="Writer",
        )
        self.writer_thread.start()
        logger.info("Started writer thread")
    
    def _populate_work_queue(
        self,
        files_to_process: list,
        album_map: dict,
        target_media_path: Path,
    ) -> None:
        """Populate work queue with files to process."""
        work_queue = self.queue_manager.work_queue
        
        for file_info in files_to_process:
            # Determine album_id from album folder path (relative)
            album_folder_str = str(file_info.album_folder_path)
            album_id = album_map.get(album_folder_str)
            
            if album_id is None:
                # Fallback: use parent folder path as album_id
                # This shouldn't happen if album discovery is correct
                logger.warning(
                    f"No album found for folder: {album_folder_str}, "
                    f"file: {file_info.relative_path}"
                )
                # Generate album_id from folder path
                from .dal.albums import AlbumDAL
                album_id = AlbumDAL.generate_album_id(album_folder_str)
            
            # Put work item in queue
            work_queue.put((file_info, album_id))
        
        logger.info(f"Populated work queue with {len(files_to_process)} items")
    
    def _wait_for_completion(self) -> None:
        """Wait for all work to complete."""
        # Wait for work queue to be empty
        self.queue_manager.work_queue.join()
        logger.info("Work queue empty")
        
        # Send sentinel to worker threads
        for _ in range(self.worker_threads):
            self.queue_manager.work_queue.put(None)
        
        # Wait for worker threads to finish
        for thread in self.worker_thread_list:
            thread.join()
        logger.info("All worker threads finished")
        
        # Wait for results queue to be empty
        self.queue_manager.results_queue.join()
        logger.info("Results queue empty")
        
        # Send sentinel to writer thread
        self.queue_manager.results_queue.put(None)
        
        # Wait for writer thread to finish
        self.writer_thread.join()
        logger.info("Writer thread finished")
    
    def _shutdown_workers(self) -> None:
        """Shutdown worker threads and process pool."""
        # Set shutdown event
        self.shutdown_event.set()
        
        # Close process pool
        self.process_pool.close()
        self.process_pool.join()
        logger.info("Process pool closed")
        
        # Cleanup
        self.queue_manager.shutdown()
