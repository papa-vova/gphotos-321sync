"""CLI command for media scanning."""

import logging
import argparse
import sys
from pathlib import Path
from typing import Optional

from .parallel_scanner import ParallelScanner
from .config import MediaScannerConfig
from .database import DatabaseConnection
from .migrations import MigrationRunner
from gphotos_321sync.common import setup_logging, ConfigLoader

# Application name derived from package name
_package = __package__ or "gphotos_321sync.media_scanner"
APP_NAME = _package.replace('_', '-').replace('.', '-')


def progress_callback(logger: logging.Logger, current: int, total: int, item: str) -> None:
    """Log scanning progress.
    
    Args:
        logger: Logger instance
        current: Current item number (1-based)
        total: Total number of items
        item: Name of current item
    """
    if current > total:
        logger.info(f"Scanning complete: {{'items': {total}}}")
    else:
        percent = (current / total) * 100 if total > 0 else 0
        logger.info(f"Scanning: {{'current': {current}, 'total': {total}, 'percent': {percent:.1f}, 'item': {item!r}}}")


def scan_command(
    config: 'MediaScannerConfig',
    target_media_path_override: Optional[Path] = None,
    database_path_override: Optional[Path] = None,
    worker_processes_override: Optional[int] = None,
    worker_threads_override: Optional[int] = None,
    use_exiftool_override: Optional[bool] = None,
    use_ffprobe_override: Optional[bool] = None
) -> int:
    """Scan media directory and catalog files.
    
    IMPORTANT: Automatically detects Google Takeout structure.
    If "Takeout/Google Photos/" subfolder exists, albums are scanned from there.
    
    Args:
        config: Configuration object
        target_media_path_override: Optional override for target media directory
        database_path_override: Optional override for database path
        worker_processes_override: Optional override for worker processes
        worker_threads_override: Optional override for worker threads
        use_exiftool_override: Optional override for exiftool usage
        use_ffprobe_override: Optional override for ffprobe usage
    
    Returns:
        Exit code (0 for success)
    """
    # Logging already set up in main(), just get logger
    # Use __package__ to avoid __main__ when run as module
    logger_name = __package__ or __name__
    logger = logging.getLogger(logger_name)
    
    # Apply overrides
    target_media_path = target_media_path_override if target_media_path_override else Path(config.scanner.target_media_path)
    
    # Determine database path
    if database_path_override:
        database_path = database_path_override
    elif config.scanner.database_path:
        database_path = Path(config.scanner.database_path)
    else:
        # Default: media.db in target media directory
        database_path = target_media_path / "media.db"
    
    worker_processes = worker_processes_override if worker_processes_override is not None else config.scanner.worker_processes
    worker_threads = worker_threads_override if worker_threads_override is not None else config.scanner.worker_threads
    batch_size = config.scanner.batch_size
    queue_maxsize = config.scanner.queue_maxsize
    use_exiftool = use_exiftool_override if use_exiftool_override is not None else config.scanner.use_exiftool
    use_ffprobe = use_ffprobe_override if use_ffprobe_override is not None else config.scanner.use_ffprobe
    
    try:
        logger.info(f"Configuration: {{'target_media_path': {str(target_media_path)!r}, 'database_path': {str(database_path)!r}, 'worker_processes': {worker_processes}, 'worker_threads': {worker_threads}, 'use_exiftool': {use_exiftool}, 'use_ffprobe': {use_ffprobe}}}")
        
        # Validate target media path exists
        if not target_media_path.exists():
            logger.error(f"Target media directory does not exist: {{'path': {str(target_media_path)!r}}}")
            return 1
        
        # Initialize database schema if needed
        logger.info("Checking database schema...")
        db_conn = DatabaseConnection(database_path)
        db_conn.connect()
        
        # Get schema directory (relative to this module)
        schema_dir = Path(__file__).parent / "schema"
        migration_runner = MigrationRunner(db_conn, schema_dir)
        
        # Apply any pending migrations
        migration_runner.apply_migrations()
        db_conn.close()
        
        logger.info("Database schema is up to date")
        
        # Create scanner and run
        scanner = ParallelScanner(
            db_path=database_path,
            worker_processes=worker_processes,
            worker_threads=worker_threads,
            batch_size=batch_size,
            queue_maxsize=queue_maxsize,
            use_exiftool=use_exiftool,
            use_ffprobe=use_ffprobe
        )
        
        results = scanner.scan(target_media_path)
        
        # Log results
        logger.info(f"Scan complete: {results}")
        
        return 0
        
    except Exception as e:
        logger.exception(f"Scan failed: {e}")
        return 1


def main() -> int:
    """Main entry point for scan command."""
    parser = argparse.ArgumentParser(
        description="Scan and catalog media files from Google Takeout"
    )
    parser.add_argument(
        "--target-media-path",
        type=Path,
        required=False,
        help="Directory containing extracted media files to scan (overrides config)"
    )
    parser.add_argument(
        "--database-path",
        type=Path,
        required=False,
        help="Path to SQLite database file (overrides config, default: target_media_path/media.db)"
    )
    parser.add_argument(
        "--worker-processes",
        type=int,
        required=False,
        help="Number of CPU worker processes (overrides config)"
    )
    parser.add_argument(
        "--worker-threads",
        type=int,
        required=False,
        help="Number of I/O worker threads (overrides config)"
    )
    parser.add_argument(
        "--use-exiftool",
        action="store_true",
        help="Use exiftool for RAW format EXIF extraction (requires exiftool installed)"
    )
    parser.add_argument(
        "--use-ffprobe",
        action="store_true",
        help="Use ffprobe for video metadata extraction (requires ffmpeg/ffprobe installed)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config file (defaults.toml)"
    )
    
    args = parser.parse_args()
    
    # Load config
    loader = ConfigLoader(
        app_name=APP_NAME,
        config_class=MediaScannerConfig
    )
    
    config = loader.load(defaults_path=args.config)
    
    # Setup logging with config values
    setup_logging(level=config.logging.level, format=config.logging.format)
    
    # Pass config and overrides to scan_command
    return scan_command(
        config=config,
        target_media_path_override=args.target_media_path,
        database_path_override=args.database_path,
        worker_processes_override=args.worker_processes,
        worker_threads_override=args.worker_threads,
        use_exiftool_override=args.use_exiftool if args.use_exiftool else None,
        use_ffprobe_override=args.use_ffprobe if args.use_ffprobe else None
    )


if __name__ == "__main__":
    sys.exit(main())
