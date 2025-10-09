"""Archive discovery and extraction for Google Takeout files."""

import logging
import zipfile
import tarfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ArchiveFormat(Enum):
    """Supported archive formats."""
    ZIP = "zip"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
    TGZ = "tgz"
    TBZ2 = "tbz2"


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
        preserve_structure: bool = True
    ):
        """Initialize archive extractor.
        
        Args:
            target_dir: Directory to extract archives to
            verify_integrity: Whether to verify archive integrity before extraction
            preserve_structure: Whether to preserve directory structure from archive
        """
        self.target_dir = Path(target_dir)
        self.verify_integrity = verify_integrity
        self.preserve_structure = preserve_structure
        
        # Create target directory if it doesn't exist
        self.target_dir.mkdir(parents=True, exist_ok=True)
    
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
                self._extract_zip(archive.path, extract_to, progress_callback)
            elif archive.format in (
                ArchiveFormat.TAR,
                ArchiveFormat.TAR_GZ,
                ArchiveFormat.TGZ,
                ArchiveFormat.TAR_BZ2,
                ArchiveFormat.TBZ2
            ):
                self._extract_tar(archive.path, extract_to, progress_callback)
            else:
                raise ValueError(f"Unsupported archive format: {archive.format}")
            
            logger.info(f"Successfully extracted to {extract_to}")
            return extract_to
            
        except Exception as e:
            logger.error(f"Failed to extract {archive.path}: {e}")
            raise RuntimeError(f"Extraction failed: {e}") from e
    
    def _extract_zip(
        self,
        archive_path: Path,
        extract_to: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> None:
        """Extract a ZIP archive.
        
        Args:
            archive_path: Path to ZIP file
            extract_to: Directory to extract to
            progress_callback: Optional progress callback
        """
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            members = zip_ref.namelist()
            total = len(members)
            
            logger.debug(f"Extracting {total} files from ZIP archive")
            
            skipped = 0
            for i, member in enumerate(members):
                try:
                    # Extract using extended-length path for Windows
                    # This handles both long paths and Unicode characters better
                    extract_to_extended = Path(f"\\\\?\\{extract_to.resolve()}")
                    zip_ref.extract(member, extract_to_extended)
                except OSError as e:
                    # If extended path fails, try normal path
                    try:
                        zip_ref.extract(member, extract_to)
                    except OSError as e2:
                        # Skip files that can't be extracted
                        logger.warning(f"Skipping file {member}: {e2}")
                        skipped += 1
                        continue
                
                # Log progress every 100 files to avoid log spam
                if (i + 1) % 100 == 0:
                    logger.info(f"Extracted {i + 1}/{total} files ({skipped} skipped)")
                
                if progress_callback:
                    progress_callback(i + 1, total)
            
            if skipped > 0:
                logger.warning(f"Skipped {skipped} files due to errors")
    
    def _extract_tar(
        self,
        archive_path: Path,
        extract_to: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> None:
        """Extract a TAR archive (including compressed variants).
        
        Args:
            archive_path: Path to TAR file
            extract_to: Directory to extract to
            progress_callback: Optional progress callback
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
            
            for i, member in enumerate(members):
                # Security check: prevent path traversal
                if not self._is_safe_path(extract_to, member.name):
                    logger.warning(f"Skipping unsafe path: {member.name}")
                    continue
                
                tar_ref.extract(member, extract_to)
                
                if progress_callback:
                    progress_callback(i + 1, total)
    
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
            except Exception as e:
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
        preserve_structure: bool = True
    ):
        """Initialize Takeout extractor.
        
        Args:
            source_dir: Directory containing Takeout archives
            target_dir: Directory to extract to
            verify_integrity: Whether to verify archive integrity
            preserve_structure: Whether to preserve directory structure
        """
        self.discovery = ArchiveDiscovery(source_dir)
        self.extractor = ArchiveExtractor(
            target_dir,
            verify_integrity=verify_integrity,
            preserve_structure=preserve_structure
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
