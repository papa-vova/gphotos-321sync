"""Tests for queue manager."""

import pytest
from queue import Queue

from gphotos_321sync.media_scanner.parallel.queue_manager import QueueManager


class TestQueueManager:
    """Tests for QueueManager class."""
    
    def test_initialization(self):
        """Test queue manager initialization."""
        qm = QueueManager(work_queue_maxsize=500, results_queue_maxsize=1000)
        
        assert qm.work_queue_maxsize == 500
        assert qm.results_queue_maxsize == 1000
        assert qm.work_queue is None
        assert qm.results_queue is None
    
    def test_create_queues(self):
        """Test queue creation."""
        qm = QueueManager(work_queue_maxsize=100, results_queue_maxsize=200)
        
        work_queue, results_queue = qm.create_queues()
        
        assert isinstance(work_queue, Queue)
        assert isinstance(results_queue, Queue)
        assert work_queue.maxsize == 100
        assert results_queue.maxsize == 200
        assert qm.work_queue is work_queue
        assert qm.results_queue is results_queue
    
    def test_get_work_queue_depth_empty(self):
        """Test work queue depth when empty."""
        qm = QueueManager()
        qm.create_queues()
        
        assert qm.get_work_queue_depth() == 0
    
    def test_get_work_queue_depth_with_items(self):
        """Test work queue depth with items."""
        qm = QueueManager()
        work_queue, _ = qm.create_queues()
        
        work_queue.put("item1")
        work_queue.put("item2")
        work_queue.put("item3")
        
        assert qm.get_work_queue_depth() == 3
    
    def test_get_results_queue_depth_empty(self):
        """Test results queue depth when empty."""
        qm = QueueManager()
        qm.create_queues()
        
        assert qm.get_results_queue_depth() == 0
    
    def test_get_results_queue_depth_with_items(self):
        """Test results queue depth with items."""
        qm = QueueManager()
        _, results_queue = qm.create_queues()
        
        results_queue.put("result1")
        results_queue.put("result2")
        
        assert qm.get_results_queue_depth() == 2
    
    def test_get_queue_stats(self):
        """Test getting queue statistics."""
        qm = QueueManager(work_queue_maxsize=500, results_queue_maxsize=1000)
        work_queue, results_queue = qm.create_queues()
        
        work_queue.put("item1")
        results_queue.put("result1")
        results_queue.put("result2")
        
        stats = qm.get_queue_stats()
        
        assert stats["work_queue_depth"] == 1
        assert stats["results_queue_depth"] == 2
        assert stats["work_queue_maxsize"] == 500
        assert stats["results_queue_maxsize"] == 1000
    
    def test_get_queue_depth_before_creation(self):
        """Test queue depth returns 0 before queues are created."""
        qm = QueueManager()
        
        assert qm.get_work_queue_depth() == 0
        assert qm.get_results_queue_depth() == 0
    
    def test_shutdown(self):
        """Test queue manager shutdown."""
        qm = QueueManager()
        qm.create_queues()
        
        qm.shutdown()
        
        assert qm.work_queue is None
        assert qm.results_queue is None
    
    def test_backpressure_work_queue(self):
        """Test backpressure on work queue."""
        qm = QueueManager(work_queue_maxsize=2)
        work_queue, _ = qm.create_queues()
        
        # Fill queue to max
        work_queue.put("item1")
        work_queue.put("item2")
        
        # Queue should be full
        assert work_queue.full()
        
        # Try to put with timeout (should fail)
        with pytest.raises(Exception):  # Queue.Full exception
            work_queue.put("item3", block=True, timeout=0.1)
    
    def test_backpressure_results_queue(self):
        """Test backpressure on results queue."""
        qm = QueueManager(results_queue_maxsize=2)
        _, results_queue = qm.create_queues()
        
        # Fill queue to max
        results_queue.put("result1")
        results_queue.put("result2")
        
        # Queue should be full
        assert results_queue.full()
        
        # Try to put with timeout (should fail)
        with pytest.raises(Exception):  # Queue.Full exception
            results_queue.put("result3", block=True, timeout=0.1)
    
    def test_default_maxsize(self):
        """Test default maxsize values."""
        qm = QueueManager()
        
        assert qm.work_queue_maxsize == 1000
        assert qm.results_queue_maxsize == 1000
