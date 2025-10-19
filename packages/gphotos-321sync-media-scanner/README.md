# gphotos-321sync-media-scanner

Scan and catalog media files from Google Photos Takeout.

## ⚠️ IMPORTANT: Google Takeout Structure

**Google Takeout places all albums in a specific subfolder structure:**

```text
target_media_path/               ← Point scanner here (ABSOLUTE path, e.g., C:\takeout_tests)
└── Takeout/
    └── Google Photos/           ← Albums are scanned from HERE
        ├── Photos from 2023/
        ├── Photos from 2024/
        ├── My Album/
        └── ...
```

**The scanner automatically detects this structure:**

- If `Takeout/Google Photos/` exists, it scans albums from there
- Otherwise, it scans from `target_media_path` directly (flat structure)
- All paths stored in database are **relative to `target_media_path`**

## Installation

```bash
pip install gphotos-321sync-media-scanner
```

## Usage

### Command Line

**Note**: `--target-media-path` must be an **absolute path** to your extraction folder.

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

**Note**: All paths must be **absolute paths** (use `Path().resolve()` if needed).

```python
from gphotos_321sync.media_scanner import ParallelScanner
from pathlib import Path

# Use absolute paths
target_path = Path(r"C:\takeout_tests").resolve()  # Absolute path to extraction folder
db_path = Path(r"C:\takeout_tests\media.db").resolve()  # Absolute path to database

scanner = ParallelScanner(
    db_path=db_path,
    worker_processes=4,
    worker_threads=8,
    use_exiftool=False,
    use_ffprobe=False
)

# Scanner will automatically detect Takeout/Google Photos/ structure
results = scanner.scan(target_path)
print(f"Scan complete: {results}")
```

### Configuration File

Create a `config.toml` file (see `config.example.toml`):

```toml
[scanner]
# ABSOLUTE path to your extraction folder (where Takeout/ is located)
target_media_path = "C:\\takeout_tests"  # Windows
# target_media_path = "/home/user/takeout_tests"  # Linux/Mac

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
