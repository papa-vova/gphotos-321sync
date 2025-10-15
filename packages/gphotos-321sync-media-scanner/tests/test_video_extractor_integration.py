"""Integration tests for video metadata extraction with ffprobe."""

import pytest
import tempfile
import subprocess
from pathlib import Path

from gphotos_321sync.media_scanner.tool_checker import check_tool_availability
from gphotos_321sync.media_scanner.metadata.video_extractor import (
    extract_video_metadata,
    is_video_file
)


# Check if ffprobe is available
tools = check_tool_availability()
ffprobe_available = tools.get('ffprobe', False)


@pytest.mark.skipif(not ffprobe_available, reason="ffprobe not available")
class TestVideoExtractorWithFfprobe:
    """Integration tests for video metadata extraction using real ffprobe."""
    
    @pytest.fixture
    def test_video(self):
        """Create a test video file using ffmpeg."""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # Create a simple 2-second test video (640x480, 30fps)
            subprocess.run(
                [
                    'ffmpeg',
                    '-f', 'lavfi',
                    '-i', 'color=c=blue:s=640x480:d=2',
                    '-r', '30',
                    '-pix_fmt', 'yuv420p',
                    '-y',
                    str(temp_path)
                ],
                capture_output=True,
                check=True,
                timeout=10
            )
            yield temp_path
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_extract_video_metadata_real_file(self, test_video):
        """Test extracting metadata from a real video file."""
        metadata = extract_video_metadata(test_video)
        
        # Check that we got metadata
        assert 'width' in metadata
        assert 'height' in metadata
        assert 'duration_seconds' in metadata
        assert 'frame_rate' in metadata
        
        # Verify values
        assert metadata['width'] == 640
        assert metadata['height'] == 480
        assert metadata['duration_seconds'] > 0
        assert metadata['frame_rate'] > 0
    
    def test_extract_video_resolution(self, test_video):
        """Test that resolution is extracted correctly."""
        metadata = extract_video_metadata(test_video)
        
        assert metadata['width'] == 640
        assert metadata['height'] == 480
    
    def test_extract_video_duration(self, test_video):
        """Test that duration is extracted correctly."""
        metadata = extract_video_metadata(test_video)
        
        # Should be approximately 2 seconds
        assert 1.5 < metadata['duration_seconds'] < 2.5
    
    def test_extract_video_frame_rate(self, test_video):
        """Test that frame rate is extracted correctly."""
        metadata = extract_video_metadata(test_video)
        
        # Should be approximately 30 fps
        assert 29 < metadata['frame_rate'] < 31
    
    def test_extract_from_missing_file(self):
        """Test handling of missing video file."""
        with pytest.raises(subprocess.CalledProcessError):
            extract_video_metadata(Path("/nonexistent/video.mp4"))
    
    def test_is_video_file_mime_types(self):
        """Test video MIME type detection."""
        assert is_video_file('video/mp4') is True
        assert is_video_file('video/quicktime') is True
        assert is_video_file('video/x-msvideo') is True
        assert is_video_file('image/jpeg') is False
        assert is_video_file('application/pdf') is False


@pytest.mark.skipif(ffprobe_available, reason="Testing behavior when ffprobe is not available")
class TestVideoExtractorWithoutFfprobe:
    """Tests for video extractor when ffprobe is not available."""
    
    def test_extract_raises_error_when_ffprobe_not_available(self):
        """Test that extraction raises FileNotFoundError when ffprobe tool is not installed."""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # Write some dummy data
            temp_path.write_bytes(b"fake video data")
            
            with pytest.raises(FileNotFoundError):
                extract_video_metadata(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)
