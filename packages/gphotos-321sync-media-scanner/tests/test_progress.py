"""Tests for progress tracker."""

import time
import pytest

from gphotos_321sync.media_scanner.progress import ProgressTracker


class TestProgressTracker:
    """Tests for ProgressTracker class."""
    
    def test_initialization(self):
        """Test progress tracker initialization."""
        tracker = ProgressTracker(total_files=1000, log_interval=50)
        
        assert tracker.total_files == 1000
        assert tracker.log_interval == 50
        assert tracker.files_processed == 0
    
    def test_update(self):
        """Test updating progress."""
        tracker = ProgressTracker(total_files=100)
        
        tracker.update(25)
        
        assert tracker.files_processed == 25
    
    def test_increment(self):
        """Test incrementing progress."""
        tracker = ProgressTracker(total_files=100)
        
        tracker.increment()
        assert tracker.files_processed == 1
        
        tracker.increment(5)
        assert tracker.files_processed == 6
    
    def test_get_progress_initial(self):
        """Test getting progress at start."""
        tracker = ProgressTracker(total_files=100)
        
        progress = tracker.get_progress()
        
        assert progress["total_files"] == 100
        assert progress["files_processed"] == 0
        assert progress["remaining_files"] == 100
        assert progress["percentage"] == 0.0
    
    def test_get_progress_halfway(self):
        """Test getting progress at 50%."""
        tracker = ProgressTracker(total_files=100)
        tracker.update(50)
        
        progress = tracker.get_progress()
        
        assert progress["files_processed"] == 50
        assert progress["remaining_files"] == 50
        assert progress["percentage"] == 50.0
    
    def test_get_progress_complete(self):
        """Test getting progress at 100%."""
        tracker = ProgressTracker(total_files=100)
        tracker.update(100)
        
        progress = tracker.get_progress()
        
        assert progress["files_processed"] == 100
        assert progress["remaining_files"] == 0
        assert progress["percentage"] == 100.0
    
    def test_rate_calculation(self):
        """Test files/sec rate calculation."""
        tracker = ProgressTracker(total_files=100)
        
        # Simulate processing 10 files
        tracker.update(10)
        
        # Wait a bit to get measurable elapsed time
        time.sleep(0.1)
        
        progress = tracker.get_progress()
        
        # Rate should be positive
        assert progress["rate_files_per_sec"] > 0
        # Should be roughly 10 files / 0.1 sec = ~100 files/sec
        # (Allow wide margin for timing variations)
        assert 50 < progress["rate_files_per_sec"] < 200
    
    def test_eta_calculation(self):
        """Test ETA calculation."""
        tracker = ProgressTracker(total_files=100)
        
        # Process 50 files
        tracker.update(50)
        time.sleep(0.05)  # Simulate 0.05 seconds elapsed
        
        progress = tracker.get_progress()
        
        # ETA should be positive (50 files remaining)
        assert progress["eta_seconds"] >= 0
    
    def test_eta_at_completion(self):
        """Test ETA is 0 when complete."""
        tracker = ProgressTracker(total_files=100)
        tracker.update(100)
        
        progress = tracker.get_progress()
        
        assert progress["eta_seconds"] == 0.0
    
    def test_format_time_seconds(self):
        """Test time formatting for seconds."""
        tracker = ProgressTracker(total_files=100)
        
        assert tracker._format_time(0) == "0s"
        assert tracker._format_time(30) == "30s"
        assert tracker._format_time(59) == "59s"
    
    def test_format_time_minutes(self):
        """Test time formatting for minutes."""
        tracker = ProgressTracker(total_files=100)
        
        assert tracker._format_time(60) == "1m"
        assert tracker._format_time(90) == "1m 30s"
        assert tracker._format_time(125) == "2m 5s"
    
    def test_format_time_hours(self):
        """Test time formatting for hours."""
        tracker = ProgressTracker(total_files=100)
        
        assert tracker._format_time(3600) == "1h"
        assert tracker._format_time(3661) == "1h 1m 1s"
        assert tracker._format_time(7325) == "2h 2m 5s"
    
    def test_format_time_complex(self):
        """Test time formatting for complex durations."""
        tracker = ProgressTracker(total_files=100)
        
        # 2h 15m 30s = 8130 seconds
        formatted = tracker._format_time(8130)
        assert "2h" in formatted
        assert "15m" in formatted
        assert "30s" in formatted
    
    def test_zero_total_files(self):
        """Test handling of zero total files."""
        tracker = ProgressTracker(total_files=0)
        
        progress = tracker.get_progress()
        
        assert progress["percentage"] == 0.0
        assert progress["remaining_files"] == 0
    
    def test_log_interval_triggering(self, caplog):
        """Test that logging happens at intervals."""
        import logging
        caplog.set_level(logging.INFO)
        
        tracker = ProgressTracker(total_files=1000, log_interval=100)
        
        # Should not log at 50
        tracker.update(50)
        assert len([r for r in caplog.records if "Progress:" in r.message]) == 0
        
        # Should log at 100
        tracker.update(100)
        assert len([r for r in caplog.records if "Progress:" in r.message]) == 1
        
        # Should log at 200
        tracker.update(200)
        assert len([r for r in caplog.records if "Progress:" in r.message]) == 2
    
    def test_final_summary_logging(self, caplog):
        """Test final summary logging."""
        import logging
        caplog.set_level(logging.INFO)
        
        tracker = ProgressTracker(total_files=100)
        tracker.update(100)
        
        tracker.log_final_summary()
        
        # Should have logged completion message
        assert any("Scan complete" in r.message for r in caplog.records)
    
    def test_elapsed_time_tracking(self):
        """Test that elapsed time is tracked."""
        tracker = ProgressTracker(total_files=100)
        
        time.sleep(0.1)
        tracker.update(50)
        
        progress = tracker.get_progress()
        
        # Elapsed time should be at least 0.1 seconds
        assert progress["elapsed_seconds"] >= 0.1
