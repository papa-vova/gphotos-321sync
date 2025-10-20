"""
Script to copy sampled test data files to a test directory.

This script reads a file list (created by sample_test_data.py) and copies
the files to a test directory, preserving the directory structure.

Usage:
    python copy_test_data.py <sample_file_list> <source_root> <dest_root>

Example:
    python copy_test_data.py sample_files.txt /path/to/Takeout ./test_data

Note:
    - sample_file_list should contain RELATIVE paths (not absolute)
    - Use sample_test_data.py with --source-root to generate proper relative paths

IMPORTANT: This script is for local testing only. Do NOT commit the
test data directory to the repository.
"""

import argparse
import shutil
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

def parse_file_list(file_path: str) -> List[str]:
    """
    Read file list from input file.
    
    Args:
        file_path: Path to file containing list of files (one per line)
        
    Returns:
        List of file paths
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def copy_files(
    file_list: List[str],
    source_root: Path,
    dest_root: Path,
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Copy files from source to destination, preserving directory structure.
    
    Args:
        file_list: List of relative file paths
        source_root: Source root directory
        dest_root: Destination root directory
        dry_run: If True, only print what would be copied
        
    Returns:
        Tuple of (files_copied, files_skipped)
    """
    files_copied = 0
    files_skipped = 0
    
    for relative_path in file_list:
        source_file = source_root / relative_path
        dest_file = dest_root / relative_path
        
        # Check if source exists
        if not source_file.exists():
            logger.warning(f"Source not found: {relative_path}")
            files_skipped += 1
            continue
        
        # Skip if destination already exists
        if dest_file.exists():
            files_skipped += 1
            continue
        
        if dry_run:
            logger.info(f"Would copy: {relative_path}")
        else:
            # Create destination directory
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_file, dest_file)
            files_copied += 1
            
            if files_copied % 10 == 0:
                logger.info(f"Copied {files_copied} files...")
    
    return files_copied, files_skipped


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Copy sampled test data files to a test directory'
    )
    parser.add_argument(
        'sample_file',
        help='File containing list of files to copy (created by sample_test_data.py)'
    )
    parser.add_argument(
        'source_root',
        help='Source root directory (e.g., /path/to/Takeout)'
    )
    parser.add_argument(
        'dest_root',
        help='Destination root directory (e.g., ./test_data)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be copied without actually copying'
    )
    
    args = parser.parse_args()
    
    # Convert to Path objects
    source_root = Path(args.source_root).resolve()
    dest_root = Path(args.dest_root).resolve()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    # Validate source exists
    if not source_root.exists():
        logger.error(f"Source directory does not exist: {source_root}")
        return 1
    
    # Read file list
    logger.info(f"Reading file list from: {args.sample_file}")
    file_list = parse_file_list(args.sample_file)
    logger.info(f"Found {len(file_list):,} files to copy")
    
    # Confirm before copying
    if not args.dry_run:
        logger.info(f"Source: {source_root}")
        logger.info(f"Dest:   {dest_root}")
        response = input("\nProceed with copy? [y/N]: ")
        if response.lower() != 'y':
            logger.info("Cancelled.")
            return 0
    
    # Copy files
    logger.info(f"{'DRY RUN: ' if args.dry_run else ''}Copying files...")
    files_copied, files_skipped = copy_files(
        file_list,
        source_root,
        dest_root,
        args.dry_run
    )
    
    # Log summary
    logger.info("=" * 70)
    logger.info("COPY SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Files copied:       {files_copied:>8,}")
    logger.info(f"Files skipped:      {files_skipped:>8,}")
    logger.info(f"Total:              {len(file_list):>8,}")
    logger.info("=" * 70)
    
    if not args.dry_run:
        logger.info(f"\n✅ Files copied to: {dest_root}")
        logger.info("\n⚠️  IMPORTANT: Do NOT commit this test data to the repository!")
        logger.info("   Add the test data directory to .gitignore")
    
    return 0


if __name__ == '__main__':
    exit(main())
