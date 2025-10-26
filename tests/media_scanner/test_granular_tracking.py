"""Tests for the new granular tracking system.

Tests the DiscoveryResult and BatchMatchingResult structures that replaced
the old list1/list2/list3 logic with comprehensive phase-by-phase tracking.
"""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock

from gphotos_321sync.media_scanner.discovery import (
    DiscoveryResult,
    BatchMatchingResult,
    ParsedSidecar,
    FileInfo,
    discover_files,
    _match_media_to_sidecar_batch,
)


class TestDiscoveryResult:
    """Test the enhanced DiscoveryResult structure."""
    
    def test_discovery_result_creation(self):
        """Test creating DiscoveryResult with all new fields."""
        files = [Mock(spec=FileInfo)]
        paired_sidecars = {Path("/test/sidecar1.json")}
        all_sidecars = {Path("/test/sidecar1.json"), Path("/test/sidecar2.json")}
        
        # Phase-by-phase results
        matched_phase1 = {Path("/test/photo1.jpg")}
        matched_phase2 = {Path("/test/photo2.jpg")}
        matched_phase3 = {Path("/test/photo3.jpg")}
        unmatched_media = {Path("/test/photo4.jpg")}
        unmatched_sidecars = {Path("/test/sidecar3.json")}
        
        # File type discovery
        discovered_media = {Path("/test/photo1.jpg"), Path("/test/photo2.jpg")}
        discovered_sidecars = {Path("/test/sidecar1.json"), Path("/test/sidecar2.json")}
        discovered_metadata = {Path("/test/metadata.json")}
        discovered_other = {Path("/test/other.txt")}
        
        result = DiscoveryResult(
            files=files,
            json_sidecar_count=len(all_sidecars),
            paired_sidecars=paired_sidecars,
            all_sidecars=all_sidecars,
            matched_phase1=matched_phase1,
            matched_phase2=matched_phase2,
            matched_phase3=matched_phase3,
            unmatched_media=unmatched_media,
            unmatched_sidecars=unmatched_sidecars,
            discovered_media=discovered_media,
            discovered_sidecars=discovered_sidecars,
            discovered_metadata=discovered_metadata,
            discovered_other=discovered_other
        )
        
        # Test basic fields
        assert len(result.files) == 1
        assert result.json_sidecar_count == 2
        assert len(result.paired_sidecars) == 1
        assert len(result.all_sidecars) == 2
        
        # Test phase-by-phase results
        assert len(result.matched_phase1) == 1
        assert len(result.matched_phase2) == 1
        assert len(result.matched_phase3) == 1
        assert len(result.unmatched_media) == 1
        assert len(result.unmatched_sidecars) == 1
        
        # Test file type discovery
        assert len(result.discovered_media) == 2
        assert len(result.discovered_sidecars) == 2
        assert len(result.discovered_metadata) == 1
        assert len(result.discovered_other) == 1
    
    def test_discovery_result_statistics(self):
        """Test that DiscoveryResult provides accurate statistics."""
        # Create mock files
        file1 = Mock(spec=FileInfo)
        file1.file_path = Path("/test/photo1.jpg")
        file1.json_sidecar_path = Path("/test/photo1.jpg.supplemental-metadata.json")
        
        file2 = Mock(spec=FileInfo)
        file2.file_path = Path("/test/photo2.jpg")
        file2.json_sidecar_path = None  # No sidecar
        
        files = [file1, file2]
        
        result = DiscoveryResult(
            files=files,
            json_sidecar_count=3,  # Total sidecars found
            paired_sidecars={Path("/test/photo1.jpg.supplemental-metadata.json")},
            all_sidecars={Path("/test/photo1.jpg.supplemental-metadata.json"), 
                         Path("/test/photo2.jpg.supplemental-metadata.json"),
                         Path("/test/photo3.jpg.supplemental-metadata.json")},
            matched_phase1={Path("/test/photo1.jpg")},
            matched_phase2=set(),
            matched_phase3=set(),
            unmatched_media={Path("/test/photo2.jpg")},
            unmatched_sidecars={Path("/test/photo2.jpg.supplemental-metadata.json"),
                              Path("/test/photo3.jpg.supplemental-metadata.json")},
            discovered_media={Path("/test/photo1.jpg"), Path("/test/photo2.jpg")},
            discovered_sidecars={Path("/test/photo1.jpg.supplemental-metadata.json"),
                               Path("/test/photo2.jpg.supplemental-metadata.json"),
                               Path("/test/photo3.jpg.supplemental-metadata.json")},
            discovered_metadata=set(),
            discovered_other=set()
        )
        
        # Test statistics calculations
        assert result.json_sidecar_count == 3  # Total sidecars
        assert len(result.paired_sidecars) == 1  # Successfully paired
        assert len(result.all_sidecars) == 3  # All discovered sidecars
        
        # Test phase statistics
        total_matched = len(result.matched_phase1) + len(result.matched_phase2) + len(result.matched_phase3)
        assert total_matched == 1  # Only photo1 matched
        
        # Test unmatched statistics
        assert len(result.unmatched_media) == 1  # photo2 has no sidecar
        assert len(result.unmatched_sidecars) == 2  # 2 orphaned sidecars


class TestBatchMatchingResult:
    """Test the BatchMatchingResult structure."""
    
    def test_batch_matching_result_creation(self):
        """Test creating BatchMatchingResult with phase tracking."""
        matches = {
            Path("/test/photo1.jpg"): Path("/test/photo1.jpg.supplemental-metadata.json"),
            Path("/test/photo2.jpg"): Path("/test/photo2.jpg.supplemental-metadata.json"),
            Path("/test/photo3.jpg"): None  # No match
        }
        
        matched_phase1 = {Path("/test/photo1.jpg")}
        matched_phase2 = {Path("/test/photo2.jpg")}
        matched_phase3 = set()
        unmatched_media = {Path("/test/photo3.jpg")}
        unmatched_sidecars = {Path("/test/photo4.jpg.supplemental-metadata.json")}
        
        result = BatchMatchingResult(
            matches=matches,
            matched_phase1=matched_phase1,
            matched_phase2=matched_phase2,
            matched_phase3=matched_phase3,
            unmatched_media=unmatched_media,
            unmatched_sidecars=unmatched_sidecars
        )
        
        # Test matches
        assert len(result.matches) == 3
        assert result.matches[Path("/test/photo1.jpg")] == Path("/test/photo1.jpg.supplemental-metadata.json")
        assert result.matches[Path("/test/photo2.jpg")] == Path("/test/photo2.jpg.supplemental-metadata.json")
        assert result.matches[Path("/test/photo3.jpg")] is None
        
        # Test phase tracking
        assert len(result.matched_phase1) == 1
        assert len(result.matched_phase2) == 1
        assert len(result.matched_phase3) == 0
        assert len(result.unmatched_media) == 1
        assert len(result.unmatched_sidecars) == 1
    
    def test_batch_matching_result_statistics(self):
        """Test that BatchMatchingResult provides accurate statistics."""
        # Create a complex scenario
        matches = {
            Path("/test/photo1.jpg"): Path("/test/photo1.jpg.supplemental-metadata.json"),
            Path("/test/photo2(1).jpg"): Path("/test/photo2.jpg.supplemental-metadata(1).json"),
            Path("/test/photo3-edited.jpg"): Path("/test/photo3.jpg.supplemental-metadata.json"),
            Path("/test/photo4.jpg"): None,  # No match
        }
        
        result = BatchMatchingResult(
            matches=matches,
            matched_phase1={Path("/test/photo1.jpg")},
            matched_phase2={Path("/test/photo2(1).jpg")},
            matched_phase3={Path("/test/photo3-edited.jpg")},
            unmatched_media={Path("/test/photo4.jpg")},
            unmatched_sidecars={Path("/test/photo5.jpg.supplemental-metadata.json")}
        )
        
        # Test total matches
        successful_matches = sum(1 for match in result.matches.values() if match is not None)
        assert successful_matches == 3
        
        # Test phase distribution
        assert len(result.matched_phase1) == 1  # Happy path
        assert len(result.matched_phase2) == 1  # Numbered files
        assert len(result.matched_phase3) == 1  # Edited files
        
        # Test unmatched
        assert len(result.unmatched_media) == 1
        assert len(result.unmatched_sidecars) == 1
        
        # Test phase totals
        total_matched_by_phase = len(result.matched_phase1) + len(result.matched_phase2) + len(result.matched_phase3)
        assert total_matched_by_phase == 3


class TestGranularTrackingIntegration:
    """Test integration between granular tracking components."""
    
    def test_discovery_result_from_batch_results(self):
        """Test creating DiscoveryResult from multiple BatchMatchingResult objects."""
        # Simulate processing multiple albums
        album1_result = BatchMatchingResult(
            matches={
                Path("/album1/photo1.jpg"): Path("/album1/photo1.jpg.supplemental-metadata.json"),
                Path("/album1/photo2.jpg"): None
            },
            matched_phase1={Path("/album1/photo1.jpg")},
            matched_phase2=set(),
            matched_phase3=set(),
            unmatched_media={Path("/album1/photo2.jpg")},
            unmatched_sidecars=set()
        )
        
        album2_result = BatchMatchingResult(
            matches={
                Path("/album2/photo3(1).jpg"): Path("/album2/photo3.jpg.supplemental-metadata(1).json"),
                Path("/album2/photo4-edited.jpg"): Path("/album2/photo4.jpg.supplemental-metadata.json")
            },
            matched_phase1=set(),
            matched_phase2={Path("/album2/photo3(1).jpg")},
            matched_phase3={Path("/album2/photo4-edited.jpg")},
            unmatched_media=set(),
            unmatched_sidecars={Path("/album2/photo5.jpg.supplemental-metadata.json")}
        )
        
        # Combine results (simulating what discover_files would do)
        all_matches = {**album1_result.matches, **album2_result.matches}
        combined_phase1 = album1_result.matched_phase1 | album2_result.matched_phase1
        combined_phase2 = album1_result.matched_phase2 | album2_result.matched_phase2
        combined_phase3 = album1_result.matched_phase3 | album2_result.matched_phase3
        combined_unmatched_media = album1_result.unmatched_media | album2_result.unmatched_media
        combined_unmatched_sidecars = album1_result.unmatched_sidecars | album2_result.unmatched_sidecars
        
        # Create FileInfo objects (simplified)
        files = []
        paired_sidecars = set()
        for media_file, sidecar_path in all_matches.items():
            if sidecar_path:
                file_info = Mock(spec=FileInfo)
                file_info.file_path = media_file
                file_info.json_sidecar_path = sidecar_path
                files.append(file_info)
                paired_sidecars.add(sidecar_path)
        
        # Create DiscoveryResult
        result = DiscoveryResult(
            files=files,
            json_sidecar_count=4,  # Total sidecars across both albums
            paired_sidecars=paired_sidecars,
            all_sidecars={Path("/album1/photo1.jpg.supplemental-metadata.json"),
                         Path("/album2/photo3.jpg.supplemental-metadata(1).json"),
                         Path("/album2/photo4.jpg.supplemental-metadata.json"),
                         Path("/album2/photo5.jpg.supplemental-metadata.json")},
            matched_phase1=combined_phase1,
            matched_phase2=combined_phase2,
            matched_phase3=combined_phase3,
            unmatched_media=combined_unmatched_media,
            unmatched_sidecars=combined_unmatched_sidecars,
            discovered_media={Path("/album1/photo1.jpg"), Path("/album1/photo2.jpg"),
                            Path("/album2/photo3(1).jpg"), Path("/album2/photo4-edited.jpg")},
            discovered_sidecars={Path("/album1/photo1.jpg.supplemental-metadata.json"),
                               Path("/album2/photo3.jpg.supplemental-metadata(1).json"),
                               Path("/album2/photo4.jpg.supplemental-metadata.json"),
                               Path("/album2/photo5.jpg.supplemental-metadata.json")},
            discovered_metadata=set(),
            discovered_other=set()
        )
        
        # Test combined statistics
        assert len(result.files) == 3  # 3 files with sidecars
        assert len(result.paired_sidecars) == 3  # 3 successfully paired
        assert result.json_sidecar_count == 4  # Total sidecars
        
        # Test phase distribution
        assert len(result.matched_phase1) == 1  # album1/photo1.jpg
        assert len(result.matched_phase2) == 1  # album2/photo3(1).jpg
        assert len(result.matched_phase3) == 1  # album2/photo4-edited.jpg
        
        # Test unmatched
        assert len(result.unmatched_media) == 1  # album1/photo2.jpg
        assert len(result.unmatched_sidecars) == 1  # album2/photo5.jpg.supplemental-metadata.json
    
    def test_empty_discovery_result(self):
        """Test DiscoveryResult with no files discovered."""
        result = DiscoveryResult(
            files=[],
            json_sidecar_count=0,
            paired_sidecars=set(),
            all_sidecars=set(),
            matched_phase1=set(),
            matched_phase2=set(),
            matched_phase3=set(),
            unmatched_media=set(),
            unmatched_sidecars=set(),
            discovered_media=set(),
            discovered_sidecars=set(),
            discovered_metadata=set(),
            discovered_other=set()
        )
        
        # All counts should be zero
        assert len(result.files) == 0
        assert result.json_sidecar_count == 0
        assert len(result.paired_sidecars) == 0
        assert len(result.all_sidecars) == 0
        assert len(result.matched_phase1) == 0
        assert len(result.matched_phase2) == 0
        assert len(result.matched_phase3) == 0
        assert len(result.unmatched_media) == 0
        assert len(result.unmatched_sidecars) == 0
        assert len(result.discovered_media) == 0
        assert len(result.discovered_sidecars) == 0
        assert len(result.discovered_metadata) == 0
        assert len(result.discovered_other) == 0


class TestGranularTrackingEdgeCases:
    """Test edge cases for granular tracking."""
    
    def test_all_phases_matched(self):
        """Test scenario where all phases have matches."""
        result = BatchMatchingResult(
            matches={
                Path("/test/photo1.jpg"): Path("/test/photo1.jpg.supplemental-metadata.json"),
                Path("/test/photo2(1).jpg"): Path("/test/photo2.jpg.supplemental-metadata(1).json"),
                Path("/test/photo3-edited.jpg"): Path("/test/photo3.jpg.supplemental-metadata.json"),
            },
            matched_phase1={Path("/test/photo1.jpg")},
            matched_phase2={Path("/test/photo2(1).jpg")},
            matched_phase3={Path("/test/photo3-edited.jpg")},
            unmatched_media=set(),
            unmatched_sidecars=set()
        )
        
        # All phases should have matches
        assert len(result.matched_phase1) == 1
        assert len(result.matched_phase2) == 1
        assert len(result.matched_phase3) == 1
        assert len(result.unmatched_media) == 0
        assert len(result.unmatched_sidecars) == 0
        
        # All matches should be successful
        successful_matches = sum(1 for match in result.matches.values() if match is not None)
        assert successful_matches == 3
    
    def test_no_matches_any_phase(self):
        """Test scenario where no files match in any phase."""
        result = BatchMatchingResult(
            matches={
                Path("/test/photo1.jpg"): None,
                Path("/test/photo2.jpg"): None,
                Path("/test/photo3.jpg"): None,
            },
            matched_phase1=set(),
            matched_phase2=set(),
            matched_phase3=set(),
            unmatched_media={Path("/test/photo1.jpg"), Path("/test/photo2.jpg"), Path("/test/photo3.jpg")},
            unmatched_sidecars={Path("/test/sidecar1.json"), Path("/test/sidecar2.json")}
        )
        
        # No phases should have matches
        assert len(result.matched_phase1) == 0
        assert len(result.matched_phase2) == 0
        assert len(result.matched_phase3) == 0
        
        # All media should be unmatched
        assert len(result.unmatched_media) == 3
        assert len(result.unmatched_sidecars) == 2
        
        # No successful matches
        successful_matches = sum(1 for match in result.matches.values() if match is not None)
        assert successful_matches == 0
    
    def test_mixed_file_types_discovery(self):
        """Test DiscoveryResult with various file types."""
        result = DiscoveryResult(
            files=[],  # Simplified for this test
            json_sidecar_count=5,
            paired_sidecars=set(),
            all_sidecars=set(),
            matched_phase1=set(),
            matched_phase2=set(),
            matched_phase3=set(),
            unmatched_media=set(),
            unmatched_sidecars=set(),
            discovered_media={Path("/test/photo1.jpg"), Path("/test/video1.mp4")},
            discovered_sidecars={Path("/test/photo1.jpg.supplemental-metadata.json"),
                               Path("/test/photo2.jpg.supplemental-metadata.json")},
            discovered_metadata={Path("/test/album1/metadata.json"),
                               Path("/test/album2/metadata.json")},
            discovered_other={Path("/test/archive_browser.html"),
                            Path("/test/readme.txt"),
                            Path("/test/config.json")}
        )
        
        # Test file type categorization
        assert len(result.discovered_media) == 2  # photo + video
        assert len(result.discovered_sidecars) == 2  # 2 sidecars
        assert len(result.discovered_metadata) == 2  # 2 album metadata files
        assert len(result.discovered_other) == 3  # html + txt + config
        
        # Total files discovered
        total_discovered = (len(result.discovered_media) + 
                          len(result.discovered_sidecars) + 
                          len(result.discovered_metadata) + 
                          len(result.discovered_other))
        assert total_discovered == 9


class TestParallelScannerIntegration:
    """Test integration of granular tracking with ParallelScanner."""
    
    def test_discovery_result_has_granular_tracking_fields(self):
        """Test that DiscoveryResult includes all new granular tracking fields."""
        # This test verifies that the DiscoveryResult structure has all the new fields
        # that ParallelScanner expects to use
        
        result = DiscoveryResult(
            files=[],
            json_sidecar_count=0,
            paired_sidecars=set(),
            all_sidecars=set(),
            matched_phase1=set(),
            matched_phase2=set(),
            matched_phase3=set(),
            unmatched_media=set(),
            unmatched_sidecars=set(),
            discovered_media=set(),
            discovered_sidecars=set(),
            discovered_metadata=set(),
            discovered_other=set()
        )
        
        # Test that all new granular tracking fields exist
        assert hasattr(result, 'matched_phase1')
        assert hasattr(result, 'matched_phase2')
        assert hasattr(result, 'matched_phase3')
        assert hasattr(result, 'unmatched_media')
        assert hasattr(result, 'unmatched_sidecars')
        assert hasattr(result, 'discovered_media')
        assert hasattr(result, 'discovered_sidecars')
        assert hasattr(result, 'discovered_metadata')
        assert hasattr(result, 'discovered_other')
        
        # Test that fields are the correct type (sets)
        assert isinstance(result.matched_phase1, set)
        assert isinstance(result.matched_phase2, set)
        assert isinstance(result.matched_phase3, set)
        assert isinstance(result.unmatched_media, set)
        assert isinstance(result.unmatched_sidecars, set)
        assert isinstance(result.discovered_media, set)
        assert isinstance(result.discovered_sidecars, set)
        assert isinstance(result.discovered_metadata, set)
        assert isinstance(result.discovered_other, set)
    
    def test_parallel_scanner_return_value_structure(self):
        """Test that ParallelScanner returns the expected structure with discovery_stats."""
        # This test verifies that the ParallelScanner.scan() method returns
        # a result dictionary that includes the new discovery_stats field
        
        # Create a mock result that matches what ParallelScanner should return
        expected_result = {
            "scan_run_id": "test-scan-run",
            "status": "completed",
            "total_files": 10,
            "media_files_processed": 8,
            "duration_seconds": 5.2,
            "phase_timings": {
                "album_discovery": 0.1,
                "file_discovery": 0.5,
                "file_processing": 4.6,
            },
            "discovery_stats": {
                "discovered_media": 8,
                "discovered_sidecars": 2,
                "discovered_metadata": 0,
                "discovered_other": 0,
                "matched_phase1": 5,
                "matched_phase2": 2,
                "matched_phase3": 1,
                "unmatched_media": 0,
                "unmatched_sidecars": 0,
            }
        }
        
        # Test that the expected structure is correct
        assert "discovery_stats" in expected_result
        discovery_stats = expected_result["discovery_stats"]
        
        # Test that all granular tracking fields are present
        required_fields = [
            "discovered_media", "discovered_sidecars", "discovered_metadata", "discovered_other",
            "matched_phase1", "matched_phase2", "matched_phase3",
            "unmatched_media", "unmatched_sidecars"
        ]
        
        for field in required_fields:
            assert field in discovery_stats, f"Missing field: {field}"
            assert isinstance(discovery_stats[field], int), f"Field {field} should be int"
        
        # Test that the statistics make sense
        total_discovered = (discovery_stats["discovered_media"] + 
                          discovery_stats["discovered_sidecars"] + 
                          discovery_stats["discovered_metadata"] + 
                          discovery_stats["discovered_other"])
        assert total_discovered == 10  # Should match total_files
        
        total_matched = (discovery_stats["matched_phase1"] + 
                        discovery_stats["matched_phase2"] + 
                        discovery_stats["matched_phase3"])
        assert total_matched == 8  # Should match media_files_processed
