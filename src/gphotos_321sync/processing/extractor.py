"""Archive discovery and extraction for Google Takeout files."""

import logging
import zipfile
import tarfile
import shutil
import json
import time
import hashlib
import re
import zlib
import gc
from pathlib import Path
from typing import List, Dict, Optional, Callable, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


def calculate_crc32(file_path: Path) -> int:
    """Calculate CRC32 checksum of a file.
    
    Args:
        file_path: Path to file
        
    Returns:
        CRC32 checksum as unsigned 32-bit integer
    """
    crc = 0
    with open(file_path, 'rb') as f:
        while chunk := f.read(65536):  # 64KB chunks
            crc = zlib.crc32(chunk, crc)
    return crc & 0xFFFFFFFF  # Ensure unsigned 32-bit

# Windows invalid filename characters
WINDOWS_INVALID_CHARS = r'[<>:"|?*]'
WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
}


def sanitize_filename(filename: str) -> tuple[str, bool]:
    """Sanitize filename for Windows compatibility.
    
    Args:
        filename: Original filename from archive
        
    Returns:
        Tuple of (sanitized_filename, was_modified)
    """
    original = filename
    
    # Replace invalid characters with underscore
    filename = re.sub(WINDOWS_INVALID_CHARS, '_', filename)
    
    # Handle path components
    parts = filename.split('/')
    sanitized_parts = []
    
    for part in parts:
        if not part:
            sanitized_parts.append(part)
            continue
            
        # Remove trailing dots and spaces (Windows doesn't allow)
        part = part.rstrip('. ')
        
        # Check for reserved names
        name_without_ext = part.split('.')[0].upper()
        if name_without_ext in WINDOWS_RESERVED_NAMES:
            part = f"_{part}"
        
        sanitized_parts.append(part)
    
    filename = '/'.join(sanitized_parts)
    
    was_modified = (filename != original)
    if was_modified:
        logger.debug(f"Sanitized filename: '{original}' -> '{filename}'")
    
    return filename, was_modified


class ArchiveFormat(Enum):
    """Supported archive formats."""
    ZIP = "zip"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
    TGZ = "tgz"
    TBZ2 = "tbz2"


@dataclass
class FileExtractionRecord:
    """Record of an extracted file for state tracking."""
    path: str  # Relative path within archive
    size: int  # File size in bytes
    extracted_at: str  # ISO timestamp
    crc32: Optional[int] = None  # CRC32 checksum from ZIP metadata


@dataclass
class ArchiveExtractionState:
    """State of archive extraction for resumption."""
    archive_name: str
    archive_path: str
    archive_size: int
    started_at: str
    completed_at: Optional[str] = None
    extracted_files: Dict[str, FileExtractionRecord] = field(default_factory=dict)
    failed_files: Dict[str, str] = field(default_factory=dict)  # path -> error message
    total_files: int = 0
    
    def mark_file_extracted(self, file_path: str, size: int, crc32: Optional[int] = None):
        """Mark a file as successfully extracted."""
        self.extracted_files[file_path] = FileExtractionRecord(
            path=file_path,
            size=size,
            extracted_at=datetime.utcnow().isoformat(),
            crc32=crc32
        )
    
    def mark_file_failed(self, file_path: str, error: str):
        """Mark a file as failed extraction."""
        self.failed_files[file_path] = error
    
    def is_file_extracted(self, file_path: str) -> bool:
        """Check if a file has been extracted."""
        return file_path in self.extracted_files
    
    def get_progress(self) -> tuple[int, int]:
        """Get extraction progress (extracted, total)."""
        return len(self.extracted_files), self.total_files


@dataclass
class ExtractionState:
    """Overall extraction state for all archives."""
    session_id: str
    started_at: str
    archives: Dict[str, ArchiveExtractionState] = field(default_factory=dict)
    
    def get_or_create_archive_state(self, archive: 'ArchiveInfo') -> ArchiveExtractionState:
        """Get or create state for an archive."""
        if archive.name not in self.archives:
            self.archives[archive.name] = ArchiveExtractionState(
                archive_name=archive.name,
                archive_path=str(archive.path),
                archive_size=archive.size_bytes,
                started_at=datetime.utcnow().isoformat()
            )
        return self.archives[archive.name]
    
    def save(self, state_file: Path):
        """Save state to JSON file.
        
        Note: Only saves extracted_files for incomplete archives to reduce memory usage.
        Completed archives only store summary statistics.
        """
        state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict for JSON serialization
        state_dict = {
            'session_id': self.session_id,
            'started_at': self.started_at,
            'archives': {}
        }
        
        for name, archive_state in self.archives.items():
            # For completed archives, don't save the full extracted_files list to save memory
            # Only save it for incomplete archives (for resume capability)
            if archive_state.completed_at:
                # Archive completed - only save summary
                state_dict['archives'][name] = {
                    'archive_name': archive_state.archive_name,
                    'archive_path': archive_state.archive_path,
                    'archive_size': archive_state.archive_size,
                    'started_at': archive_state.started_at,
                    'completed_at': archive_state.completed_at,
                    'total_files': archive_state.total_files,
                    'extracted_files': {},  # Empty for completed archives
                    'failed_files': archive_state.failed_files
                }
            else:
                # Archive in progress - save full state for resume
                state_dict['archives'][name] = {
                    'archive_name': archive_state.archive_name,
                    'archive_path': archive_state.archive_path,
                    'archive_size': archive_state.archive_size,
                    'started_at': archive_state.started_at,
                    'completed_at': archive_state.completed_at,
                    'total_files': archive_state.total_files,
                    'extracted_files': {k: asdict(v) for k, v in archive_state.extracted_files.items()},
                    'failed_files': archive_state.failed_files
                }
        
        with open(state_file, 'w') as f:
            json.dump(state_dict, f, indent=2)
        
        logger.debug(f"Saved extraction state to {state_file}")
    
    @classmethod
    def load(cls, state_file: Path) -> Optional['ExtractionState']:
        """Load state from JSON file."""
        if not state_file.exists():
            return None
        
        try:
            with open(state_file, 'r') as f:
                state_dict = json.load(f)
            
            state = cls(
                session_id=state_dict['session_id'],
                started_at=state_dict['started_at']
            )
            
            for name, archive_dict in state_dict.get('archives', {}).items():
                archive_state = ArchiveExtractionState(
                    archive_name=archive_dict['archive_name'],
                    archive_path=archive_dict['archive_path'],
                    archive_size=archive_dict['archive_size'],
                    started_at=archive_dict['started_at'],
                    completed_at=archive_dict.get('completed_at'),
                    total_files=archive_dict.get('total_files', 0),
                    failed_files=archive_dict.get('failed_files', {})
                )
                
                # Reconstruct extracted files
                for file_path, file_dict in archive_dict.get('extracted_files', {}).items():
                    archive_state.extracted_files[file_path] = FileExtractionRecord(**file_dict)
                
                state.archives[name] = archive_state
            
            logger.info(f"Loaded extraction state from {state_file}")
            return state
            
        except Exception as e:
            logger.warning(f"Failed to load extraction state: {e}")
            return None


@dataclass
class ArchiveInfo:
    """Information about a discovered archive."""
    path: Path
    format: ArchiveFormat
    size_bytes: int
    name: str
    
    def __str__(self) -> str:
        size_mb = self.size_bytes / (1024 * 1024)
        return f"{self.name} ({self.format.value}, {size_mb:.2f} MB)"


class ArchiveDiscovery:
    """Discovers archives in a source directory."""
    
    # Map file extensions to archive formats
    EXTENSION_MAP = {
        '.zip': ArchiveFormat.ZIP,
        '.tar': ArchiveFormat.TAR,
        '.tar.gz': ArchiveFormat.TAR_GZ,
        '.tgz': ArchiveFormat.TGZ,
        '.tar.bz2': ArchiveFormat.TAR_BZ2,
        '.tbz2': ArchiveFormat.TBZ2,
    }
    
    def __init__(self, source_dir: Path):
        """Initialize archive discovery.
        
        Args:
            source_dir: Directory to search for archives
        """
        self.source_dir = Path(source_dir)
        if not self.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")
        if not self.source_dir.is_dir():
            raise NotADirectoryError(f"Source path is not a directory: {source_dir}")
    
    def discover(self, recursive: bool = True) -> List[ArchiveInfo]:
        """Discover all supported archives in the source directory.
        
        Args:
            recursive: Whether to search subdirectories
            
        Returns:
            List of discovered archives
        """
        archives = []
        
        # Use rglob for recursive, glob for non-recursive
        pattern = "**/*" if recursive else "*"
        
        for file_path in self.source_dir.glob(pattern):
            if not file_path.is_file():
                continue
            
            archive_format = self._detect_format(file_path)
            if archive_format:
                archive_info = ArchiveInfo(
                    path=file_path,
                    format=archive_format,
                    size_bytes=file_path.stat().st_size,
                    name=file_path.name
                )
                archives.append(archive_info)
                logger.debug(f"Discovered archive: {archive_info}")
        
        # Sort archives by name to ensure correct order (e.g., -001, -002, -003)
        archives.sort(key=lambda a: a.name)
        
        logger.info(f"Discovered {len(archives)} archive(s) in {self.source_dir}")
        return archives
    
    def _detect_format(self, file_path: Path) -> Optional[ArchiveFormat]:
        """Detect archive format from file extension.
        
        Args:
            file_path: Path to file
            
        Returns:
            Archive format or None if not supported
        """
        # Check for compound extensions first (.tar.gz, .tar.bz2)
        for ext, fmt in self.EXTENSION_MAP.items():
            if file_path.name.lower().endswith(ext):
                return fmt
        
        return None


class ArchiveExtractor:
    """Extracts archives to a target directory."""
    
    def __init__(
        self,
        target_dir: Path,
        verify_integrity: bool = True,
        preserve_structure: bool = True,
        max_retry_attempts: int = 10,
        initial_retry_delay: float = 32.0,
        enable_resume: bool = True,
        state_file: Optional[Path] = None,
        verify_extracted_files: bool = True
    ):
        """Initialize archive extractor.
        
        Args:
            target_dir: Directory to extract archives to
            verify_integrity: Whether to verify archive integrity before extraction
            preserve_structure: Whether to preserve directory structure from archive
            max_retry_attempts: Maximum number of retry attempts per file (then hard fail)
            initial_retry_delay: Initial delay (seconds), doubles each attempt
            enable_resume: Whether to enable resumption of interrupted extractions
            state_file: Path to state file for tracking progress
            verify_extracted_files: Whether to verify extracted files exist before skipping
        """
        self.target_dir = Path(target_dir)
        self.verify_integrity = verify_integrity
        self.preserve_structure = preserve_structure
        self.max_retry_attempts = max_retry_attempts
        self.initial_retry_delay = initial_retry_delay
        self.enable_resume = enable_resume
        self.state_file = Path(state_file) if state_file else None
        self.verify_extracted_files = verify_extracted_files
        
        # Create target directory if it doesn't exist
        self.target_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create extraction state
        self.state: Optional[ExtractionState] = None
        if self.enable_resume and self.state_file:
            self.state = ExtractionState.load(self.state_file)
            if self.state:
                logger.info(f"Resuming extraction from previous session: {self.state.session_id}")
        
        if not self.state:
            self.state = ExtractionState(
                session_id=datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
                started_at=datetime.utcnow().isoformat()
            )
    
    def extract(
        self,
        archive: ArchiveInfo,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Path:
        """Extract an archive to the target directory.
        
        Args:
            archive: Archive to extract
            progress_callback: Optional callback(current, total) for progress updates
            
        Returns:
            Path to extracted content
            
        Raises:
            ValueError: If archive format is not supported
            RuntimeError: If extraction fails
        """
        logger.info(f"Extracting {archive}")
        
        # Get or create state for this archive
        archive_state = self.state.get_or_create_archive_state(archive)
        
        # Check if archive was already completed in a previous session
        if archive_state.completed_at:
            logger.info(f"Archive {archive.name} marked as completed at {archive_state.completed_at}")
            
            # Determine extraction path
            if self.preserve_structure:
                extract_to = self.target_dir / archive.path.stem
            else:
                extract_to = self.target_dir
            
            # Verify all files actually exist with correct CRC32
            all_valid, bad_files = self._verify_archive_extraction(archive, extract_to)
            
            if all_valid:
                logger.info(f"Archive {archive.name} verified successfully, skipping")
                return extract_to
            elif bad_files:
                # Selective re-extraction of corrupted/missing files only
                logger.warning(
                    f"Archive {archive.name} has {len(bad_files)} corrupted/missing files, "
                    f"re-extracting them only"
                )
                try:
                    if archive.format == ArchiveFormat.ZIP:
                        self._extract_specific_files_from_zip(archive.path, extract_to, bad_files)
                        logger.info(f"Successfully repaired {archive.name}")
                        return extract_to
                    else:
                        logger.warning(f"Selective re-extraction not supported for {archive.format}, will re-extract entire archive")
                        # Mark as incomplete to trigger full re-extraction
                        archive_state.completed_at = None
                except Exception as e:
                    logger.error(f"Failed to re-extract specific files: {e}, will re-extract entire archive")
                    # Mark as incomplete to trigger full re-extraction
                    archive_state.completed_at = None
            else:
                # Verification failed but no specific files identified
                logger.warning(
                    f"Archive {archive.name} verification failed, will re-extract entire archive"
                )
                # Mark as incomplete to trigger re-extraction
                archive_state.completed_at = None
                # Continue to extraction below
        
        # Determine extraction subdirectory
        if self.preserve_structure:
            # Extract to subdirectory named after archive (without extension)
            extract_to = self.target_dir / archive.path.stem
        else:
            # Extract directly to target directory
            extract_to = self.target_dir
        
        extract_to.mkdir(parents=True, exist_ok=True)
        
        try:
            if archive.format == ArchiveFormat.ZIP:
                self._extract_zip(archive.path, extract_to, progress_callback, archive_state)
            elif archive.format in (
                ArchiveFormat.TAR,
                ArchiveFormat.TAR_GZ,
                ArchiveFormat.TGZ,
                ArchiveFormat.TAR_BZ2,
                ArchiveFormat.TBZ2
            ):
                self._extract_tar(archive.path, extract_to, progress_callback, archive_state)
            else:
                raise ValueError(f"Unsupported archive format: {archive.format}")
            
            # Mark archive as completed and save state
            # This will trigger the save logic to only store summary (not full file list)
            archive_state.completed_at = datetime.utcnow().isoformat()
            self._save_state()
            
            # Clear extracted_files dict from memory after archive completion to prevent OOM
            # The state file already saved (without the file list for completed archives)
            if archive_state:
                extracted_count = len(archive_state.extracted_files)
                logger.debug(f"Clearing {extracted_count} file records from memory for {archive.name}")
                archive_state.extracted_files.clear()
                # Also clear failed_files if archive completed successfully
                if not archive_state.failed_files:
                    archive_state.failed_files.clear()
                # Force garbage collection to free memory immediately
                gc.collect()
                logger.debug(f"Freed memory after completing {archive.name}")
            
            logger.info(f"Successfully extracted to {extract_to}")
            return extract_to
            
        except Exception as e:
            logger.error(f"Failed to extract {archive.path}: {e}")
            self._save_state()  # Save state even on failure
            raise RuntimeError(f"Extraction failed: {e}") from e
    
    def _save_state(self):
        """Save extraction state to file."""
        if self.enable_resume and self.state_file and self.state:
            try:
                self.state.save(self.state_file)
            except Exception as e:
                logger.warning(f"Failed to save extraction state: {e}")
    
    def _retry_with_backoff(
        self,
        operation: Callable,
        operation_name: str,
        *args,
        **kwargs
    ):
        """Retry an operation with exponential backoff.
        
        Args:
            operation: Function to retry
            operation_name: Name for logging
            *args, **kwargs: Arguments to pass to operation
            
        Returns:
            Result of operation
            
        Raises:
            RuntimeError: If all retries fail (FATAL - terminates entire extraction)
        """
        delay = self.initial_retry_delay
        
        for attempt in range(1, self.max_retry_attempts + 1):
            try:
                return operation(*args, **kwargs)
            except OSError as e:
                if attempt >= self.max_retry_attempts:
                    # Final attempt failed - raise fatal error
                    logger.error(
                        f"{operation_name} failed after {attempt} attempts: {e}"
                    )
                    logger.critical(f"FATAL: Terminating extraction process due to persistent error: {e}")
                    raise RuntimeError(
                        f"Extraction failed after {attempt} attempts: {e}"
                    ) from e
                
                # Log retry attempt
                logger.warning(
                    f"{operation_name} failed (attempt {attempt}/{self.max_retry_attempts}): {e}. "
                    f"Retrying in {delay:.0f}s..."
                )
                
                # Wait before retry
                time.sleep(delay)
                
                # Double delay for next retry (exponential backoff)
                delay *= 2
    
    def _verify_extracted_file(
        self,
        extract_to: Path,
        member_path: str,
        expected_size: Optional[int] = None,
        expected_crc32: Optional[int] = None
    ) -> bool:
        """Verify that an extracted file exists and matches expected properties.
        
        Args:
            extract_to: Base extraction directory
            member_path: Relative path of file within archive
            expected_size: Expected file size in bytes
            expected_crc32: Expected CRC32 checksum
            
        Returns:
            True if file exists and is valid, False otherwise
        """
        try:
            file_path = extract_to / member_path
            if not file_path.exists():
                logger.debug(f"File not found: {member_path}")
                return False
            
            # Check size
            if expected_size is not None:
                actual_size = file_path.stat().st_size
                if actual_size != expected_size:
                    logger.warning(
                        f"File size mismatch for {member_path}: "
                        f"expected {expected_size}, got {actual_size}"
                    )
                    return False
            
            # Check CRC32
            if expected_crc32 is not None:
                actual_crc32 = calculate_crc32(file_path)
                if actual_crc32 != expected_crc32:
                    logger.warning(
                        f"CRC32 mismatch for {member_path}: "
                        f"expected {expected_crc32:08X}, got {actual_crc32:08X}"
                    )
                    return False
            
            return True
        except Exception as e:
            logger.debug(f"Error verifying file {member_path}: {e}")
            return False
    
    def _verify_archive_extraction(
        self,
        archive: ArchiveInfo,
        extract_to: Path
    ) -> tuple[bool, List[str]]:
        """Verify all files from a completed archive exist with correct CRC32.
        
        Uses batch optimization: first scans directory tree once to check existence,
        then verifies CRC32 only for files that exist.
        
        Args:
            archive: Archive to verify
            extract_to: Directory where files were extracted
            
        Returns:
            Tuple of (all_valid, bad_files_list)
            - all_valid: True if all files verified, False if any issues
            - bad_files_list: List of file paths that need re-extraction (original names from ZIP)
        """
        try:
            logger.info(f"Verifying extraction of {archive.name}")
            
            if archive.format != ArchiveFormat.ZIP:
                logger.warning(f"Verification not possible for {archive.format.value} archives, will re-extract to be safe")
                return (False, [])  # Cannot verify, assume bad and trigger full re-extraction
            
            with zipfile.ZipFile(archive.path, 'r') as zip_ref:
                members = zip_ref.namelist()
                total = len(members)
                
                # Build expected files map with sanitized names
                # Keep mapping of sanitized -> original for re-extraction
                expected_files = {}
                sanitized_to_original = {}
                for member in members:
                    info = zip_ref.getinfo(member)
                    sanitized_member, _ = sanitize_filename(member)
                    expected_files[sanitized_member] = info
                    sanitized_to_original[sanitized_member] = member
                
                logger.debug(f"Verifying {total} files from {archive.name}")
                
                # Step 1: Batch existence check - scan directory tree once
                logger.debug("Scanning directory tree for existing files")
                existing_files = {}
                try:
                    for file_path in extract_to.rglob('*'):
                        if file_path.is_file():
                            rel_path = file_path.relative_to(extract_to)
                            # Convert to forward slashes for consistency with ZIP paths
                            rel_path_str = str(rel_path).replace('\\', '/')
                            existing_files[rel_path_str] = file_path
                except Exception as e:
                    logger.warning(f"Error scanning directory tree: {e}")
                    return (False, [])
                
                # Step 2: Check for missing/corrupted files
                bad_files = []  # Track files that need re-extraction (original names)
                
                # Check missing files
                for member_path in expected_files.keys():
                    if member_path not in existing_files:
                        bad_files.append(sanitized_to_original[member_path])
                
                if bad_files:
                    logger.warning(
                        f"Archive {archive.name} has {len(bad_files)} missing files "
                        f"(first 5: {bad_files[:5]})"
                    )
                    return (False, bad_files)
                
                # Step 3: Verify CRC32 for all files (expensive, but only if all exist)
                logger.debug(f"All {total} files exist, verifying CRC32 checksums")
                verified_count = 0
                
                for member_path, info in expected_files.items():
                    file_path = existing_files[member_path]
                    
                    # Verify size
                    actual_size = file_path.stat().st_size
                    if actual_size != info.file_size:
                        logger.warning(
                            f"Size mismatch for {member_path}: "
                            f"expected {info.file_size}, got {actual_size}"
                        )
                        bad_files.append(sanitized_to_original[member_path])
                        continue
                    
                    # Verify CRC32
                    actual_crc32 = calculate_crc32(file_path)
                    if actual_crc32 != info.CRC:
                        logger.warning(
                            f"CRC32 mismatch for {member_path}: "
                            f"expected {info.CRC:08X}, got {actual_crc32:08X}"
                        )
                        bad_files.append(sanitized_to_original[member_path])
                        continue
                    
                    verified_count += 1
                    
                    # Log progress every 100 files
                    if verified_count % 100 == 0:
                        logger.debug(f"Verified {verified_count}/{total} files")
                
                if bad_files:
                    logger.warning(
                        f"Archive {archive.name} has {len(bad_files)} corrupted files "
                        f"(first 5: {bad_files[:5]})"
                    )
                    return (False, bad_files)
                
                logger.info(f"Successfully verified all {total} files from {archive.name}")
                return (True, [])
                
        except Exception as e:
            logger.warning(f"Error verifying archive {archive.name}: {e}")
            return (False, [])
    
    def _extract_specific_files_from_zip(
        self,
        archive_path: Path,
        extract_to: Path,
        files_to_extract: List[str]
    ) -> None:
        """Extract specific files from a ZIP archive.
        
        Args:
            archive_path: Path to ZIP file
            extract_to: Directory to extract to
            files_to_extract: List of file paths (original names from ZIP) to extract
        """
        logger.info(f"Re-extracting {len(files_to_extract)} corrupted/missing files from {archive_path.name}")
        
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            for i, member in enumerate(files_to_extract, 1):
                try:
                    # Sanitize filename
                    sanitized_member, was_sanitized = sanitize_filename(member)
                    
                    if was_sanitized:
                        logger.info(f"Sanitized filename: '{member}' -> '{sanitized_member}'")
                    
                    # Extract to sanitized path
                    target_path = extract_to / sanitized_member
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Read from archive and write to sanitized path
                    with zip_ref.open(member) as source:
                        with open(target_path, 'wb') as target:
                            # Use smaller buffer (8KB) and explicit copying to reduce memory usage
                            while True:
                                chunk = source.read(8192)
                                if not chunk:
                                    break
                                target.write(chunk)
                    
                    logger.debug(f"Re-extracted {i}/{len(files_to_extract)}: {member}")
                    
                except Exception as e:
                    logger.error(f"Failed to re-extract {member}: {e}")
                    raise
        
        logger.info(f"Successfully re-extracted {len(files_to_extract)} files")
    
    def _extract_zip(
        self,
        archive_path: Path,
        extract_to: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        archive_state: Optional[ArchiveExtractionState] = None
    ) -> None:
        """Extract a ZIP archive.
        
        Args:
            archive_path: Path to ZIP file
            extract_to: Directory to extract to
            progress_callback: Optional progress callback
            archive_state: Optional state tracker for resumption
        """
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            members = zip_ref.namelist()
            total = len(members)
            
            # Update total files in state
            if archive_state:
                archive_state.total_files = total
            
            logger.debug(f"Extracting {total} files from ZIP archive")
            
            skipped = 0
            resumed = 0
            
            for i, member in enumerate(members):
                info = zip_ref.getinfo(member)
                
                # Sanitize filename for Windows compatibility
                sanitized_member, was_sanitized = sanitize_filename(member)
                
                # Check if file was already extracted
                if archive_state and self.enable_resume:
                    if archive_state.is_file_extracted(sanitized_member):
                        # Verify file still exists if verification is enabled
                        if self.verify_extracted_files:
                            # Get stored CRC32 from state
                            stored_record = archive_state.extracted_files.get(sanitized_member)
                            expected_crc32 = stored_record.crc32 if stored_record else info.CRC
                            
                            if self._verify_extracted_file(
                                extract_to, 
                                sanitized_member, 
                                info.file_size,
                                expected_crc32
                            ):
                                resumed += 1
                                if (i + 1) % 100 == 0:
                                    logger.info(
                                        f"Progress {i + 1}/{total} files "
                                        f"({resumed} resumed, {skipped} skipped)"
                                    )
                                if progress_callback:
                                    progress_callback(i + 1, total)
                                continue
                            else:
                                logger.info(f"Re-extracting {member} (verification failed)")
                        else:
                            resumed += 1
                            if (i + 1) % 100 == 0:
                                logger.info(
                                    f"Progress {i + 1}/{total} files "
                                    f"({resumed} resumed, {skipped} skipped)"
                                )
                            if progress_callback:
                                progress_callback(i + 1, total)
                            continue
                
                if was_sanitized:
                    logger.info(f"Sanitized filename: '{member}' -> '{sanitized_member}'")
                
                # Extract file with retry logic
                try:
                    def extract_operation():
                        # Extract to sanitized path
                        target_path = extract_to / sanitized_member
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Read from archive and write to sanitized path with explicit buffer control
                        with zip_ref.open(member) as source:
                            with open(target_path, 'wb') as target:
                                # Use smaller buffer (8KB) and explicit copying to reduce memory usage
                                while True:
                                    chunk = source.read(8192)
                                    if not chunk:
                                        break
                                    target.write(chunk)
                    
                    self._retry_with_backoff(
                        extract_operation,
                        f"Extraction of {member}"
                    )
                    
                    # Mark file as extracted in state (use sanitized name + CRC32)
                    if archive_state:
                        archive_state.mark_file_extracted(
                            sanitized_member, 
                            info.file_size,
                            info.CRC  # CRC32 from ZIP metadata
                        )
                        
                        # Save state periodically (every 100 files)
                        if (i + 1) % 100 == 0:
                            self._save_state()
                        
                        # Force garbage collection every 500 files to prevent memory buildup
                        if (i + 1) % 500 == 0:
                            gc.collect()
                            logger.debug(f"Performed garbage collection at {i + 1}/{total} files")
                    
                except (OSError, RuntimeError) as e:
                    # File extraction failed after all retries - this is now FATAL
                    logger.critical(f"FATAL: Extraction terminated due to persistent error on file {member}")
                    self._save_state()  # Save state before terminating
                    raise
                
                # Log progress every 100 files to avoid log spam
                if (i + 1) % 100 == 0:
                    logger.info(
                        f"Extracted {i + 1}/{total} files "
                        f"({resumed} resumed, {skipped} skipped)"
                    )
                
                if progress_callback:
                    progress_callback(i + 1, total)
            
            # Final state save
            self._save_state()
            
            if resumed > 0:
                logger.info(f"Resumed {resumed} previously extracted files")
            if skipped > 0:
                logger.warning(f"Skipped {skipped} files due to errors")
    
    def _extract_tar(
        self,
        archive_path: Path,
        extract_to: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        archive_state: Optional[ArchiveExtractionState] = None
    ) -> None:
        """Extract a TAR archive (including compressed variants).
        
        Args:
            archive_path: Path to TAR file
            extract_to: Directory to extract to
            progress_callback: Optional progress callback
            archive_state: Optional state tracker for resumption
        """
        # Determine compression mode
        if archive_path.suffix in ('.gz', '.tgz'):
            mode = 'r:gz'
        elif archive_path.suffix in ('.bz2', '.tbz2'):
            mode = 'r:bz2'
        else:
            mode = 'r'
        
        with tarfile.open(archive_path, mode) as tar_ref:
            members = tar_ref.getmembers()
            total = len(members)
            
            # Update total files in state
            if archive_state:
                archive_state.total_files = total
            
            skipped = 0
            resumed = 0
            
            for i, member in enumerate(members):
                # Security check: prevent path traversal
                if not self._is_safe_path(extract_to, member.name):
                    logger.warning(f"Skipping unsafe path: {member.name}")
                    skipped += 1
                    continue
                
                # Check if file was already extracted
                if archive_state and self.enable_resume:
                    if archive_state.is_file_extracted(member.name):
                        # Verify file still exists if verification is enabled
                        if self.verify_extracted_files:
                            if self._verify_extracted_file(extract_to, member.name, member.size):
                                resumed += 1
                                if (i + 1) % 100 == 0:
                                    logger.info(
                                        f"Progress {i + 1}/{total} files "
                                        f"({resumed} resumed, {skipped} skipped)"
                                    )
                                if progress_callback:
                                    progress_callback(i + 1, total)
                                continue
                            else:
                                logger.info(f"Re-extracting {member.name} (verification failed)")
                        else:
                            resumed += 1
                            if (i + 1) % 100 == 0:
                                logger.info(
                                    f"Progress {i + 1}/{total} files "
                                    f"({resumed} resumed, {skipped} skipped)"
                                )
                            if progress_callback:
                                progress_callback(i + 1, total)
                            continue
                
                # Extract file with retry logic
                try:
                    def extract_operation():
                        tar_ref.extract(member, extract_to)
                    
                    self._retry_with_backoff(
                        extract_operation,
                        f"Extraction of {member.name}"
                    )
                    
                    # Mark file as extracted in state
                    if archive_state:
                        archive_state.mark_file_extracted(member.name, member.size)
                        
                        # Save state periodically (every 100 files)
                        if (i + 1) % 100 == 0:
                            self._save_state()
                        
                        # Force garbage collection every 500 files to prevent memory buildup
                        if (i + 1) % 500 == 0:
                            gc.collect()
                            logger.debug(f"Performed garbage collection at {i + 1}/{total} files")
                
                except (OSError, RuntimeError) as e:
                    # File extraction failed after all retries - this is now FATAL
                    logger.critical(f"FATAL: Extraction terminated due to persistent error on file {member.name}")
                    self._save_state()  # Save state before terminating
                    raise
                
                # Log progress every 100 files
                if (i + 1) % 100 == 0:
                    logger.info(
                        f"Extracted {i + 1}/{total} files "
                        f"({resumed} resumed, {skipped} skipped)"
                    )
                
                if progress_callback:
                    progress_callback(i + 1, total)
            
            # Final state save
            self._save_state()
            
            if resumed > 0:
                logger.info(f"Resumed {resumed} previously extracted files")
            if skipped > 0:
                logger.warning(f"Skipped {skipped} files due to errors")
    
    def _is_safe_path(self, base_dir: Path, member_path: str) -> bool:
        """Check if extraction path is safe (no path traversal).
        
        Args:
            base_dir: Base extraction directory
            member_path: Path from archive member
            
        Returns:
            True if safe, False otherwise
        """
        target_path = (base_dir / member_path).resolve()
        return str(target_path).startswith(str(base_dir.resolve()))
    
    def extract_all(
        self,
        archives: List[ArchiveInfo],
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Path]:
        """Extract multiple archives.
        
        Args:
            archives: List of archives to extract
            progress_callback: Optional callback(current, total, archive_name) - current is 1-based
            
        Returns:
            Dictionary mapping archive names to extraction paths
        """
        results = {}
        total = len(archives)
        
        for i, archive in enumerate(archives, start=1):
            if progress_callback:
                progress_callback(i, total, archive.name)
            
            try:
                extract_path = self.extract(archive)
                results[archive.name] = extract_path
            except RuntimeError as e:
                # Fatal error - re-raise to terminate entire process
                logger.error(f"Failed to extract {archive.name}: {e}")
                raise
            except Exception as e:
                # Non-fatal error - log and continue
                logger.error(f"Failed to extract {archive.name}: {e}")
                results[archive.name] = None
        
        if progress_callback:
            progress_callback(total, total, "Complete")
        
        return results


class TakeoutExtractor:
    """High-level interface for discovering and extracting Google Takeout archives."""
    
    def __init__(
        self,
        source_dir: Path,
        target_dir: Path,
        verify_integrity: bool = True,
        preserve_structure: bool = True,
        max_retry_attempts: int = 10,
        initial_retry_delay: float = 32.0,
        enable_resume: bool = True,
        state_file: Optional[Path] = None,
        verify_extracted_files: bool = True
    ):
        """Initialize Takeout extractor.
        
        Args:
            source_dir: Directory containing Takeout archives
            target_dir: Directory to extract to
            verify_integrity: Whether to verify archive integrity
            preserve_structure: Whether to preserve directory structure
            max_retry_attempts: Maximum number of retry attempts per file
            initial_retry_delay: Initial delay (seconds), doubles each attempt
            enable_resume: Whether to enable resumption of interrupted extractions
            state_file: Path to state file for tracking progress
            verify_extracted_files: Whether to verify extracted files exist before skipping
        """
        self.discovery = ArchiveDiscovery(source_dir)
        self.extractor = ArchiveExtractor(
            target_dir,
            verify_integrity=verify_integrity,
            preserve_structure=preserve_structure,
            max_retry_attempts=max_retry_attempts,
            initial_retry_delay=initial_retry_delay,
            enable_resume=enable_resume,
            state_file=state_file,
            verify_extracted_files=verify_extracted_files
        )
    
    def run(
        self,
        recursive: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Path]:
        """Discover and extract all archives.
        
        Args:
            recursive: Whether to search subdirectories
            progress_callback: Optional progress callback
            
        Returns:
            Dictionary mapping archive names to extraction paths
        """
        logger.info("Starting Takeout extraction process")
        
        # Discover archives
        archives = self.discovery.discover(recursive=recursive)
        
        if not archives:
            logger.warning("No archives found")
            return {}
        
        # Extract all archives
        results = self.extractor.extract_all(archives, progress_callback)
        
        successful = sum(1 for path in results.values() if path is not None)
        logger.info(f"Extraction complete: {successful}/{len(archives)} successful")
        
        return results
