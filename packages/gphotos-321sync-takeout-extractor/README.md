# gphotos-321sync-takeout-extractor

Extract and process Google Takeout archives.

## Installation

```bash
pip install gphotos-321sync-takeout-extractor
```

## Usage

### Python API

```python
from gphotos_321sync.takeout_extractor import TakeoutExtractor
from pathlib import Path

extractor = TakeoutExtractor(
    source_dir=Path("/path/to/archives"),
    target_dir=Path("/path/to/output")
)

results = extractor.run(recursive=True)
print(f"Extracted {len(results)} archives")
```

### Command Line

```bash
gphotos-extract --source-dir /path/to/archives --target-dir /path/to/output
```

## Features

- Supports ZIP, TAR, and 7z archives
- Resumable extraction
- CRC32 verification
- Unicode path normalization
- Progress tracking
