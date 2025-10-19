# gphotos-321sync-takeout-extractor

Extract and process Google Takeout archives.

## Installation

```bash
pip install gphotos-321sync-takeout-extractor
```

## Usage

### Command Line

```bash
# Using default config file (recommended)
# Config file location:
#   Windows: %LOCALAPPDATA%\gphotos-321sync-takeout-extractor\config.toml
#   Linux:   ~/.config/gphotos-321sync-takeout-extractor/config.toml
#   Mac:     ~/Library/Application Support/gphotos-321sync-takeout-extractor/config.toml
python -m gphotos_321sync.takeout_extractor

# Override config with command-line arguments
python -m gphotos_321sync.takeout_extractor --source-dir /path/to/archives --target-media-path /path/to/output

# Skip checksum verification (faster)
python -m gphotos_321sync.takeout_extractor --source-dir /path/to/archives --target-media-path /path/to/output --no-verify

# Using a custom config file
python -m gphotos_321sync.takeout_extractor --config /path/to/custom/config.toml
```

### Python API

```python
from gphotos_321sync.takeout_extractor import TakeoutExtractor
from pathlib import Path

extractor = TakeoutExtractor(
    source_dir=Path("/path/to/archives"),
    target_media_path=Path("/path/to/output"),
    verify_integrity=True,
    enable_resume=True
)

results = extractor.run(recursive=True)
print(f"Extracted {len(results)} archives")
```

### Configuration File

Create a `config.toml` file (see `config.example.toml`):

```toml
[extraction]
source_dir = "/path/to/archives"
target_media_path = "/path/to/output"

[logging]
level = "INFO"
format = "detailed"
```

## Features

- Supports Google Takeout archives (zip, tgz)
- Resumable extraction with state tracking
- CRC32 verification for data integrity
- Unicode path normalization
- Progress tracking
- Automatic retry on failures
