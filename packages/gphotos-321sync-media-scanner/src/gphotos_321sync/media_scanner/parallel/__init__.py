"""Parallel processing components for media scanner.

This package contains the parallel processing infrastructure:
- Worker threads: Coordinate I/O and CPU work
- Writer thread: Batch database writes
- Queue manager: Queue creation and backpressure
- Orchestrator: Main parallel scanner coordinator
"""

from .worker_thread import worker_thread_main

__all__ = [
    "worker_thread_main",
]
