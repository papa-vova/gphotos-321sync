"""CLI command for extracting Takeout archives."""

import logging
import argparse
import tempfile
from pathlib import Path
import sys
from typing import Optional

from .extractor import TakeoutExtractor
from .config import TakeoutExtractorConfig
from gphotos_321sync.common import setup_logging, ConfigLoader

# Application name derived from package name
_package = __package__ or "gphotos_321sync.takeout_extractor"
APP_NAME = _package.replace('_', '-').replace('.', '-')


def progress_callback(logger: logging.Logger, current: int, total: int, name: str) -> None:
    """Log extraction progress.
    
    Args:
        logger: Logger instance
        current: Current archive number (1-based)
        total: Total number of archives
        name: Name of current archive
    """
    if current > total:
        logger.info(f"Extraction complete: {total} archive(s) processed")
    else:
        percent = (current / total) * 100 if total > 0 else 0
        logger.info(f"Extracting archive {current}/{total} ({percent:.1f}%): {name}")


def extract_command(
    config: 'TakeoutExtractorConfig',
    source_dir_override: Optional[Path] = None,
    target_dir_override: Optional[Path] = None,
    verify_override: Optional[bool] = None
) -> int:
    """Extract Takeout archives.
    
    Args:
        config: Configuration object
        source_dir_override: Optional override for source directory
        target_dir_override: Optional override for target directory
        verify_override: Optional override for verification
    
    Returns:
        Exit code (0 for success)
    """
    # Logging already set up in main(), just get logger
    # Use __package__ to avoid __main__ when run as module
    logger_name = __package__ or __name__
    logger = logging.getLogger(logger_name)
    
    # Apply overrides
    source_dir = source_dir_override if source_dir_override else Path(config.extraction.source_dir)
    target_dir = target_dir_override if target_dir_override else Path(config.extraction.target_dir)
    verify = verify_override if verify_override is not None else config.extraction.verify_checksums
    max_retry_attempts = config.extraction.max_retry_attempts
    initial_retry_delay = config.extraction.initial_retry_delay
    enable_resume = config.extraction.enable_resume
    verify_extracted_files = config.extraction.verify_extracted_files
    
    try:
        logger.info(f"Source directory: {source_dir}")
        logger.info(f"Target directory: {target_dir}")
        
        # Validate source exists
        if not source_dir.exists():
            logger.error(f"Source directory does not exist: {source_dir}")
            return 1
        
        # Validate target exists
        if not target_dir.exists():
            logger.error(f"Target directory does not exist: {target_dir}")
            return 1
        
        # Create state file in temp directory
        temp_dir = Path(tempfile.gettempdir()) / APP_NAME
        temp_dir.mkdir(parents=True, exist_ok=True)
        state_file = temp_dir / "extraction_state.json"
        
        # Create extractor and run
        extractor = TakeoutExtractor(
            source_dir=source_dir,
            target_dir=target_dir,
            verify_integrity=verify,
            preserve_structure=False,
            max_retry_attempts=max_retry_attempts,
            initial_retry_delay=initial_retry_delay,
            enable_resume=enable_resume,
            state_file=state_file,
            verify_extracted_files=verify_extracted_files
        )
        
        results = extractor.run(
            recursive=True,
            progress_callback=lambda c, t, n: progress_callback(logger, c, t, n)
        )
        
        # Log results
        if not results:
            logger.warning("No archives found to extract")
            return 0
        
        successful = []
        failed = []
        
        for archive_name, extract_path in results.items():
            if extract_path:
                successful.append((archive_name, extract_path))
                logger.info(f"Successfully extracted: {archive_name} -> {extract_path}")
            else:
                failed.append(archive_name)
                logger.error(f"Failed to extract: {archive_name}")
        
        logger.info(f"Extraction complete: {len(successful)} successful, {len(failed)} failed")
        
        return 1 if failed else 0
        
    except Exception as e:
        logger.exception(f"Extraction failed: {e}")
        return 1


def main() -> int:
    """Main entry point for extract command."""
    parser = argparse.ArgumentParser(
        description="Extract Google Takeout archives"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        required=False,
        help="Directory containing Takeout archives (overrides config)"
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        required=False,
        help="Directory to extract archives to (overrides config)"
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip checksum verification"
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
        config_class=TakeoutExtractorConfig
    )
    
    config = loader.load(defaults_path=args.config)
    
    # Setup logging with config values
    setup_logging(level=config.logging.level, format_type=config.logging.format)
    
    # Pass config and overrides to extract_command (which will setup logging)
    return extract_command(
        config=config,
        source_dir_override=args.source_dir,
        target_dir_override=args.target_dir,
        verify_override=not args.no_verify if args.no_verify else None
    )


if __name__ == "__main__":
    sys.exit(main())
