# gphotos-321sync-common

Common utilities for gphotos_321sync packages.

## Installation

```bash
pip install gphotos-321sync-common
```

## Usage

```python
from gphotos_321sync.common import get_logger, GPSyncError

# Set up logging
logger = get_logger(__name__)
logger.info("Hello from common package")

# Use base error class
raise GPSyncError("Something went wrong", file_path="/path/to/file")
```

## Features

- **Structured logging** - JSON and human-readable formatters
- **Base error class** - With context support
- **Config utilities** - Path expansion, CPU detection
- **Path normalization** - Unicode NFC normalization + forward slash conversion
- **Checksums** - CRC32 computation for file integrity
