# Google Photos 3-2-1 Sync

Monorepo for Google Photos backup and synchronization tools.

## Goals

**Primary Objectives:**

- **Preserve your Google Photos data** - Extract and organize photos/videos from Google Takeout archives
- **Metadata integrity** - Maintain EXIF data, timestamps, GPS coordinates, and album information
- **Data ownership** - Keep full control of your photos with local or cloud storage options

**Key Features:**

- Automated extraction of Google Takeout archives
- Intelligent metadata extraction from EXIF and Google JSON files
- Metadata normalization and embedding into media files
- Virtual gallery organization by year, month, and albums
- Duplicate detection and file integrity verification
- Scalable architecture for processing large photo collections

## Packages

This monorepo contains three independent packages under the `gphotos_321sync` namespace:

| Package | Description | Status |
|---------|-------------|--------|
| **[gphotos-321sync-common](packages/gphotos-321sync-common/)** | Shared utilities (logging, errors, config) | Ready |
| **[gphotos-321sync-takeout-extractor](packages/gphotos-321sync-takeout-extractor/)** | Extract Google Takeout archives | Working |
| **[gphotos-321sync-media-scanner](packages/gphotos-321sync-media-scanner/)** | Scan and catalog media files | In Progress |

Each package can be installed and used independently. See individual package READMEs for detailed documentation.

## Quick Start

```bash
# Clone repository
git clone https://github.com/papa-vova/gphotos-321sync.git
cd gphotos-321sync

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1

# Install packages
pip install -e ./packages/gphotos-321sync-common
pip install -e ./packages/gphotos-321sync-takeout-extractor
pip install -e ./packages/gphotos-321sync-media-scanner
```

## Usage

See individual package READMEs for detailed usage:

- [Common utilities](packages/gphotos-321sync-common/README.md)
- [Takeout extractor](packages/gphotos-321sync-takeout-extractor/README.md)
- [Media scanner](packages/gphotos-321sync-media-scanner/README.md)

## Development

```bash
# Run tests
python -m pytest packages/

# Format code
python -m black packages/
python -m ruff check packages/
