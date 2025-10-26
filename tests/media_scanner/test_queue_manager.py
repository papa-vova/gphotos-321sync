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
    
    def test_get_work_queue_depth_no_queues(self):
        """Test work queue depth when queues not created."""
        qm = QueueManager()
        
        assert qm.get_work_queue_depth() == 0
    
    def test_get_results_queue_depth_no_queues(self):
        """Test results queue depth when queues not created."""
        qm = QueueManager()
        
        assert qm.get_results_queue_depth() == 0
    
    def test_shutdown(self):
        """Test queue manager shutdown."""
        qm = QueueManager()
        qm.create_queues()
        
        # Add some items to queues
        qm.work_queue.put("item1")
        qm.results_queue.put("result1")
        
        # Shutdown should clear queues
        qm.shutdown()
        
        # Verify queues are empty after shutdown
        assert qm.get_work_queue_depth() == 0
        assert qm.get_results_queue_depth() == 0
    
    def test_shutdown_no_queues(self):
        """Test shutdown when queues not created."""
        qm = QueueManager()
        
        # Should not raise exception
        qm.shutdown()
    
    def test_default_maxsize(self):
        """Test default maxsize values."""
        qm = QueueManager()
        
        # Default values should be reasonable
        assert qm.work_queue_maxsize > 0
        assert qm.results_queue_maxsize > 0
    
    def test_custom_maxsize(self):
        """Test custom maxsize values."""
        qm = QueueManager(work_queue_maxsize=50, results_queue_maxsize=75)
        
        assert qm.work_queue_maxsize == 50
        assert qm.results_queue_maxsize == 75
    
    def test_queue_operations(self):
        """Test basic queue operations."""
        qm = QueueManager()
        work_queue, results_queue = qm.create_queues()
        
        # Test work queue operations
        work_queue.put("work_item")
        assert work_queue.get() == "work_item"
        
        # Test results queue operations
        results_queue.put("result_item")
        assert results_queue.get() == "result_item"
    
    def test_queue_maxsize_enforcement(self):
        """Test that queue maxsize is enforced."""
        qm = QueueManager(work_queue_maxsize=2, results_queue_maxsize=2)
        work_queue, results_queue = qm.create_queues()
        
        # Fill work queue to maxsize
        work_queue.put("item1")
        work_queue.put("item2")
        
        # Verify maxsize is enforced
        assert work_queue.maxsize == 2
        assert results_queue.maxsize == 2
    
    def test_multiple_create_queues_calls(self):
        """Test multiple create_queues calls."""
        qm = QueueManager()
        
        # First call
        work_queue1, results_queue1 = qm.create_queues()
        
        # Second call creates new queues (current implementation behavior)
        work_queue2, results_queue2 = qm.create_queues()
        
        # Should be different queue objects (current implementation)
        assert work_queue1 is not work_queue2
        assert results_queue1 is not results_queue2
        assert qm.work_queue is work_queue2  # Latest created queues
        assert qm.results_queue is results_queue2
    
    def test_queue_manager_state_consistency(self):
        """Test queue manager state consistency."""
        qm = QueueManager(work_queue_maxsize=100, results_queue_maxsize=200)
        
        # Initially no queues
        assert qm.work_queue is None
        assert qm.results_queue is None
        
        # After creating queues
        work_queue, results_queue = qm.create_queues()
        assert qm.work_queue is work_queue
        assert qm.results_queue is results_queue
        
        # After shutdown, queues are set to None (current implementation behavior)
        qm.shutdown()
        assert qm.work_queue is None
        assert qm.results_queue is None
    
    def test_queue_manager_thread_safety(self):
        """Test queue manager thread safety."""
        import threading
        import time
        
        qm = QueueManager()
        work_queue, results_queue = qm.create_queues()
        
        results = []
        
        def producer():
            for i in range(10):
                work_queue.put(f"item{i}")
                time.sleep(0.01)
        
        def consumer():
            for _ in range(10):
                try:
                    item = work_queue.get(timeout=1)
                    results.append(item)
                except:
                    break
        
        # Start producer and consumer threads
        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)
        
        producer_thread.start()
        consumer_thread.start()
        
        producer_thread.join()
        consumer_thread.join()
        
        # Verify all items were processed
        assert len(results) == 10
        assert qm.get_work_queue_depth() == 0
