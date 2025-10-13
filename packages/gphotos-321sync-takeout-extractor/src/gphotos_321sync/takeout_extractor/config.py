"""Configuration schema for takeout extractor."""

from pydantic import BaseModel, Field
from pathlib import Path


class ExtractionConfig(BaseModel):
    """Configuration for takeout extraction."""
    
    source_dir: str = Field(
        default=".",
        description="Directory containing Takeout archives"
    )
    target_dir: str = Field(
        default="./extracted",
        description="Directory to extract archives to"
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
    
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
