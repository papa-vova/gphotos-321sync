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

extractor = TakeoutExtractor(
    archives_dir="/path/to/takeout/archives",
    output_dir="/path/to/output"
)

result = extractor.extract_all()
print(f"Extracted {result.files_extracted} files")
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
