"""Shared logging configuration."""

from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class LoggingConfig(BaseModel):
    """Logging configuration shared across all packages."""
    
    model_config = ConfigDict(extra='forbid')
    
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Log level"
    )
    format: Literal["simple", "detailed", "json"] = Field(
        default="json",
        description="Log format type"
    )
    file: str | None = Field(default=None, description="Optional log file path")
    
    @field_validator('level', mode='before')
    @classmethod
    def normalize_level(cls, v: str) -> str:
        """Normalize log level to uppercase for case-insensitive input."""
        if isinstance(v, str):
            return v.upper()
        return v
    
    @field_validator('format', mode='before')
    @classmethod
    def normalize_format(cls, v: str) -> str:
        """Normalize format to lowercase for case-insensitive input."""
        if isinstance(v, str):
            return v.lower()
        return v
