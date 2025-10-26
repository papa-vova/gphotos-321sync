# End-to-End Testing Infrastructure

Comprehensive end-to-end testing framework for the media scanner with synthetic data generation and automated analysis.

## Overview

This testing infrastructure provides:

- **Synthetic data generation** - Creates realistic Google Takeout-like structures with ~10,000 files
- **Scanner execution** - Runs the media scanner with custom parameters
- **Automated analysis** - Compares filesystem vs database, identifies unprocessed files
- **Repeatable testing** - Supports initial scan, rescan, and load testing scenarios
- **Advanced matching validation** - Tests the 4-phase batch matching algorithm with exclusion

All generated data is fully synthetic with no personal information.

## Components

### 1. `generate_test_data.py`

Generates a complete synthetic test dataset resembling Google Takeout structure.

**Features:**

- Multiple album types (user albums + year-based albums)
- All supported media formats (images, videos, RAW)
- All JSON sidecar variants (standard, truncated, plain `.json`)
- Edge cases (edited files, duplicates, orphaned sidecars)
- Corrupted files for error handling tests
- Synthetic metadata (no personal data)
- Enhanced edge cases for testing the matching algorithm

**File Types Generated:**

| Category | Formats | Count |
|----------|---------|-------|
| Images | JPG, JPEG, PNG, GIF, WebP, HEIC | ~5,600 |
| Videos | MP4, M4V, MOV, 3GP, AVI | ~590 |
| RAW | NEF, CR2, ARW, DNG | ~100 |
| **Total Media** | | **~6,290** |
| **Sidecars** | JSON variants | **~5,660** |
| **Grand Total** | | **~10,000** |

**Album Structure:**

- 8 user albums with `metadata.json` (60% of files)
- 5 year-based albums "Photos from YYYY" (40% of files)
- Special albums for edge cases and corrupted files

**Edge Cases Included:**

- **Happy Path**: Standard media files with matching sidecars
- **Numbered Files**: Files with `(1)`, `(2)` suffixes in various positions
- **Edited Files**: Files with `-edited` suffix (case-insensitive)
- **Complex Cases**: Files with both numeric suffixes AND `-edited`
- **Tilde Duplicates**: Files with `~2`, `~3` suffixes
- **Extraction Duplicates**: Files with `(1)`, `(2)` suffixes
- **Files without sidecars**: 10 files
- **Orphaned sidecars**: 5 sidecars without media files
- **Long filenames**: For truncation testing
- **Corrupted/invalid files**: For error handling

### 2. `run_scanner_and_analyze.py`

Executes the media scanner and performs comprehensive analysis of results.

**Capabilities:**

- Runs scanner CLI with custom parameters
- Captures complete log output
- Analyzes filesystem structure
- Queries database for statistics
- Compares filesystem vs database counts
- Identifies unprocessed files
- Generates detailed JSON report

**Analysis Output:**

- Filesystem statistics (files by type, extension, album)
- Database statistics (scan runs, albums, media items, errors)
- Log analysis (error/warning counts, key events)
- Comparison results (matches/mismatches)
- List of unprocessed files
- Error summary by category

### 3. `example_usage.py`

Demonstrates usage patterns for various testing scenarios.

## Quick Start

**Important:** The data generator creates a proper Google Takeout structure:

```text
C:\temp\e2e_test_data\
└── Takeout\
    └── Google Photos\
        ├── Abstract Patterns\
        ├── Photos from 2020\
        └── ...
```

The scanner automatically detects this structure when you point it to the root directory.

### Generate Test Data

```powershell
python tests_e2e\generate_test_data.py --output-dir C:\temp\e2e_test_data
```

**Note:** This creates a `Takeout/Google Photos/` subdirectory structure. When running the scanner, point to the root directory (e.g., `C:\temp\e2e_test_data`), and it will automatically detect and scan the `Takeout/Google Photos/` subfolder.

Options:

- `--output-dir` - Directory for generated data (required)
- `--total-files` - Target total file count (default: 10000)

### Run Scanner and Analyze

```powershell
python tests_e2e\run_scanner_and_analyze.py --test-data-dir C:\temp\e2e_test_data
```

Options:

- `--test-data-dir` - Test data directory (required)
- `--db-path` - Database path (default: `test_data_dir/media.db`)
- `--log-path` - Log path (default: `test_data_dir/scan.log`)
- `--results-path` - Results JSON path (default: `test_data_dir/analysis.json`)
- `--worker-threads` - Number of worker threads (default: 4)
- `--use-exiftool` - Enable exiftool
- `--use-ffprobe` - Enable ffprobe
- `--skip-scan` - Skip scanner run, only analyze existing results

### View Examples

```powershell
python tests_e2e\example_usage.py
```

## Testing Scenarios

### Initial Scan Testing

Test the scanner's ability to process a fresh dataset.

```powershell
# Step 1: Generate test data
python tests_e2e\generate_test_data.py --output-dir C:\temp\e2e_test_data

# Step 2: Run scanner and analyze
python tests_e2e\run_scanner_and_analyze.py --test-data-dir C:\temp\e2e_test_data

# Step 3: Review results
# - Check console output for summary
# - Open C:\temp\e2e_test_data\analysis.json for details

# Step 4: Test repeatability (delete database and re-run)
Remove-Item C:\temp\e2e_test_data\media.db
python tests_e2e\run_scanner_and_analyze.py --test-data-dir C:\temp\e2e_test_data
```

**Expected Results:**

- All media files should be processed
- Filesystem count should match database count
- No unprocessed files (except intentionally corrupted ones)
- Consistent results across multiple runs

### Rescan Testing

Test the scanner's ability to detect unchanged files and changes.

```powershell
# Step 1: Generate test data
python tests_e2e\generate_test_data.py --output-dir C:\temp\e2e_test_data

# Step 2: Initial scan
python tests_e2e\run_scanner_and_analyze.py --test-data-dir C:\temp\e2e_test_data

# Step 3: Rescan (should detect unchanged files)
python tests_e2e\run_scanner_and_analyze.py --test-data-dir C:\temp\e2e_test_data

# Step 4: Modify some files
# (manually edit or delete some files)

# Step 5: Rescan again (should detect changes)
python tests_e2e\run_scanner_and_analyze.py --test-data-dir C:\temp\e2e_test_data
```

**Expected Results:**

- First rescan should detect all files as unchanged
- After modifications, rescan should detect changes
- Processing should be faster for unchanged files

## Output Files

After running the scanner, you'll find these files in the test data directory:

### `media.db`

SQLite database containing:

- `scan_runs` - Scan execution records
- `albums` - Discovered albums
- `media_items` - Processed media files with metadata
- `processing_errors` - Errors encountered during processing

### `scan.log`

Complete scanner log output with:

- Informational messages
- Warnings (e.g., heuristic matches)
- Errors (e.g., corrupted files)
- Progress updates
- Performance metrics

### `analysis.json`

Detailed analysis results with:

```json
{
  "timestamp": "2024-10-22T10:30:00",
  "filesystem": {
    "total_files": 10000,
    "media_files": 5000,
    "sidecar_files": 4500,
    "albums": 13,
    "by_extension": {...},
    "by_album": {...}
  },
  "database": {
    "scan_runs": 1,
    "albums": 13,
    "media_items": 4950,
    "processing_errors": 4,
    "by_mime_type": {...},
    "error_summary": {...}
  },
  "comparison": {
    "media_files": {
      "filesystem": 5000,
      "database": 4950,
      "difference": 50,
      "match": false
    }
  },
  "unprocessed_files": [...]
}
```

## Requirements

### Python Packages

- **Required**: `Pillow` (PIL) for image generation
- **Optional**: `exiftool`, `ffprobe` (for enhanced metadata extraction)

Install requirements:

```powershell
pip install Pillow
```

### Scanner Package

The media scanner package must be installed:

```powershell
pip install -e packages/gphotos-321sync-media-scanner
```

## Advanced Usage

### Custom Data Generation

Generate specific file counts:

```powershell
python tests_e2e\generate_test_data.py `
  --output-dir C:\temp\custom_test `
  --total-files 5000
```

### Scanner with External Tools

Run scanner with exiftool and ffprobe:

```powershell
python tests_e2e\run_scanner_and_analyze.py `
  --test-data-dir C:\temp\e2e_test_data `
  --worker-threads 8 `
  --use-exiftool `
  --use-ffprobe
```

### Analyze Existing Results

Analyze without re-running scanner:

```powershell
python tests_e2e\run_scanner_and_analyze.py `
  --test-data-dir C:\temp\e2e_test_data `
  --skip-scan
```

### Custom Output Paths

Specify custom paths for outputs:

```powershell
python tests_e2e\run_scanner_and_analyze.py `
  --test-data-dir C:\temp\e2e_test_data `
  --db-path C:\temp\custom.db `
  --log-path C:\temp\custom.log `
  --results-path C:\temp\custom_analysis.json
```

## Matching Algorithm Validation

The e2e tests now validate the 4-phase batch matching algorithm:

### Phase 1: Happy Path Matching

- Tests standard media files with matching sidecars
- Validates exact filename + extension matches
- Ensures proper exclusion of matched pairs

### Phase 2: Numbered Files Matching

- Tests files with numeric suffixes `(1)`, `(2)` in various positions
- Validates suffix extraction and matching logic
- Tests both end-of-filename and middle-of-filename suffixes

### Phase 3: Edited Files Matching

- Tests files with `-edited` suffix (case-insensitive)
- Validates stripping of `-edited` and subsequent matching
- Tests complex cases with both numeric suffixes AND `-edited`

### Phase 4: Unmatched Analysis

- Identifies remaining unmatched media files and sidecars
- Provides detailed statistics for each phase
- Validates exclusion logic worked correctly

### Expected Matching Statistics

A successful scan should show:

```json
{
  "matching_statistics": {
    "phase_1_happy_path": {
      "matches": 4500,
      "description": "Exact filename + extension matches"
    },
    "phase_2_numbered_files": {
      "matches": 800,
      "description": "Files with numeric suffixes"
    },
    "phase_3_edited_files": {
      "matches": 200,
      "description": "Files with -edited suffix"
    },
    "phase_4_unmatched": {
      "unmatched_media": 50,
      "unmatched_sidecars": 30,
      "description": "Remaining unmatched files"
    },
    "total_matches": 5500,
    "match_rate": "87.3%"
  }
}
```

### Validation Checks

The analysis automatically validates:

- **Exclusion Logic**: No file appears in multiple phases
- **Match Completeness**: All possible matches are found
- **Edge Case Handling**: Complex filename patterns work correctly
- **Performance**: Batch processing is efficient
- **Logging**: Detailed debug logs for each phase

## Interpreting Results

### Successful Scan

A successful scan should show:

- `comparison.media_files.match: true` - All media files processed
- `comparison.albums.match: true` - All albums discovered
- `unprocessed_files: []` - No unprocessed files (except corrupted)
- `database.processing_errors: 4` - Only expected corrupted files

### Common Issues

**Mismatch in file counts:**

- Check `unprocessed_files` list in `analysis.json`
- Review `scan.log` for errors
- Check `database.error_summary` for error categories

**High error count:**

- Review `processing_errors` table in database
- Check if external tools (exiftool, ffprobe) are missing
- Verify file permissions

**Performance issues:**

- Increase `--worker-threads`
- Check system resources (CPU, memory, disk I/O)
- Review log timestamps for bottlenecks

## Cleanup

Remove test data after testing:

```powershell
Remove-Item -Recurse -Force C:\temp\e2e_test_data
```

## Notes

- Test data generation requires PIL (Pillow) for image creation
- Without PIL, placeholder binary files are created instead
- All generated data is fully synthetic (no personal information)
- Test data can be safely deleted after testing
- Use `--use-exiftool` and `--use-ffprobe` only if tools are installed
- Generated images contain geometric patterns only (no people)

## Troubleshooting

### "Module not found" error

Ensure you're running from the project root and the package is installed:

```powershell
cd C:\Users\papav\prj\gphotos-321sync
pip install -e packages/gphotos-321sync-media-scanner
```

### "PIL not available" warning

Install Pillow:

```powershell
pip install Pillow
```

### Scanner fails to start

Check that the media scanner CLI is accessible:

```powershell
python -m gphotos_321sync.media_scanner --help
```

### Analysis shows many unprocessed files

- Review `scan.log` for errors
- Check file permissions
- Verify scanner completed successfully (exit code 0)
- Check matching algorithm statistics in `analysis.json`
