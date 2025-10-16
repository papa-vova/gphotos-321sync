"""Configuration models for media scanner."""

import os
from pydantic import BaseModel, Field, ConfigDict
from gphotos_321sync.common import LoggingConfig


class ScannerConfig(BaseModel):
    """Scanner performance configuration."""
    
    model_config = ConfigDict(extra='forbid')
    
    target_media_path: str = Field(
        default="",
        description="Path to the target media folder to scan (extracted Takeout files)"
    )
    database_path: str | None = Field(
        default=None,
        description="Path to SQLite database file (default: target_media_path/media.db)"
    )
    worker_threads: int = Field(
        default_factory=lambda: os.cpu_count() * 2 if os.cpu_count() else 4,
        description="Number of I/O worker threads (default: 2 × CPU cores)"
    )
    worker_processes: int = Field(
        default_factory=lambda: os.cpu_count() or 2,
        description="Number of CPU worker processes (default: CPU cores)"
    )
    batch_size: int = Field(
        default=100,
        description="Number of records to batch for database writes"
    )
    queue_maxsize: int = Field(
        default=1000,
        description="Maximum size of work and results queues"
    )
    use_ffprobe: bool = Field(
        default=False,
        description="Use ffprobe for video metadata extraction (duration, resolution, fps). Optional tool."
    )
    use_exiftool: bool = Field(
        default=False,
        description="Use exiftool for RAW format EXIF extraction (DNG, CR2, NEF, ARW). Optional tool."
    )


class MediaScannerConfig(BaseModel):
    """Root configuration for media scanner."""
    
    model_config = ConfigDict(extra='forbid')
    
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    scanner: ScannerConfig = Field(default_factory=ScannerConfig)
