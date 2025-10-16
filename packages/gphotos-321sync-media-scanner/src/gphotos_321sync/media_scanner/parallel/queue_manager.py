"""Queue management for parallel media scanning.

Manages work and results queues with backpressure control.
"""

import logging
from queue import Queue
from typing import Tuple

logger = logging.getLogger(__name__)


class QueueManager:
    """Manages queues for parallel processing with backpressure.
    
    Creates and manages:
    - Work queue: (FileInfo, album_id) tuples for worker threads
    - Results queue: MediaItemRecord or error dicts for writer thread
    
    Backpressure is provided by maxsize limits on queues.
    """
    
    def __init__(self, work_queue_maxsize: int = 1000, results_queue_maxsize: int = 1000):
        """Initialize queue manager.
        
        Args:
            work_queue_maxsize: Maximum size of work queue (backpressure limit)
            results_queue_maxsize: Maximum size of results queue (backpressure limit)
        """
        self.work_queue_maxsize = work_queue_maxsize
        self.results_queue_maxsize = results_queue_maxsize
        
        self.work_queue: Queue = None
        self.results_queue: Queue = None
        
        logger.info(
            f"QueueManager initialized (work_maxsize={work_queue_maxsize}, "
            f"results_maxsize={results_queue_maxsize})"
        )
    
    def create_queues(self) -> Tuple[Queue, Queue]:
        """Create work and results queues.
        
        Returns:
            Tuple of (work_queue, results_queue)
        """
        self.work_queue = Queue(maxsize=self.work_queue_maxsize)
        self.results_queue = Queue(maxsize=self.results_queue_maxsize)
        
        logger.debug("Created work and results queues")
        
        return self.work_queue, self.results_queue
    
    def get_work_queue_depth(self) -> int:
        """Get current depth of work queue.
        
        Returns:
            Number of items in work queue
        """
        if self.work_queue is None:
            return 0
        return self.work_queue.qsize()
    
    def get_results_queue_depth(self) -> int:
        """Get current depth of results queue.
        
        Returns:
            Number of items in results queue
        """
        if self.results_queue is None:
            return 0
        return self.results_queue.qsize()
    
    def get_queue_stats(self) -> dict:
        """Get statistics about queue depths.
        
        Returns:
            Dict with work_queue_depth and results_queue_depth
        """
        return {
            "work_queue_depth": self.get_work_queue_depth(),
            "results_queue_depth": self.get_results_queue_depth(),
            "work_queue_maxsize": self.work_queue_maxsize,
            "results_queue_maxsize": self.results_queue_maxsize,
        }
    
    def shutdown(self):
        """Shutdown queues (cleanup).
        
        Note: Python queues don't need explicit cleanup, but this method
        is provided for consistency and future extensibility.
        """
        logger.debug("QueueManager shutdown")
        # Queues will be garbage collected
        self.work_queue = None
        self.results_queue = None
