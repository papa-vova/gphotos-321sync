"""CLI command for extracting Takeout archives."""

import logging
import argparse
from pathlib import Path
import sys
from typing import Optional

from .extractor import TakeoutExtractor
from .config import TakeoutExtractorConfig
from gphotos_321sync.common import setup_logging, ConfigLoader


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


def extract_command(source_dir: Path, target_dir: Path, verify: bool = True) -> int:
    """Extract Takeout archives.
    
    Args:
        source_dir: Directory containing archives
        target_dir: Directory to extract to
        verify: Whether to verify checksums
    
    Returns:
        Exit code (0 for success)
    """
    # Setup logging
    setup_logging(level="INFO", format_type="simple")
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Source directory: {source_dir}")
        logger.info(f"Target directory: {target_dir}")
        
        # Validate source exists
        if not source_dir.exists():
            logger.error(f"Source directory does not exist: {source_dir}")
            return 1
        
        # Create target directory
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Create extractor and run
        extractor = TakeoutExtractor(
            source_dir=source_dir,
            target_dir=target_dir,
            verify_integrity=verify,
            preserve_structure=False,
            max_retry_attempts=3,
            initial_retry_delay=1.0,
            enable_resume=True,
            state_file=target_dir / ".extraction_state.json",
            verify_extracted_files=verify
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
        app_name="gphotos-321sync-takeout-extractor",
        config_class=TakeoutExtractorConfig
    )
    
    try:
        config = loader.load(defaults_path=args.config)
    except Exception as e:
        # If config fails to load, use defaults
        config = TakeoutExtractorConfig()
    
    # CLI arguments override config
    source_dir = args.source_dir if args.source_dir else Path(config.extraction.source_dir)
    target_dir = args.target_dir if args.target_dir else Path(config.extraction.target_dir)
    verify = not args.no_verify if args.no_verify else config.extraction.verify_checksums
    
    return extract_command(
        source_dir=source_dir,
        target_dir=target_dir,
        verify=verify
    )


if __name__ == "__main__":
    sys.exit(main())
