"""Configuration models for media scanner."""

import os
from typing import Literal
from pydantic import BaseModel, Field


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")
    format: Literal["simple", "detailed", "json"] = Field(
        default="json",
        description="Log format type"
    )
    file: str | None = Field(default=None, description="Optional log file path")


class ScannerConfig(BaseModel):
    """Scanner performance configuration."""
    
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
    
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    scanner: ScannerConfig = Field(default_factory=ScannerConfig)
