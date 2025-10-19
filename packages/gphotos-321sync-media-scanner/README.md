# gphotos-321sync-media-scanner

Scan and catalog media files from Google Photos Takeout.

## Installation

```bash
pip install gphotos-321sync-media-scanner
```

## Usage

### Command Line

```bash
# Using default config file (recommended)
# Config file location:
#   Windows: %LOCALAPPDATA%\gphotos-321sync-media-scanner\config.toml
#   Linux:   ~/.config/gphotos-321sync-media-scanner/config.toml
#   Mac:     ~/Library/Application Support/gphotos-321sync-media-scanner/config.toml
python -m gphotos_321sync.media_scanner

# Override config with command-line arguments
python -m gphotos_321sync.media_scanner --target-media-path /path/to/extracted/media

# With custom database location
python -m gphotos_321sync.media_scanner --target-media-path /path/to/media --database-path /path/to/media.db

# Enable optional tools (requires exiftool and ffprobe installed)
python -m gphotos_321sync.media_scanner --target-media-path /path/to/media --use-exiftool --use-ffprobe

# Custom worker configuration
python -m gphotos_321sync.media_scanner --target-media-path /path/to/media --worker-processes 4 --worker-threads 8

# Using a custom config file
python -m gphotos_321sync.media_scanner --config /path/to/custom/config.toml
```

### Python API

```python
from gphotos_321sync.media_scanner import ParallelScanner
from pathlib import Path

scanner = ParallelScanner(
    db_path=Path("media.db"),
    worker_processes=4,
    worker_threads=8,
    use_exiftool=False,
    use_ffprobe=False
)

results = scanner.scan(Path("/path/to/extracted/media"))
print(f"Scan complete: {results}")
```

### Configuration File

Create a `config.toml` file (see `config.example.toml`):

```toml
[scanner]
target_media_path = "/path/to/extracted/media"

[logging]
level = "INFO"
format = "detailed"
```

## Features

- Parallel media scanning (threads + processes)
- EXIF metadata extraction (PIL + optional exiftool for RAW)
- Video metadata extraction (optional ffprobe)
- Album detection and cataloging
- SQLite database storage
- Resumable scans
- Progress tracking

## Documentation

See the `docs/` directory for detailed architecture and implementation plans.
