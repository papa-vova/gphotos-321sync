"""Configuration schema for takeout extractor."""

from pydantic import BaseModel, Field, ConfigDict
from pathlib import Path
from gphotos_321sync.common import LoggingConfig


class ExtractionConfig(BaseModel):
    """Configuration for takeout extraction."""
    
    model_config = ConfigDict(extra='forbid')
    
    source_dir: str = Field(
        default=".",
        description="Directory containing Takeout archives"
    )
    target_media_path: str = Field(
        default="./extracted",
        description="Target media directory to extract archives to"
    )
    verify_checksums: bool = Field(
        default=True,
        description="Verify file checksums after extraction"
    )
    max_retry_attempts: int = Field(
        default=10,
        ge=1,
        description="Maximum number of retry attempts for failed extractions"
    )
    initial_retry_delay: float = Field(
        default=32.0,
        ge=32,
        description="Initial delay in seconds before retrying (doubles each attempt)"
    )
    enable_resume: bool = Field(
        default=True,
        description="Enable resuming interrupted extractions"
    )
    verify_extracted_files: bool = Field(
        default=True,
        description="Verify extracted files match archive contents"
    )


class TakeoutExtractorConfig(BaseModel):
    """Root configuration for takeout extractor."""
    
    model_config = ConfigDict(extra='forbid')
    
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
