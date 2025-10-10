# Test Suite Documentation

This directory contains the test suite for the Google Photos 3-2-1 Sync project.

## Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_extractor_verification.py

# Run with verbose output
python -m pytest -v

# Run with coverage
python -m pytest --cov=gphotos_321sync
```

## Test Files

### test_config.py

Tests for configuration management.

- **Configuration loading**: Validates loading from TOML files
- **Default values**: Ensures defaults are applied correctly
- **Validation**: Checks configuration validation logic

### test_extractor.py

Tests for basic archive extraction functionality.

- **Archive discovery**: Tests finding ZIP/TAR archives in directories
- **ZIP extraction**: Validates extracting ZIP archives
- **TAR extraction**: Validates extracting TAR.GZ archives
- **Progress callbacks**: Tests progress reporting during extraction
- **State persistence**: Tests saving and loading extraction state
- **Resume functionality**: Tests resuming interrupted extractions
- **Retry logic**: Tests exponential backoff on transient failures

### test_extractor_verification.py

Tests for archive verification and selective re-extraction.

#### Verification - Missing Files

- **All files missing**: Detects when no files from archive exist
- **Some files missing**: Detects partial extraction
- **One file missing**: Detects single missing file

#### Verification - Corrupted Files

- **Size mismatch (smaller)**: Detects truncated files
- **Size mismatch (larger)**: Detects files with extra data
- **CRC32 mismatch**: Detects files with correct size but wrong content

#### Verification - Mixed Scenarios

- **Missing and corrupted**: Tests fast-fail on missing files
- **First file corrupted**: Ensures corruption detected early
- **Last file corrupted**: Ensures full verification
- **Multiple corrupted**: Collects all corrupted files

#### Selective Re-Extraction

- **Single file re-extraction**: Re-extracts only one corrupted file
- **Multiple file re-extraction**: Re-extracts multiple corrupted files

#### Resume Logic

- **Completed archive verification**: Verifies and skips completed archives
- **Corrupted file detection**: Triggers selective re-extraction on resume

#### Edge Cases

- **Corrupted ZIP file**: Fails with clear error on invalid ZIP
- **Empty ZIP file**: Handles empty archives gracefully
- **Filename sanitization**: Verifies sanitized filenames correctly

### test_pipeline.py

Tests for the complete extraction pipeline.

- **End-to-end extraction**: Tests full workflow from discovery to completion
- **Pipeline integration**: Validates component integration
