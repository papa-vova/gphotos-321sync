"""Shared logging configuration."""

from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


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
