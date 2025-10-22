"""Run scanner and analyze results for end-to-end testing.

This script:
1. Runs the media scanner CLI with custom parameters
2. Captures log output to file
3. Analyzes the resulting database
4. Compares numbers across all file types
5. Provides complete account of processed vs unprocessed files
"""

import argparse
import json
import logging
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScannerAnalyzer:
    """Analyzes scanner results from database and logs."""
    
    def __init__(self, test_data_dir: Path, db_path: Path, log_path: Path):
        """Initialize analyzer.
        
        Args:
            test_data_dir: Directory containing test data
            db_path: Path to scanner database
            log_path: Path to scanner log file
        """
        self.test_data_dir = Path(test_data_dir)
        self.db_path = Path(db_path)
        self.log_path = Path(log_path)
        
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "test_data_dir": str(test_data_dir),
            "db_path": str(db_path),
            "log_path": str(log_path),
            "filesystem": {},
            "database": {},
            "log_analysis": {},
            "comparison": {},
            "unprocessed_files": [],
            "errors": [],
        }
    
    def analyze(self) -> Dict:
        """Run complete analysis.
        
        Returns:
            Results dictionary
        """
        logger.info("=" * 60)
        logger.info("SCANNER ANALYSIS")
        logger.info("=" * 60)
        
        logger.info("Step 1: Analyzing filesystem...")
        self._analyze_filesystem()
        
        logger.info("Step 2: Analyzing database...")
        self._analyze_database()
        
        logger.info("Step 3: Analyzing log file...")
        self._analyze_log()
        
        logger.info("Step 4: Comparing results...")
        self._compare_results()
        
        logger.info("Step 5: Identifying unprocessed files...")
        self._find_unprocessed_files()
        
        return self.results
    
    def _analyze_filesystem(self) -> None:
        """Analyze test data directory structure."""
        fs_stats = {
            "total_files": 0,
            "media_files": 0,
            "sidecar_files": 0,
            "album_metadata_files": 0,
            "other_files": 0,
            "albums": 0,
            "by_extension": defaultdict(int),
            "by_album": {},
        }
        
        # Count albums (top-level directories)
        for item in self.test_data_dir.iterdir():
            if item.is_dir():
                fs_stats["albums"] += 1
                album_files = self._count_album_files(item)
                fs_stats["by_album"][item.name] = album_files
        
        # Count all files
        for file_path in self.test_data_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            fs_stats["total_files"] += 1
            
            if file_path.name == "metadata.json":
                fs_stats["album_metadata_files"] += 1
            elif file_path.name == "archive_browser.html":
                fs_stats["other_files"] += 1
            elif ".json" in file_path.name:
                fs_stats["sidecar_files"] += 1
            else:
                fs_stats["media_files"] += 1
                ext = file_path.suffix.lower()
                fs_stats["by_extension"][ext] += 1
        
        self.results["filesystem"] = fs_stats
        
        logger.info(f"  Total files: {fs_stats['total_files']}")
        logger.info(f"  Media files: {fs_stats['media_files']}")
        logger.info(f"  Sidecar files: {fs_stats['sidecar_files']}")
        logger.info(f"  Albums: {fs_stats['albums']}")
    
    def _count_album_files(self, album_dir: Path) -> Dict:
        """Count files in an album directory."""
        counts = {
            "total": 0,
            "media": 0,
            "sidecars": 0,
        }
        
        for file_path in album_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            counts["total"] += 1
            
            if ".json" in file_path.name and file_path.name != "metadata.json":
                counts["sidecars"] += 1
            elif file_path.name not in ["metadata.json", "archive_browser.html"]:
                counts["media"] += 1
        
        return counts
    
    def _analyze_database(self) -> None:
        """Analyze scanner database."""
        if not self.db_path.exists():
            logger.error(f"  Database not found: {self.db_path}")
            self.results["errors"].append(f"Database not found: {self.db_path}")
            return
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        db_stats = {
            "scan_runs": 0,
            "albums": 0,
            "media_items": 0,
            "processing_errors": 0,
            "by_mime_type": {},
            "by_album": {},
            "by_status": {},
            "error_summary": {},
        }
        
        # Scan runs
        cursor.execute("SELECT COUNT(*) as count FROM scan_runs")
        db_stats["scan_runs"] = cursor.fetchone()["count"]
        
        # Albums
        cursor.execute("SELECT COUNT(*) as count FROM albums")
        db_stats["albums"] = cursor.fetchone()["count"]
        
        cursor.execute("SELECT album_folder_path, COUNT(*) as count FROM albums GROUP BY album_folder_path")
        for row in cursor.fetchall():
            db_stats["by_album"][row["album_folder_path"]] = row["count"]
        
        # Media items
        cursor.execute("SELECT COUNT(*) as count FROM media_items")
        db_stats["media_items"] = cursor.fetchone()["count"]
        
        cursor.execute("SELECT mime_type, COUNT(*) as count FROM media_items GROUP BY mime_type")
        for row in cursor.fetchall():
            db_stats["by_mime_type"][row["mime_type"] or "unknown"] = row["count"]
        
        # Processing errors
        cursor.execute("SELECT COUNT(*) as count FROM processing_errors")
        db_stats["processing_errors"] = cursor.fetchone()["count"]
        
        cursor.execute("SELECT error_category, COUNT(*) as count FROM processing_errors GROUP BY error_category")
        for row in cursor.fetchall():
            db_stats["error_summary"][row["error_category"]] = row["count"]
        
        conn.close()
        
        self.results["database"] = db_stats
        
        logger.info(f"  Scan runs: {db_stats['scan_runs']}")
        logger.info(f"  Albums: {db_stats['albums']}")
        logger.info(f"  Media items: {db_stats['media_items']}")
        logger.info(f"  Processing errors: {db_stats['processing_errors']}")
    
    def _analyze_log(self) -> None:
        """Analyze scanner log file."""
        if not self.log_path.exists():
            logger.warning(f"  Log file not found: {self.log_path}")
            self.results["log_analysis"] = {"error": "Log file not found"}
            return
        
        log_stats = {
            "total_lines": 0,
            "info_lines": 0,
            "warning_lines": 0,
            "error_lines": 0,
            "debug_lines": 0,
            "key_events": [],
        }
        
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                log_stats["total_lines"] += 1
                
                line_lower = line.lower()
                
                if " info " in line_lower or " - info - " in line_lower:
                    log_stats["info_lines"] += 1
                elif " warning " in line_lower or " - warning - " in line_lower:
                    log_stats["warning_lines"] += 1
                elif " error " in line_lower or " - error - " in line_lower:
                    log_stats["error_lines"] += 1
                elif " debug " in line_lower or " - debug - " in line_lower:
                    log_stats["debug_lines"] += 1
                
                # Extract key events
                if "scanning complete" in line_lower:
                    log_stats["key_events"].append({"event": "scan_complete", "line": line.strip()})
                elif "albums discovered" in line_lower:
                    log_stats["key_events"].append({"event": "albums_discovered", "line": line.strip()})
                elif "files discovered" in line_lower:
                    log_stats["key_events"].append({"event": "files_discovered", "line": line.strip()})
        
        self.results["log_analysis"] = log_stats
        
        logger.info(f"  Total log lines: {log_stats['total_lines']}")
        logger.info(f"  Errors: {log_stats['error_lines']}")
        logger.info(f"  Warnings: {log_stats['warning_lines']}")
    
    def _compare_results(self) -> None:
        """Compare filesystem vs database results."""
        fs = self.results["filesystem"]
        db = self.results["database"]
        
        comparison = {
            "media_files": {
                "filesystem": fs.get("media_files", 0),
                "database": db.get("media_items", 0),
                "difference": fs.get("media_files", 0) - db.get("media_items", 0),
                "match": fs.get("media_files", 0) == db.get("media_items", 0),
            },
            "albums": {
                "filesystem": fs.get("albums", 0),
                "database": db.get("albums", 0),
                "difference": fs.get("albums", 0) - db.get("albums", 0),
                "match": fs.get("albums", 0) == db.get("albums", 0),
            },
        }
        
        self.results["comparison"] = comparison
        
        logger.info("  Comparison:")
        logger.info(f"    Media files: FS={comparison['media_files']['filesystem']}, "
                   f"DB={comparison['media_files']['database']}, "
                   f"Diff={comparison['media_files']['difference']}, "
                   f"Match={comparison['media_files']['match']}")
        logger.info(f"    Albums: FS={comparison['albums']['filesystem']}, "
                   f"DB={comparison['albums']['database']}, "
                   f"Diff={comparison['albums']['difference']}, "
                   f"Match={comparison['albums']['match']}")
    
    def _find_unprocessed_files(self) -> None:
        """Identify files that exist in filesystem but not in database."""
        if not self.db_path.exists():
            logger.error("  Cannot identify unprocessed files - database not found")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all processed file paths from database
        cursor.execute("SELECT relative_path FROM media_items")
        processed_paths = {row[0] for row in cursor.fetchall()}
        
        conn.close()
        
        # Find unprocessed files
        unprocessed = []
        
        for file_path in self.test_data_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Skip non-media files
            if file_path.name in ["metadata.json", "archive_browser.html"]:
                continue
            if ".json" in file_path.name:
                continue
            
            # Calculate relative path
            try:
                rel_path = file_path.relative_to(self.test_data_dir)
                rel_path_str = str(rel_path).replace("\\", "/")
                
                if rel_path_str not in processed_paths:
                    unprocessed.append({
                        "path": rel_path_str,
                        "size": file_path.stat().st_size,
                        "extension": file_path.suffix,
                    })
            except ValueError:
                pass
        
        self.results["unprocessed_files"] = unprocessed
        
        logger.info(f"  Unprocessed files: {len(unprocessed)}")
        
        if unprocessed and len(unprocessed) <= 20:
            logger.info("  Sample unprocessed files:")
            for item in unprocessed[:10]:
                logger.info(f"    - {item['path']}")
    
    def print_summary(self) -> None:
        """Print detailed summary."""
        logger.info("")
        logger.info("=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        
        fs = self.results["filesystem"]
        db = self.results["database"]
        comp = self.results["comparison"]
        
        logger.info("")
        logger.info("Filesystem:")
        logger.info(f"  Total files: {fs['total_files']}")
        logger.info(f"  Media files: {fs['media_files']}")
        logger.info(f"  Sidecar files: {fs['sidecar_files']}")
        logger.info(f"  Albums: {fs['albums']}")
        
        logger.info("")
        logger.info("Database:")
        logger.info(f"  Scan runs: {db.get('scan_runs', 0)}")
        logger.info(f"  Albums: {db.get('albums', 0)}")
        logger.info(f"  Media items: {db.get('media_items', 0)}")
        logger.info(f"  Processing errors: {db.get('processing_errors', 0)}")
        
        if db.get("by_mime_type"):
            logger.info("")
            logger.info("By MIME type:")
            for mime, count in sorted(db["by_mime_type"].items()):
                logger.info(f"  {mime}: {count}")
        
        if db.get("error_summary"):
            logger.info("")
            logger.info("Error summary:")
            for category, count in sorted(db["error_summary"].items()):
                logger.info(f"  {category}: {count}")
        
        logger.info("")
        logger.info("Comparison:")
        logger.info(f"  Media files match: {comp['media_files']['match']}")
        logger.info(f"  Albums match: {comp['albums']['match']}")
        
        if self.results["unprocessed_files"]:
            logger.info("")
            logger.info(f"Unprocessed files: {len(self.results['unprocessed_files'])}")
    
    def save_results(self, output_path: Path) -> None:
        """Save results to JSON file."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to: {output_path}")


def run_scanner(
    test_data_dir: Path,
    db_path: Path,
    log_path: Path,
    worker_threads: int = 4,
    use_exiftool: bool = False,
    use_ffprobe: bool = False,
) -> int:
    """Run the media scanner.
    
    Args:
        test_data_dir: Directory containing test data
        db_path: Path for output database
        log_path: Path for output log
        worker_threads: Number of worker threads
        use_exiftool: Enable exiftool
        use_ffprobe: Enable ffprobe
        
    Returns:
        Exit code
    """
    logger.info("=" * 60)
    logger.info("RUNNING SCANNER")
    logger.info("=" * 60)
    logger.info(f"Test data: {test_data_dir}")
    logger.info(f"Database: {db_path}")
    logger.info(f"Log file: {log_path}")
    logger.info(f"Worker threads: {worker_threads}")
    logger.info(f"Use exiftool: {use_exiftool}")
    logger.info(f"Use ffprobe: {use_ffprobe}")
    logger.info("")
    
    # Build command
    cmd = [
        sys.executable,
        "-m",
        "gphotos_321sync.media_scanner",
        "scan",
        "--target-media-path", str(test_data_dir),
        "--database-path", str(db_path),
        "--worker-threads", str(worker_threads),
    ]
    
    if use_exiftool:
        cmd.append("--use-exiftool")
    if use_ffprobe:
        cmd.append("--use-ffprobe")
    
    logger.info(f"Command: {' '.join(cmd)}")
    logger.info("")
    
    # Run scanner
    try:
        with open(log_path, "w", encoding="utf-8") as log_file:
            result = subprocess.run(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
        
        logger.info(f"Scanner exit code: {result.returncode}")
        return result.returncode
    
    except Exception as e:
        logger.error(f"Failed to run scanner: {e}")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run scanner and analyze results")
    parser.add_argument("--test-data-dir", type=Path, required=True, help="Test data directory")
    parser.add_argument("--db-path", type=Path, help="Database path (default: test_data_dir/media.db)")
    parser.add_argument("--log-path", type=Path, help="Log path (default: test_data_dir/scan.log)")
    parser.add_argument("--results-path", type=Path, help="Results JSON path (default: test_data_dir/analysis.json)")
    parser.add_argument("--worker-threads", type=int, default=4, help="Number of worker threads")
    parser.add_argument("--use-exiftool", action="store_true", help="Enable exiftool")
    parser.add_argument("--use-ffprobe", action="store_true", help="Enable ffprobe")
    parser.add_argument("--skip-scan", action="store_true", help="Skip scanner run, only analyze existing results")
    
    args = parser.parse_args()
    
    # Set default paths
    db_path = args.db_path or (args.test_data_dir / "media.db")
    log_path = args.log_path or (args.test_data_dir / "scan.log")
    results_path = args.results_path or (args.test_data_dir / "analysis.json")
    
    # Run scanner
    if not args.skip_scan:
        exit_code = run_scanner(
            args.test_data_dir,
            db_path,
            log_path,
            args.worker_threads,
            args.use_exiftool,
            args.use_ffprobe,
        )
        
        if exit_code != 0:
            logger.error(f"Scanner failed with exit code {exit_code}")
            return exit_code
    
    # Analyze results
    analyzer = ScannerAnalyzer(args.test_data_dir, db_path, log_path)
    analyzer.analyze()
    analyzer.print_summary()
    analyzer.save_results(results_path)
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("COMPLETE")
    logger.info("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
