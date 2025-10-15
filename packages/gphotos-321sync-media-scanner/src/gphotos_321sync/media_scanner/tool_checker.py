"""Tool availability checker for external dependencies."""

import shutil
import subprocess
import logging
import sys
from typing import Dict
from .errors import ToolNotFoundError

logger = logging.getLogger(__name__)


def check_tool_availability() -> Dict[str, bool]:
    """
    Check availability of external tools for metadata extraction.
    
    Returns:
        Dictionary mapping tool names to availability status:
        - 'ffprobe': For video metadata extraction (optional)
        - 'exiftool': For RAW format EXIF extraction (optional)
    """
    tools = {}
    
    # Check ffprobe (part of ffmpeg) - optional for video metadata
    tools['ffprobe'] = shutil.which('ffprobe') is not None
    
    # Check exiftool - optional for RAW formats (DNG, CR2, NEF, ARW)
    tools['exiftool'] = shutil.which('exiftool') is not None
    
    return tools


def _require_tool(tool_name: str) -> None:
    """
    Raise error if a tool is not available.
    
    Internal helper for check_required_tools().
    
    Args:
        tool_name: Name of the tool to check ('ffprobe', 'exiftool')
        
    Raises:
        ToolNotFoundError: If the tool is not available with installation instructions
    """
    tools = check_tool_availability()
    
    if not tools.get(tool_name, False):
        instructions = _get_installation_instructions(tool_name)
        raise ToolNotFoundError(
            f"Tool '{tool_name}' is enabled in config but not available.\n\n{instructions}"
        )


def check_required_tools(use_ffprobe: bool = False, use_exiftool: bool = False) -> None:
    """
    Check if configured tools are available and raise error if required but missing.
    
    If a tool is enabled in config but not available, raises ToolNotFoundError.
    Logs at INFO level for all cases.
    
    Args:
        use_ffprobe: Whether ffprobe is required (from config)
        use_exiftool: Whether exiftool is required (from config)
        
    Raises:
        ToolNotFoundError: If a tool is enabled in config but not available
    """
    tools = check_tool_availability()
    
    # Check ffprobe
    if use_ffprobe:
        if tools.get('ffprobe', False):
            logger.info("ffprobe: available - will extract video metadata (duration, resolution, fps)")
        else:
            logger.error("ffprobe: NOT FOUND but required by config (use_ffprobe=true)")
            _require_tool('ffprobe')  # Raises ToolNotFoundError
    else:
        logger.info("ffprobe: disabled in config - video metadata will not be extracted")
    
    # Check exiftool
    if use_exiftool:
        if tools.get('exiftool', False):
            logger.info("exiftool: available - will extract EXIF from RAW formats (DNG, CR2, NEF, ARW)")
        else:
            logger.error("exiftool: NOT FOUND but required by config (use_exiftool=true)")
            _require_tool('exiftool')  # Raises ToolNotFoundError
    else:
        logger.info("exiftool: disabled in config - RAW format EXIF will not be extracted")


def _get_installation_instructions(tool_name: str) -> str:
    """Get installation instructions for a missing tool."""
    instructions = {
        'ffprobe': (
            "ffprobe is part of FFmpeg. Install it:\n"
            "  - Windows: Download from https://ffmpeg.org/download.html\n"
            "  - macOS: brew install ffmpeg\n"
            "  - Linux: sudo apt-get install ffmpeg (Debian/Ubuntu)\n"
            "           sudo yum install ffmpeg (RHEL/CentOS)"
        ),
        'exiftool': (
            "ExifTool is optional for RAW formats. Install it:\n"
            "  - Windows: Download from https://exiftool.org/\n"
            "  - macOS: brew install exiftool\n"
            "  - Linux: sudo apt-get install libimage-exiftool-perl"
        ),
    }
    
    return instructions.get(tool_name, f"Please install {tool_name}")
