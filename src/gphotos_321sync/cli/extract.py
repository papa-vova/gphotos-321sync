"""CLI command for extracting Takeout archives."""

import logging
from pathlib import Path
import sys

from ..config.loader import get_config
from ..processing.extractor import TakeoutExtractor
from ..logging_config import setup_logging


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


def extract_command() -> int:
    """Extract Takeout archives using configuration.
    
    All settings are loaded from config file.
    
    Returns:
        Exit code (0 for success)
    """
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = get_config()
        
        # Get paths from config
        src = Path(config.paths.takeout_archives)
        tgt = Path(config.paths.working_directory)
        
        logger.info(f"Source directory: {src}")
        logger.info(f"Target directory: {tgt}")
        
        # Validate source exists
        if not src.exists():
            logger.error(f"Source directory does not exist: {src}")
            return 1
        
        # Create extractor and run
        # preserve_structure=False so all archives extract to same dir
        # (Google Takeout archives all contain "Takeout" folder inside)
        
        # Prepare state file path
        state_file = Path(config.paths.temp_directory) / "extraction_state.json"
        
        extractor = TakeoutExtractor(
            source_dir=src,
            target_dir=tgt,
            verify_integrity=config.extraction.verify_checksums,
            preserve_structure=False,
            max_retry_attempts=config.extraction.max_retry_attempts,
            initial_retry_delay=config.extraction.initial_retry_delay_seconds,
            enable_resume=config.extraction.enable_resume,
            state_file=state_file,
            verify_extracted_files=config.extraction.verify_extracted_files
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
    return extract_command()


if __name__ == "__main__":
    sys.exit(main())
