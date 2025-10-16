"""Progress tracking for media scanning.

Tracks and reports scan progress with ETA calculation.
"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Tracks scanning progress and calculates ETA.
    
    Features:
    - Files processed count
    - Processing rate (files/sec)
    - Estimated time remaining
    - Periodic logging (every N files)
    """
    
    def __init__(self, total_files: int, log_interval: int = 100):
        """Initialize progress tracker.
        
        Args:
            total_files: Total number of files to process
            log_interval: Log progress every N files
        """
        self.total_files = total_files
        self.log_interval = log_interval
        
        self.files_processed = 0
        self.start_time = time.time()
        self.last_log_time = self.start_time
        self.last_log_count = 0
        
        logger.info(f"ProgressTracker initialized (total_files={total_files})")
    
    def update(self, files_processed: int) -> None:
        """Update progress with current file count.
        
        Args:
            files_processed: Total number of files processed so far
        """
        self.files_processed = files_processed
        
        # Log progress at intervals
        if files_processed % self.log_interval == 0 and files_processed > 0:
            self._log_progress()
    
    def increment(self, count: int = 1) -> None:
        """Increment files processed counter.
        
        Args:
            count: Number of files to add to counter
        """
        self.files_processed += count
        
        if self.files_processed % self.log_interval == 0:
            self._log_progress()
    
    def get_progress(self) -> dict:
        """Get current progress statistics.
        
        Returns:
            Dict with progress metrics
        """
        elapsed_time = time.time() - self.start_time
        
        # Calculate rate
        if elapsed_time > 0:
            rate = self.files_processed / elapsed_time
        else:
            rate = 0.0
        
        # Calculate percentage
        if self.total_files > 0:
            percentage = (self.files_processed / self.total_files) * 100
        else:
            percentage = 0.0
        
        # Calculate ETA
        remaining_files = self.total_files - self.files_processed
        if rate > 0 and remaining_files > 0:
            eta_seconds = remaining_files / rate
        else:
            eta_seconds = 0.0
        
        return {
            "total_files": self.total_files,
            "files_processed": self.files_processed,
            "remaining_files": remaining_files,
            "percentage": percentage,
            "elapsed_seconds": elapsed_time,
            "rate_files_per_sec": rate,
            "eta_seconds": eta_seconds,
        }
    
    def _log_progress(self) -> None:
        """Log current progress."""
        progress = self.get_progress()
        
        # Calculate instantaneous rate since last log
        current_time = time.time()
        time_delta = current_time - self.last_log_time
        count_delta = self.files_processed - self.last_log_count
        
        if time_delta > 0:
            instant_rate = count_delta / time_delta
        else:
            instant_rate = 0.0
        
        logger.info(
            f"Progress: {self.files_processed}/{self.total_files} "
            f"({progress['percentage']:.1f}%) - "
            f"{progress['rate_files_per_sec']:.1f} files/sec (avg), "
            f"{instant_rate:.1f} files/sec (current) - "
            f"ETA: {self._format_time(progress['eta_seconds'])}"
        )
        
        self.last_log_time = current_time
        self.last_log_count = self.files_processed
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as human-readable time.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted string (e.g., "2h 15m 30s")
        """
        if seconds <= 0:
            return "0s"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    def log_final_summary(self) -> None:
        """Log final progress summary."""
        elapsed_time = time.time() - self.start_time
        
        if elapsed_time > 0:
            rate = self.files_processed / elapsed_time
        else:
            rate = 0.0
        
        logger.info(
            f"Scan complete: {self.files_processed}/{self.total_files} files processed "
            f"in {self._format_time(elapsed_time)} "
            f"({rate:.1f} files/sec average)"
        )
