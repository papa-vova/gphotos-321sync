# Google Photos Sync (gphotos-321sync)

A comprehensive backup and synchronization tool for Google Photos Takeout archives.

## Goals

**Primary Objectives:**

- **Preserve your Google Photos data** - Extract and organize photos/videos from Google Takeout archives
- **Metadata integrity** - Maintain EXIF data, timestamps, GPS coordinates, and album information
- **Data ownership** - Keep full control of your photos with local or cloud storage options

**Key Features:**

- Automated extraction of Google Takeout archives (ZIP, TAR, 7z)
- Intelligent metadata extraction from EXIF and Google JSON files
- Metadata normalization and embedding into media files
- Virtual gallery organization by year, month, and albums
- Duplicate detection and file integrity verification
- Scalable architecture for processing large photo collections

## Quick Start

### Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/yourusername/gphotos-321sync.git
    cd gphotos-321sync
    ```

2. Create a virtual environment:

    ```bash
    python -m venv .venv
    # On Windows PowerShell:
    .venv\Scripts\Activate.ps1
    # On Linux/Mac:
    source .venv/bin/activate
    ```

3. Install dependencies:

    ```bash
    pip install -e .[dev]
    ```

### Running the Application

Start the application:

```bash
python -m gphotos_sync.main
```

The web interface will be available at `http://localhost:8080`

**Verify installation:**

- Health check: `http://localhost:8080/api/health`
- API documentation: `http://localhost:8080/api/docs`
- Current config: `http://localhost:8080/api/config`

### Configuration

Configuration is managed through multiple sources (in priority order):

1. **Environment variables** - `GPHOTOS_SECTION_KEY=value`
2. **User config** - `~/.config/gphotos-sync/config.toml` (Linux/Mac) or `%APPDATA%\gphotos-sync\config.toml` (Windows)
3. **System config** - `/etc/gphotos-sync/config.toml` (Linux/Mac) or `%PROGRAMDATA%\gphotos-sync\config.toml` (Windows)
4. **Default config** - `config/defaults.toml` (shipped with app)

**Configuration example:**

```toml
[paths]
takeout_archives = "C:/Users/YourName/Downloads"  # Use forward slashes
working_directory = "D:/GooglePhotos"

[resources]
max_cpu_percent = 80.0
max_memory_percent = 60.0
```

**Environment variable examples:**

```bash
# Windows PowerShell
$env:GPHOTOS_LOGGING_LEVEL="DEBUG"
$env:GPHOTOS_API_PORT="9000"

# Linux/Mac
export GPHOTOS_LOGGING_LEVEL=DEBUG
export GPHOTOS_API_PORT=9000
```

See `config/defaults.toml` for all available options or `.env.example` for environment variable format.

## Development

### Setup Development Environment

```bash
pip install -r requirements-dev.txt
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ --cov=src/gphotos_sync --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_config.py -v
```

### Code Formatting

```bash
black src/
ruff check src/
```

### Type Checking

```bash
mypy src/
```
