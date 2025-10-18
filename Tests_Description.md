# Test Suite Documentation

Comprehensive documentation of all test suites in the gphotos-321sync project.

## Summary

**Total: 330 tests** (12 + 42 + 276)

- **gphotos-321sync-common:** 12 tests
- **gphotos-321sync-takeout-extractor:** 42 tests
- **gphotos-321sync-media-scanner:** 276 tests

---

## Table of Contents

- [gphotos-321sync-common](#gphotos-321sync-common)
- [gphotos-321sync-takeout-extractor](#gphotos-321sync-takeout-extractor)
- [gphotos-321sync-media-scanner](#gphotos-321sync-media-scanner)

---

## gphotos-321sync-common

### test_logging_config.py

Tests for shared `LoggingConfig` validation (9 tests).

**Rationale**: Ensures logging configuration accepts valid values, rejects invalid ones, and handles case-insensitive input for better user experience.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_valid_config` | level="INFO", format="json" | Valid LoggingConfig object | Valid parameters | Validates Pydantic model accepts correct values |
| 2 | `test_default_values` | No parameters | level="INFO", format="json" | Using defaults | Ensures default configuration values are sensible |
| 3 | `test_rejects_invalid_log_level` | level="TRACE" or "CRITICAL" | ValidationError raised | Invalid log level (not in allowed list) | Rejects unsupported log levels (only DEBUG/INFO/WARNING/ERROR allowed) |
| 4 | `test_rejects_invalid_format` | format="xml" | ValidationError raised | Invalid format (not in allowed list) | Rejects unsupported formats (only simple/detailed/json allowed) |
| 5 | `test_rejects_unknown_fields` | unknown_field="value" | ValidationError with "extra_forbidden" | Extra field not in schema | Ensures Pydantic's extra="forbid" rejects unknown fields |
| 6 | `test_case_insensitive_log_level` | level="info" or "Debug" | Normalized to "INFO", "DEBUG" | Case-insensitive input | Accepts any case, normalizes to uppercase for consistency |
| 7 | `test_case_insensitive_format` | format="JSON" or "Simple" | Normalized to "json", "simple" | Case-insensitive input | Accepts any case, normalizes to lowercase for consistency |
| 8 | `test_serialization` | Config with all fields | Dictionary matching input | Using model_dump() | Tests Pydantic serialization to dict |
| 9 | `test_deserialization` | Dictionary with config values | Valid LoggingConfig object | Using **dict unpacking | Tests Pydantic deserialization from dict |

### test_path_utils.py

Tests for path normalization utilities (3 tests).

**Rationale**: Ensures paths are normalized consistently across platforms (Windows/Unix) and Unicode forms for database storage and comparison.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_forward_slashes` | Path: "C:\\Users\\test\\photos\\image.jpg" (Windows) | "C:/Users/test/photos/image.jpg" | Windows backslashes | Converts backslashes to forward slashes for cross-platform consistency |
| 2 | `test_unicode_normalization` | Path: "café" (NFD: cafe\u0301) | "café" (NFC: caf\u00e9) | Decomposed Unicode | Normalizes to NFC form for consistent string comparison across filesystems |
| 3 | `test_relative_path` | Path: "photos/2023/image.jpg" | "photos/2023/image.jpg" (normalized) | Relative path | Handles relative paths correctly |

---

## gphotos-321sync-takeout-extractor

### test_config.py (takeout-extractor)

Tests for extractor-specific configuration (2 tests).

**Rationale**: Tests ONLY extractor-specific parameters and their defaults/overrides. Common validation patterns (extra='forbid', dict/object input) are tested in gphotos-321sync-common.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_extraction_config_defaults` | No parameters | source_dir=".", target_media_path="./extracted", verify_checksums=True, max_retry_attempts=10 | Using defaults | Tests extractor-specific default values |
| 2 | `test_extraction_config_custom_values` | Extractor-specific parameters | Config with custom values | Parameters provided | Tests extractor-specific parameter overrides |

### test_extractor.py

Tests for archive extraction functionality (16 tests).

**Note**: Tests 13-16 test the app's state persistence and retry infrastructure, not core extraction logic.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_discover_archives` | Directory with ZIP and TAR.GZ | 2 archives discovered | Archives present | Discovers archives by extension |
| 2 | `test_discover_no_archives` | Empty directory | Empty list | No archives | Returns empty list when no archives found (discovery only, not extraction) |
| 3 | `test_invalid_source_dir` | Non-existent source_dir path | FileNotFoundError raised immediately | source_dir doesn't exist | Validates source_dir parameter: app fails promptly if path not found/inaccessible |
| 4 | `test_source_is_file` | source_dir points to file instead of directory | NotADirectoryError raised immediately | source_dir is a file, not directory | Validates source_dir must be directory: app fails promptly if parameter is file |
| 5 | `test_extract_zip` | ZIP archive | Files extracted to target | Valid ZIP | Extracts ZIP archive |
| 6 | `test_extract_tar_gz` | TAR.GZ archive | Files extracted to target | Valid TAR.GZ | Extracts TAR.GZ archive |
| 7 | `test_extract_with_progress` | Archive with progress callback | Progress callbacks invoked | Callback provided | Reports extraction progress |
| 8 | `test_extract_all` | Multiple archives | All archives extracted | Multiple archives | Extracts all archives |
| 9 | `test_preserve_structure` | Archive with preserve_structure flag | Structure preserved or flattened | Flag setting | Respects preserve_structure option |
| 10 | `test_run` | Source dir with 2 archives (ZIP + TAR.GZ) | All 2 archives extracted to target_media_path | Valid source_dir and target_media_path | Complete extraction workflow: discovers archives, extracts all, returns results dict with archive paths |
| 11 | `test_run_with_progress` | Extraction with progress callback | Progress callbacks invoked | Callback provided | Reports overall progress |
| 12 | `test_run_no_archives` | Empty source directory (no archives) | RuntimeError raised with "No archives found" | No archives found | App fails with error when source folder is empty (no archives to extract) |
| 13 | `test_state_save_and_load` | Extraction state | State saved and loaded | State file used | Persists extraction state |
| 14 | `test_resume_extraction` | Interrupted extraction | Extraction resumes | State file exists | Resumes from saved state |
| 15 | `test_retry_on_transient_failure` | Mock function that fails 2x then succeeds, max_retry_attempts=3, initial_retry_delay=0.1s | _retry_with_backoff() returns "success" after 3 attempts | Tests retry wrapper with transient failures | Test calls mock function 3 times: fails with OSError twice, succeeds on 3rd attempt. Verifies retry logic works. |
| 16 | `test_retry_gives_up_after_max_attempts` | Mock function that always raises OSError, max_retry_attempts=2, initial_retry_delay=0.1s | _retry_with_backoff() raises RuntimeError after 2 failed attempts | Tests retry wrapper gives up | Test calls mock function 2 times, both fail with OSError. Verifies retry logic gives up and raises RuntimeError with "failed after 2 attempts" message. |

### test_extractor_verification.py

Tests for archive verification and selective re-extraction (24 tests).

**Purpose**: The app has a custom verification system that checks extracted files against ZIP metadata (CRC32 checksums). On resume, if files are missing/corrupted, it selectively re-extracts ONLY the bad files instead of re-extracting the entire archive.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_all_files_missing` | Extracted archive, all files deleted | _verify_archive_extraction() returns (False, [all 5 files]) | Verification detects missing files | Tests verification system detects when no files exist on disk |
| 2 | `test_some_files_missing` | Extracted archive, 2 files deleted | _verify_archive_extraction() returns (False, [2 files]) | Verification detects partial missing | Tests verification system detects subset of missing files |
| 3 | `test_one_file_missing` | Extracted archive, 1 file deleted | _verify_archive_extraction() returns (False, [1 file]) | Verification detects single missing | Tests verification system detects single missing file |
| 4 | `test_file_size_mismatch_smaller` | Extracted archive, file truncated | _verify_archive_extraction() returns (False, [truncated file]) | Verification detects size mismatch | Tests verification compares file size against ZIP metadata |
| 5 | `test_file_size_mismatch_larger` | Extracted archive, file enlarged | _verify_archive_extraction() returns (False, [enlarged file]) | Verification detects size mismatch | Tests verification compares file size against ZIP metadata |
| 6 | `test_file_crc32_mismatch` | Extracted archive, file content changed | _verify_archive_extraction() returns (False, [corrupted file]) | Verification detects content corruption | Tests verification compares CRC32 checksum against ZIP metadata |
| 7 | `test_missing_and_corrupted_files` | Extracted archive, mixed issues | _verify_archive_extraction() returns (False, [all bad files]) | Verification detects multiple issue types | Tests verification detects both missing and corrupted files |
| 8 | `test_first_file_corrupted` | Extracted archive, first file corrupted | _verify_archive_extraction() returns (False, [first file]) | Verification scans all files | Tests verification doesn't stop at first file |
| 9 | `test_last_file_corrupted` | Extracted archive, last file corrupted | _verify_archive_extraction() returns (False, [last file]) | Verification scans all files | Tests verification checks entire file list |
| 10 | `test_multiple_scattered_corrupted_files` | Extracted archive, multiple files corrupted | _verify_archive_extraction() returns (False, [all bad files]) | Verification collects all issues | Tests verification reports all corrupted files, not just first |
| 11 | `test_reextract_single_corrupted_file` | Corrupted file, call _extract_specific_files_from_zip() | File re-extracted with correct content | Selective re-extraction | Tests app can re-extract single file from ZIP without extracting entire archive |
| 12 | `test_reextract_multiple_files` | Multiple corrupted files, call _extract_specific_files_from_zip() | Files re-extracted with correct content | Selective re-extraction | Tests app can re-extract multiple specific files from ZIP |
| 13 | `test_resume_with_completed_archive_verified` | State file shows "completed", all files valid | extract() verifies files and skips re-extraction | Resume workflow | Tests resume: loads state → sees completed → verifies files → skips extraction |
| 14 | `test_resume_with_corrupted_file_reextracts` | State file shows "completed", 1 file corrupted | extract() detects corruption → selectively re-extracts bad file | Resume + repair workflow | Tests resume: loads state → verifies → detects corruption → re-extracts ONLY corrupted file (not entire archive) |
| 15 | `test_filename_sanitization_verification` | Archive with normal filename | Files extracted and verified | Filename sanitization | Tests verification works with sanitized filenames (Windows reserved names) |
| 16 | `test_normalize_unicode_path_nfc` | NFD Unicode path (e + combining accent) | normalize_unicode_path() returns NFC form (é as single char) | Unicode normalization | Tests path normalization converts NFD → NFC for consistent comparison |
| 17 | `test_cyrillic_filenames` | ZIP with Cyrillic filenames (Russian/Ukrainian/Bulgarian) | Files extracted and verification succeeds | Cyrillic Unicode | Tests extraction + verification with Cyrillic characters (Израильские, Проводы Сергія, България) |
| 18 | `test_chinese_filenames` | ZIP with Chinese filenames | Files extracted and verification succeeds | Chinese Unicode | Tests extraction + verification with Chinese characters |
| 19 | `test_arabic_filenames` | ZIP with Arabic filenames | Files extracted and verification succeeds | Arabic Unicode | Tests extraction + verification with Arabic characters (RTL text) |
| 20 | `test_japanese_filenames` | ZIP with Japanese filenames | Files extracted and verification succeeds | Japanese Unicode | Tests extraction + verification with Japanese characters (Hiragana/Katakana/Kanji) |
| 21 | `test_korean_filenames` | ZIP with Korean filenames | Files extracted and verification succeeds | Korean Unicode | Tests extraction + verification with Korean characters (Hangul) |
| 22 | `test_mixed_unicode_languages` | ZIP with multiple languages in same archive | All files extracted and verification succeeds | Mixed Unicode | Tests extraction + verification with mixed language filenames |
| 23 | `test_unicode_normalization_forms` | ZIP with café (NFC) and naïve filenames | Files extracted and verification succeeds | NFC/NFD variants | Tests verification handles different Unicode normalization forms (é vs e+combining) |
| 24 | `test_emoji_in_filenames` | ZIP with emoji in filenames (📷, 🏖️, 👨‍👩‍👧‍👦) | Files extracted and verification succeeds | Emoji Unicode | Tests extraction + verification with emoji characters in paths |

---

## gphotos-321sync-media-scanner

### test_config.py (media-scanner)

Tests for scanner-specific configuration (3 tests).

**Rationale**: Tests ONLY scanner-specific parameters and their defaults/overrides. Common validation patterns (extra='forbid', dict/object input) are tested in gphotos-321sync-common.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_scanner_config_defaults` | No parameters | target_media_path="", batch_size=100, worker_threads>0, use_ffprobe=False, use_exiftool=False | Using defaults | Tests scanner-specific default values |
| 2 | `test_scanner_config_custom_values` | Scanner-specific parameters | Config with custom values | Parameters provided | Tests scanner-specific parameter overrides |
| 3 | `test_media_scanner_config_defaults` | No parameters | Root config with nested defaults | Using defaults | Tests root configuration structure with scanner defaults |

### test_path_utils.py (media-scanner)

Tests for media scanner path utilities (6 tests).

**Rationale**: Tests media-scanner specific file filtering (hidden/system/temp files).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_unix_hidden_files` | Files: .hidden, .DS_Store, .gitignore | is_hidden=True for all | Unix hidden files | Identifies files starting with . as hidden |
| 2 | `test_regular_files_not_hidden` | Files: photo.jpg, document.pdf | is_hidden=False for all | Normal files | Regular files not marked as hidden |
| 3 | `test_regular_files_should_scan` | Files: photo.jpg, video.mp4 | should_scan=True for all | Normal files | All regular media files should be scanned |
| 4 | `test_hidden_files_should_skip` | Files: .hidden, .DS_Store | should_scan=False for all | Hidden files | Skips Unix hidden files (system metadata) |
| 5 | `test_system_files_should_skip` | Files: Thumbs.db, desktop.ini, .DS_Store | should_scan=False for all | Windows/Mac system files | Skips system-generated files |
| 6 | `test_temp_files_should_skip` | Files: file.tmp, cache.cache, backup.bak | should_scan=False for all | Temporary file extensions | Skips temporary and backup files |

### test_database.py

Tests for database connection and DAL operations (8 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_database_connection` | Database path | Active connection, file created | Valid path | Tests SQLite connection creation |
| 2 | `test_database_pragmas` | Database connection | WAL mode, busy_timeout=5000ms | Connection established | Verifies SQLite pragmas |
| 3 | `test_migration_initial_schema` | Empty database (no schema_version table), run MigrationRunner | get_current_version() returns 1 after migration | First-time migration | Tests that MigrationRunner applies initial SQL schema (001_initial_schema.sql) and sets version to 1. Note: MigrationRunner runs on every app start but only applies pending migrations (idempotent). |
| 4 | `test_scan_run_dal` | Call ScanRunDAL methods | create_scan_run() → get_scan_run() → update_scan_run() → complete_scan_run() all succeed | Tests scan_runs table operations | Tests CRUD operations on scan_runs table: create new scan, retrieve by ID, update fields (files_processed), mark as completed with end_timestamp |
| 5 | `test_album_dal` | Call AlbumDAL methods with scan_run_id | insert_album() → get_album_by_path() → get_album_by_id() → update_album() all succeed | Tests albums table operations | Tests CRUD operations on albums table: insert album with path/title, retrieve by path or ID, update fields (description). Requires scan_run_id foreign key. |
| 6 | `test_media_item_dal` | Call MediaItemDAL methods with album_id + scan_run_id | insert_media_item() → get_media_item_by_path() → update_media_item() all succeed | Tests media_items table operations | Tests CRUD operations on media_items table: insert item with UUID/path/size/mime_type, retrieve by path or ID, update metadata (width/height). Requires album_id and scan_run_id foreign keys. |
| 7 | `test_processing_error_dal` | Call ProcessingErrorDAL methods with scan_run_id | insert_error() → get_errors_by_scan() → get_error_count() → get_error_summary() all succeed | Tests processing_errors table operations | Tests error tracking: insert error with type/category/message, retrieve all errors for scan, get total count, get summary grouped by category (e.g., {'corrupted': 1}) |
| 8 | `test_transaction_rollback` | Start transaction, insert valid row, insert into invalid_table (fails), catch exception | get_scan_run() returns None (first insert was rolled back) | Tests SQLite transaction rollback | Tests that when transaction fails (invalid SQL), all operations in that transaction are rolled back and no data persists |

### test_migrations.py

Tests for database migration system (17 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_initial_migration_creates_schema_version_table` | Empty database | schema_version table created | First migration | Creates version tracking table |
| 2 | `test_initial_migration_creates_all_tables` | Empty database | All required tables created | First migration | Creates complete schema |
| 3 | `test_get_current_version_on_empty_db` | Empty database | Version 0 | No migrations applied | Returns 0 for empty DB |
| 4 | `test_get_current_version_after_migration` | Database after migration | Version 1 | Migrations applied | Returns current version |
| 5 | `test_migration_idempotency` | Run migrations twice | Same version, tables intact | Multiple runs | Migrations are idempotent |
| 6 | `test_reapplying_migration_preserves_scan_runs` | Populated DB, re-migrate | Scan runs preserved | Data exists | Doesn't delete existing data |
| 7 | `test_reapplying_migration_preserves_albums` | Populated DB, re-migrate | Albums preserved | Data exists | Doesn't delete existing data |
| 8 | `test_reapplying_migration_preserves_media_items` | Populated DB, re-migrate | Media items preserved | Data exists | Doesn't delete existing data |
| 9 | `test_all_required_columns_exist_in_media_items` | Migrated database | All required columns present | After migration | Validates media_items schema |
| 10 | `test_all_required_columns_exist_in_albums` | Migrated database | All required columns present | After migration | Validates albums schema |
| 11 | `test_all_required_columns_exist_in_scan_runs` | Migrated database | All required columns present | After migration | Validates scan_runs schema |
| 12 | `test_indexes_created` | Migrated database | All required indexes present | After migration | Validates index creation |
| 13 | `test_migration_files_are_numbered` | Schema directory | Files follow naming convention | Migration files exist | Validates file naming |
| 14 | `test_migrations_applied_in_order` | Empty database | Migrations applied sequentially | Multiple migrations | Validates sequential application |
| 15 | `test_can_query_data_after_migration` | Populated DB, re-migrate | DAL queries work | After migration | Validates data accessibility |
| 16 | `test_can_insert_data_after_migration` | Populated DB, re-migrate | New data insertable | After migration | Validates write operations |
| 17 | `test_missing_schema_version_table_handled` | DB without schema_version | Version 0 detected, migrations applied | Incomplete DB | Handles missing version table |

### test_errors.py

Tests for error classification system (12 tests).

**Rationale**: When processing files, various errors can occur (permission denied, corrupted files, I/O errors, etc.). The `classify_error()` function categorizes exceptions into error categories (strings like "permission", "corrupted", "io", etc.) so they can be logged to the database's `scan_errors` table with consistent categorization. This enables error reporting/analysis (e.g., "show me all permission errors"). Tests validate that both custom exceptions (PermissionDeniedError, CorruptedFileError) and Python built-in exceptions (PermissionError, OSError, ValueError) are correctly mapped to categories.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_scanner_error_inherits_from_gpsync_error` | ScannerError instance | Is both ScannerError and GPSyncError | Error hierarchy | Tests inheritance chain: ScannerError → GPSyncError. Ensures all scanner errors inherit from common base error class for consistent error handling across packages. |
| 2 | `test_all_errors_inherit_from_scanner_error` | All specific error types (PermissionDeniedError, CorruptedFileError, IOError, ParseError, UnsupportedFormatError, ToolNotFoundError) | All inherit from ScannerError | Error hierarchy | Tests that ALL 6 specific error types inherit from ScannerError. Validates error hierarchy is correctly implemented. |
| 3 | `test_classify_permission_denied_error` | PermissionDeniedError("Access denied") | "permission" | Custom error type | Tests classify_error() maps custom PermissionDeniedError → "permission" category. Used when file access is denied during scan. |
| 4 | `test_classify_corrupted_file_error` | CorruptedFileError("File corrupted") | "corrupted" | Custom error type | Tests classify_error() maps CorruptedFileError → "corrupted" category. Used when file is unreadable/damaged. |
| 5 | `test_classify_io_error` | IOError("I/O failed") | "io" | Custom error type | Tests classify_error() maps custom IOError → "io" category. Used for general I/O failures. |
| 6 | `test_classify_parse_error` | ParseError("Parse failed") | "parse" | Custom error type | Tests classify_error() maps ParseError → "parse" category. Used when JSON/EXIF parsing fails. |
| 7 | `test_classify_unsupported_format_error` | UnsupportedFormatError("Format not supported") | "unsupported" | Custom error type | Tests classify_error() maps UnsupportedFormatError → "unsupported" category. Used for unknown/unsupported file formats. |
| 8 | `test_classify_tool_not_found_error` | ToolNotFoundError("Tool missing") | "tool_missing" | Custom error type | Tests classify_error() maps ToolNotFoundError → "tool_missing" category. Used when external tool (e.g., exiftool) is not installed. |
| 9 | `test_classify_builtin_permission_error` | Python's PermissionError("Access denied") | "permission" | Python built-in exception | Tests classify_error() handles Python's built-in PermissionError (raised by OS) → "permission" category. Ensures built-in exceptions are also categorized correctly. |
| 10 | `test_classify_builtin_os_error` | Python's OSError("OS error") | "io" | Python built-in exception | Tests classify_error() handles Python's built-in OSError → "io" category. OSError is raised for various OS-level I/O failures. |
| 11 | `test_classify_builtin_value_error` | Python's ValueError("Invalid value") | "parse" | Python built-in exception | Tests classify_error() handles Python's built-in ValueError → "parse" category. ValueError often occurs during data parsing/conversion. |
| 12 | `test_classify_unknown_error` | RuntimeError("Unknown error") | "unknown" | Unrecognized exception type | Tests classify_error() fallback: unrecognized exception types → "unknown" category. Ensures function never crashes, always returns a category. |

### test_tool_checker.py

Tests for tool availability checker (3 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_returns_dict` | No input | Dictionary returned | Tool checker called | Returns dict of tool availability |
| 2 | `test_checks_expected_tools` | No input | Dict with 'ffprobe' and 'exiftool' keys | Tool checker called | Checks expected tools |
| 3 | `test_returns_boolean_values` | No input | All values are booleans | Tool checker called | Returns boolean availability |

### test_tool_checker_integration.py

Integration tests for tool checker with config (4 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_disabled_tools_no_error` | use_ffprobe=False, use_exiftool=False | No error raised | Tools disabled | Disabled tools don't cause errors |
| 2 | `test_enabled_tool_available_no_error` | Enabled tool that's available | No error raised | Tool available | Available tools don't cause errors |
| 3 | `test_enabled_tool_missing_raises_error` | Enabled tool that's missing | ToolNotFoundError raised | Tool missing | Missing enabled tools raise error |
| 4 | `test_both_enabled_both_missing_raises_error` | Both tools enabled and missing | ToolNotFoundError raised | Both missing | Raises error for first missing tool |

### test_album_discovery.py

Tests for album discovery and metadata parsing (16 tests).

**Rationale**: Ensures albums are correctly discovered from Google Photos Takeout structure (top-level folders only, as Google Photos doesn't support nested albums), metadata is parsed from JSON files, and album IDs remain consistent across scans for proper tracking.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_parse_album_metadata_complete` | metadata.json with title, description, access, date | Dict with all parsed fields | Complete metadata.json | Parses all Google Photos album metadata fields correctly |
| 2 | `test_parse_album_metadata_minimal` | metadata.json with only {"title": "My Album"} | Dict with title="My Album", others None | Minimal metadata | Handles sparse metadata gracefully without errors |
| 3 | `test_parse_album_metadata_invalid_json` | File with content "not valid json{" | parse_album_metadata() raises ParseError with "Invalid JSON" message | Malformed JSON | Tests that parse_album_metadata() raises ParseError when JSON is syntactically invalid |
| 4 | `test_parse_album_metadata_missing_file` | Path to nonexistent.json file | parse_album_metadata() raises ParseError with "Failed to read" message | File doesn't exist | Tests that parse_album_metadata() raises ParseError when file path doesn't exist |
| 5 | `test_extract_year_from_folder_valid` | Folder name "Photos from 2023" | Integer 2023 | Valid year pattern (1900-2200) | Extracts year from Google Photos year-based album folders |
| 6 | `test_extract_year_from_folder_invalid` | "Photos", "Photos from 1899", "Photos from 2201" | None | No valid year pattern or out of range | Returns None for non-matching or invalid year patterns |
| 7 | `test_discover_albums_user_album` | Directory containing metadata.json | AlbumInfo with is_user_album=True, parsed metadata | Album has metadata.json | Discovers user-created albums (have metadata.json) |
| 8 | `test_discover_albums_year_based` | Folder "Photos from 2023" (no metadata.json) | AlbumInfo with is_user_album=False, year in title | Folder matches year pattern | Identifies Google Photos year-based albums |
| 9 | `test_discover_albums_regular_folder` | Regular folder "Vacation" (no metadata, no year) | AlbumInfo using folder name as title | Generic folder | Treats any top-level folder as potential album |
| 10 | `test_discover_albums_invalid_metadata` | Folder "Invalid Album" with malformed metadata.json | Album discovered with title="Invalid Album" (folder name), warning "Failed to parse album metadata" logged | Invalid metadata.json in folder | Tests that discover_albums() continues when metadata.json is invalid: uses folder name as title, logs warning, doesn't crash. Different from test #3 because this tests discover_albums() behavior (continues scanning), while test #3 tests parse_album_metadata() behavior (raises error). |
| 11 | `test_discover_albums_database_insertion` | Discovered albums + DB connection | Albums inserted into albums table | Valid DB connection | Verifies albums are persisted to database correctly |
| 12 | `test_discover_albums_album_id_generation` | Same album path in different scans | Identical album_ids (UUID5 based on path) | Deterministic ID generation | Ensures album IDs remain consistent across scans for tracking |
| 13 | `test_discover_albums_empty_directory` | target_media_path directory with no subdirectories | discover_albums() raises RuntimeError with "No albums discovered" | Empty directory - nothing to scan | Tests that discover_albums() fails when target_media_path has no albums: raises RuntimeError (app has nothing to do, should exit) |
| 14 | `test_discover_albums_nonexistent_path` | target_media_path pointing to non-existent directory | discover_albums() raises FileNotFoundError with "does not exist" | target_media_path doesn't exist | Tests that discover_albums() fails fast when target_media_path doesn't exist: raises FileNotFoundError immediately (app should not continue with invalid path) |
| 15 | `test_discover_albums_count` | Test fixture with 4 top-level folders | Exactly 4 albums discovered | Only top-level folders | Verifies only top-level folders are discovered (no recursion) |
| 16 | `test_discover_albums_update_existing` | Re-scan with new scan_run_id | Albums updated with new scan_run_id | Albums already in database | Updates existing albums rather than creating duplicates |

### test_discovery.py

Tests for file discovery functionality (14 tests).

**Rationale**: Ensures all media files are discovered correctly, JSON sidecars are paired with their media files, and hidden/system files are filtered out to avoid processing unwanted files.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_discover_files_basic` | Directory: "Photos/" with IMG_001.jpg, IMG_002.jpg | List of 2 FileInfo objects | Media files present | Discovers all non-hidden, non-system files |
| 2 | `test_discover_files_sidecar_pairing` | photo1.jpg + photo1.jpg.supplemental-metadata.json, video1.mp4 + video1.mp4.supplemental-metadata.json, photo2.png (no sidecar) | FileInfo with json_sidecar_path set for files with sidecars, None for others | Google Takeout sidecar patterns | Tests sidecar pairing. App supports Google Takeout patterns: 1) `filename.ext.supplemental-metadata.json` (standard), 2) `filename.ext.supplemental-me.json` (truncated), 3) `filename.ext.supplemental-metadat.json` (truncated), 4) `filename.ext.supplemental-metad.json` (truncated), 5) `filename.ext.json` (legacy). Test covers: files with sidecars (photo1.jpg, video1.mp4, photo4.heic) and files without (photo2.png, photo3.jpg, video2.mov). |
| 3 | `test_discover_files_relative_paths` | Root: "/media", File: "/media/Photos/2023/img.jpg" | FileInfo with relative_path="Photos/2023/img.jpg" | Files at various depths | Calculates correct relative paths from root |
| 4 | `test_discover_files_album_folder` | File: "Photos/Vacation/img.jpg" | FileInfo with album_folder_path="Photos/Vacation" | Files in subdirectories | Identifies immediate parent folder as album |
| 5 | `test_discover_files_excludes_json` | Directory with photo1.jpg.json, video1.mp4.json, metadata.json | discover_files() returns only media files, no .json files | JSON files present | Tests that JSON files are excluded from results (they're paired as sidecars or album metadata, not scanned as media files). Verifies no FileInfo has .json extension. |
| 6 | `test_discover_files_excludes_hidden` | Files: .hidden, .DS_Store, IMG_001.jpg | Only IMG_001.jpg in results | Hidden files present | Filters out Unix hidden files (starting with .) |
| 7 | `test_discover_files_empty_directory` | Empty directory (no files) | discover_files() returns empty list, warning "No media files discovered" logged | No files to discover | Tests that discover_files() handles empty directories gracefully: returns empty list, logs warning (folder exists but has no media - user should know). Unlike discover_albums which raises error, this just warns. |
| 8 | `test_discover_files_nonexistent_path` | Path: "/does/not/exist" | Empty list | Path doesn't exist | Handles missing paths gracefully |
| 9 | `test_discover_files_file_not_directory` | Path to file instead of directory | Empty list | Path is a file | Handles file paths gracefully |
| 10 | `test_discover_files_no_extension` | Files: "photo", "image" | Files discovered | Files lack extensions | Discovers extensionless files (MIME detection later) |
| 11 | `test_discover_files_wrong_extension` | File: "image.txt" (actually JPEG) | File discovered | Extension doesn't match content | Tests that discover_files() doesn't filter by extension - it discovers ALL files regardless of extension. MIME type detection happens LATER in the pipeline (during metadata extraction). This ensures misnamed files (e.g., JPEG with .txt extension) are still discovered and processed. |
| 12 | `test_discover_files_file_size` | Files with various sizes | FileInfo with correct file_size in bytes | Files exist | Captures file size from filesystem metadata |
| 13 | `test_discover_files_large_tree` | 10 albums × 5 files = 50 files | All 50 files discovered with sidecars paired | Large file set | Tests scalability of discovery algorithm |

### test_file_processor.py

Tests for file metadata extraction (14 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_calculate_crc32_different_files` | Two different files | Different CRC32 values | Different content | Tests our calculate_crc32() wrapper detects file differences. |
| 2 | `test_calculate_crc32_large_file` | File >64KB | Valid 8-char hex CRC32 | Large file | Tests chunked CRC32 |
| 3 | `test_process_file_cpu_work_success` | Image file | Dict with success=True, mime_type, crc32, fingerprint | Valid file | Performs all CPU operations |
| 4 | `test_process_file_cpu_work_mime_type` | Image file | MIME type detected | Valid file | Detects file MIME type |
| 5 | `test_process_file_cpu_work_crc32` | Text file | CRC32 from process_file_cpu_work() matches direct calculate_crc32() call | Valid file | Tests integration: calls process_file_cpu_work() and calculate_crc32() separately on same file, verifies both return identical CRC32. Ensures process_file_cpu_work() wrapper has no bugs. Note: calculate_crc32() is a wrapper in file_processor.py (not the compute_crc32() from fingerprint.py). |
| 6 | `test_process_file_cpu_work_fingerprint` | Text file | 64-char hex SHA-256 | Valid file | Calculates SHA-256 of first 64KB + last 64KB for files >128KB, or entire file if ≤128KB. |
| 7 | `test_process_file_cpu_work_exif_data` | Image file | Dict with exif_data (may be empty) | Valid image | Attempts EXIF extraction |
| 8 | `test_process_file_cpu_work_resolution` | Image file | Width and height fields | Valid image | Attempts resolution extraction |
| 9 | `test_process_file_cpu_work_video_data` | Non-video file | video_data=None | Image file | Returns None for non-video |
| 10 | `test_process_file_cpu_work_nonexistent_file` | Non-existent path | success=False, error fields | File doesn't exist | Handles missing files |
| 11 | `test_process_file_cpu_work_error_handling` | Invalid file data | Result with success/error, no exception | Invalid file | Catches all exceptions |
| 12 | `test_process_file_cpu_work_small_file` | File <128KB | CRC32 and fingerprint | Small file | Processes small files |
| 13 | `test_process_file_cpu_work_large_file` | File >128KB | CRC32 and fingerprint | Large file | Handles large files with chunking |
| 14 | `test_process_file_cpu_work_empty_file` | Empty file (0 bytes) | Result with success and crc32 | Empty file | Handles empty files |

### test_fingerprint.py

Tests for content fingerprinting utilities (3 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_change_detection` | File before/after modification | Different fingerprints | Content changed | Verifies fingerprint detects changes |
| 2 | `test_identical_files_same_fingerprint` | Two identical files | Same fingerprint | Identical content | Verifies identical files match |
| 3 | `test_large_file_crc32` | ~1MB file | Valid CRC32 | Large file | Tests CRC32 on large files |

### test_json_parser.py

Tests for JSON sidecar parser (10 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_parse_complete_json` | JSON with all fields | Dict with title, description, photoTakenTime, geoData, people | Complete JSON | Parses all Google Photos JSON fields |
| 2 | `test_parse_minimal_json` | JSON with only title | Dict with title only | Minimal JSON | Handles sparse JSON |
| 3 | `test_parse_timestamp_formats` | JSON with timestamp | ISO-formatted timestamp | Timestamp present | Converts timestamp to ISO |
| 4 | `test_parse_creation_time_fallback` | JSON with creationTime | creationTime parsed | photoTakenTime missing | Uses fallback timestamp field |
| 5 | `test_parse_geo_data_exif_fallback` | JSON with geoDataExif | geoData populated from geoDataExif | geoData missing | Uses fallback geo field |
| 6 | `test_parse_people_array` | JSON with people array | List of person names | People present | Extracts person names from array |
| 7 | `test_parse_invalid_json` | Malformed JSON | JSONDecodeError raised | Invalid JSON | Validates error handling |
| 8 | `test_parse_missing_file` | Non-existent file | FileNotFoundError raised | File doesn't exist | Validates error handling |
| 9 | `test_parse_empty_people_array` | JSON with empty people | Empty list | No people | Handles empty people array |
| 10 | `test_parse_partial_geo_data` | JSON with lat/lon only | geoData with lat/lon, no altitude | Partial geo data | Handles partial geo data |

### test_mime_detector.py

Tests for MIME type detection (7 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_jpeg_detection` | Temp file with JPEG magic bytes `\xff\xd8\xff\xe0\x00\x10JFIF` | detect_mime_type() returns "image/jpeg" | Valid JPEG header | Detects JPEG by reading first 8 bytes (magic bytes), NOT by file extension. Uses `filetype` library which reads file signatures. |
| 2 | `test_png_detection` | Temp file with PNG signature `\x89PNG\r\n\x1a\n` | detect_mime_type() returns "image/png" | Valid PNG header | Detects PNG by reading first 8 bytes (PNG signature), NOT by file extension. |
| 3 | `test_mp4_detection` | Temp file with MP4 ftyp box structure (24 bytes: size + 'ftyp' + 'mp42' + version + brands) | detect_mime_type() returns "video/mp4" | Valid MP4 ftyp box | Detects MP4 by reading ftyp box structure (ISO base media file format), NOT by file extension. |
| 4 | `test_unknown_extension` | Temp file with random data `b'random data'` and .xyz extension | detect_mime_type() returns "application/octet-stream" | Unknown file type | Returns default MIME type when `filetype` library cannot identify file signature. Handles unknown formats gracefully. |
| 5 | `test_case_insensitive_extension` | Temp file named `.JPG` (uppercase) with JPEG magic bytes | detect_mime_type() returns "image/jpeg" | Case variation in extension | Verifies detection works regardless of extension case (reads magic bytes, ignores extension). |
| 6 | `test_is_image_mime_type` | Strings: "image/jpeg", "image/png", "image/gif", "video/mp4", "application/pdf" | is_image_mime_type() returns True for "image/*", False for others | MIME type strings | Helper function that checks if MIME type starts with "image/". Used in extract_exif_smart() to route JPEG/PNG to Pillow vs RAW formats to ExifTool. NOT used for database insertion. |
| 7 | `test_is_video_mime_type` | Strings: "video/mp4", "video/quicktime", "video/x-matroska", "image/jpeg", "application/pdf" | is_video_mime_type() returns True for "video/*", False for others | MIME type strings | Helper function that checks if MIME type starts with "video/". Used for conditional video metadata extraction. NOT used for database insertion. |

### test_edited_variants.py

Tests for edited variant detection and linking (14 tests).

**Rationale**: Ensures edited photos (created by Google Photos editor with "-edited" suffix) are correctly linked to their originals, allowing users to track photo editing history and maintain relationships between versions.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_detects_edited_variant` | Files: IMG_1234.JPG, IMG_1234-edited.JPG | Mapping: {edited → original} | Both in same directory | Detects Google Photos `-edited` suffix pattern |
| 2 | `test_detects_multiple_variants` | 3 original/edited pairs | Mapping with 3 entries | Multiple pairs present | Detects all edited variants in directory |
| 3 | `test_requires_original_to_exist` | Only IMG_1234-edited.JPG (no original) | detect_edited_variants() returns empty dict | Original missing | Tests edited variant detection algorithm: 1) Loop through all files, 2) Check if filename contains `-edited`, 3) If YES, strip `-edited` to construct original filename, 4) Check if original EXISTS in file list, 5) If NO (this test case), skip - no mapping created. Algorithm validates original exists before creating relationship. |
| 4 | `test_requires_same_directory` | Original in "Photos/", edited in "Photos/Edited/" | Empty mapping | Different folders | Only links files in same directory (Google Photos behavior) |
| 5 | `test_ignores_non_edited_files` | IMG_1234.JPG, IMG_5678.JPG, IMG_9999.JPG (no -edited suffix) | detect_edited_variants() returns empty dict | No edited variants | Tests algorithm early-exit optimization: files WITHOUT `-edited` suffix are skipped immediately (step 2 of algorithm). Validates that regular files don't waste processing time. |
| 6 | `test_handles_nested_directories` | Photos/2023/January/IMG_1234.JPG + IMG_1234-edited.JPG, Photos/2023/February/IMG_5678.HEIC + IMG_5678-edited.HEIC | detect_edited_variants() returns 2 mappings | Nested directory structure | Tests that detection works at any directory depth within albums. Both pairs detected correctly regardless of nesting level. Note: Google Photos doesn't support nested albums, but files within an album can be in subdirectories (e.g., Photos from 2023/January/). |
| 7 | `test_empty_file_list` | Empty list [] | detect_edited_variants() returns empty dict {} | No files | Tests robustness: detect_edited_variants([]) handles empty input gracefully without errors. Edge case for when scan finds no files whatsoever. |
| 8 | `test_links_variant_to_original` | DB with IMG_1234.JPG (id=uuid1) and IMG_1234-edited.JPG (id=uuid2) | link_edited_variants() updates edited item's original_media_item_id=uuid1 in DB | Both files in database | Tests database linking: reads mapping {edited → original}, finds both in media_items table, updates edited item's original_media_item_id field. Same as detection but persisted in DB. |
| 9 | `test_links_multiple_variants` | DB with 3 original/edited pairs (IMG_0.JPG + IMG_0-edited.JPG, IMG_1.JPG + IMG_1-edited.JPG, IMG_2.JPG + IMG_2-edited.JPG) | link_edited_variants() updates all 3 edited items with correct original_media_item_id | Multiple pairs in database | Tests batch linking: all 3 edited variants correctly linked to their originals in single operation. Same as detection but persisted in DB for multiple files. |
| 10 | `test_handles_missing_original` | DB has IMG_1234-edited.JPG but NOT IMG_1234.JPG, mapping says edited → original | link_edited_variants() returns stats: {variants_linked=0, originals_found=0, originals_missing=1} | Original not in database | Tests failure case: mapping exists but original not in DB. App logs warning, increments originals_missing counter, doesn't crash. Edited item's original_media_item_id remains NULL. |
| 11 | `test_handles_missing_edited_variant` | DB has IMG_1234.JPG but NOT IMG_1234-edited.JPG, mapping says edited → original | link_edited_variants() returns stats: {variants_linked=0, originals_found=1, originals_missing=0} | Edited variant not in database | Tests edge case: mapping exists, original found in DB, but edited variant not in DB (maybe filtered out during scan). App logs warning, increments originals_found, doesn't update anything. |
| 12 | `test_end_to_end_detection_and_linking` | DB with files, full workflow | Variants detected and linked in DB | Complete workflow | Tests entire detection and linking pipeline |
| 13 | `test_no_variants_found` | DB with IMG_1234.JPG, IMG_5678.JPG (no -edited files) | detect_and_link_edited_variants() returns stats: {variants_linked=0, originals_found=0, originals_missing=0} | No edited variants in scan | Tests the happy path: when no edited variants exist (most common case - users don't edit many photos), the workflow completes successfully with zero stats. Validates algorithm doesn't fail/warn when there's simply no work to do. |
| 14 | `test_multiple_variants_in_different_albums` | Album 0: IMG_1234.JPG + IMG_1234-edited.JPG, Album 1: IMG_1234.JPG + IMG_1234-edited.JPG (same filename, different albums) | detect_and_link_edited_variants() links both pairs correctly (2 variants linked) | Same filename in different albums | Tests that variants are only linked within the same directory (album folder). Algorithm checks `path.parent` to ensure edited file and original are in same folder. Files with same name in different albums are NOT linked to each other - each album's pair is independent. Both pairs linked correctly to their respective originals. |

### test_exif_extractor.py

Tests for EXIF metadata extraction (8 tests).

**Note on format coverage**: GIF and WebP formats are untested but expected to work via the same fallback mechanism (PIL's `.size` property) validated by PNG test. If comprehensive format coverage is needed, consider adding dedicated tests for GIF (especially animated GIFs with frames) and WebP.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_extract_resolution` | Image file (800×600) | Tuple (800, 600) | Valid image | Extracts dimensions using PIL |
| 2 | `test_extract_resolution_with_exif` | Image with EXIF (1920×1080) | Tuple (1920, 1080) | Image has EXIF | Extracts resolution from EXIF image |
| 3 | `test_extract_resolution_missing_file` | Non-existent file path | None | File doesn't exist | Returns None on error |
| 4 | `test_extract_exif_no_data` | JPEG without EXIF | Empty/minimal dictionary | No EXIF present | Tests fallback behavior when EXIF is absent (regardless of format). Uses JPEG created without EXIF data. Returns empty dict gracefully. |
| 5 | `test_extract_exif_with_data` | Image with camera EXIF | Dict with camera_make, model, orientation | EXIF data present | Extracts and parses EXIF fields |
| 6 | `test_extract_exif_missing_file` | Non-existent file path | Empty dictionary | File doesn't exist | Returns empty dict on error |
| 7 | `test_extract_exif_invalid_file` | File with garbage data | Empty dictionary | Invalid image data | Handles corrupted files |
| 8 | `test_resolution_extraction_png` | PNG file (640×480) | Tuple (640, 480) | PNG format (no EXIF) | Tests resolution extraction for PNG format specifically. While `test_extract_exif_no_data` already tests JPEG without EXIF (fallback behavior), this test validates that PIL's `.size` property works correctly for PNG's different decoder/format. Ensures format-specific bugs don't break resolution extraction. Real-world: Google Photos exports contain PNGs (screenshots). Note: JPEG/HEIC have EXIF; PNG/GIF/WebP don't; videos use different standards. |

### test_exif_extractor_integration.py

Integration tests for EXIF extraction (10 tests).

**Rationale**: These tests use **PIL (Pillow)** library to create real images with actual EXIF data, then verify extraction works correctly. Unlike unit tests which may use mocks, integration tests validate the entire extraction pipeline with real image formats. All tests use PIL's simple API (no advanced libraries like exiftool).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_extract_camera_info` | Image with Canon EOS EXIF | Dict with camera_make, camera_model | Complete camera EXIF | Extracts camera information. |
| 2 | `test_extract_timestamps` | Image with datetime EXIF | ISO-formatted timestamp strings | EXIF timestamps present | Converts EXIF datetime to ISO format. |
| 3 | `test_extract_exposure_settings` | Image with exposure EXIF | Dict with iso, f_number, focal_length, exposure_time | Exposure EXIF present | Extracts exposure settings. |
| 4 | `test_extract_exif_orientation` | Image with orientation=6 (rotated 90°) | Dict with orientation=6 | EXIF orientation present | Extracts EXIF orientation value (1-8). Orientation indicates how camera was held: 1=normal (0°), 3=upside-down (180°), 6=rotated 90° CCW, 8=rotated 90° CW. Values 2,4,5,7 are mirrored versions. Needed to display photos correctly - if orientation is 6 or 8, width/height must be swapped. |
| 5 | `test_extract_gps_coordinates` | Image with GPS EXIF | Dict with latitude, longitude | GPS data present | Extracts GPS location from EXIF. GPS stored as degrees/minutes/seconds rationals, converted to decimal degrees. |
| 6 | `test_gps_coordinate_conversion` | Image with N/W GPS | Positive lat, negative lon | GPS with N/W references | Tests GPS sign conversion: N=positive lat, S=negative lat, E=positive lon, W=negative lon. |
| 7 | `test_extract_resolution_from_real_image` | Real image (1920×1080) | Tuple (1920, 1080) | Valid image | Extracts resolution from real image. |
| 8 | `test_extract_from_png` | PNG file | Resolution extracted, EXIF empty | PNG format | Handles PNG files (no EXIF). |
| 9 | `test_extract_from_image_without_exif` | Image with no EXIF | Empty EXIF dict, resolution works | No EXIF present | Handles images without EXIF gracefully. |
| 10 | `test_rational_value_parsing` | Image with rational EXIF (28/10, 50/1) | Float values (2.8, 50.0) | Rational EXIF values | Converts EXIF rational values (fractions) to floats. |

### test_exif_extractor_raw_integration.py

Integration tests for RAW format EXIF extraction with ExifTool (5 tests).

**Rationale**: Tests ExifTool integration for RAW camera formats (CR2, NEF, ARW, DNG) that Pillow cannot read. Tests are skipped if ExifTool is not installed.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_extract_exif_with_exiftool_cr2` | Mock CR2 file | Dict with metadata | ExifTool available | Tests extract_exif_with_exiftool() with RAW file |
| 2 | `test_extract_exif_smart_with_raw_file` | Mock CR2 file, use_exiftool=True | Dict with metadata | ExifTool available | Tests extract_exif_smart() invokes ExifTool for RAW formats |
| 3 | `test_extract_exif_smart_raw_without_exiftool_flag` | Mock CR2 file, use_exiftool=False | Empty dict | ExifTool available but disabled | Tests that ExifTool is NOT invoked when flag is False |
| 4 | `test_extract_raises_error_when_exiftool_not_available` | CR2 file | FileNotFoundError | ExifTool NOT available | Tests graceful error when ExifTool missing |
| 5 | `test_extract_smart_raw_without_exiftool_returns_empty` | CR2 file, use_exiftool=True | Empty dict | ExifTool NOT available | Tests fallback when ExifTool unavailable |

### test_video_extractor_integration.py

Integration tests for video metadata extraction (7 tests, requires ffprobe).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_extract_video_metadata_real_file` | Real video file | Dict with width, height, duration, frame_rate | ffprobe available | Extracts metadata from real video |
| 2 | `test_extract_video_resolution` | Video file (640×480) | width=640, height=480 | ffprobe available | Extracts video resolution |
| 3 | `test_extract_video_duration` | 2-second video | duration ≈ 2 seconds | ffprobe available | Extracts video duration |
| 4 | `test_extract_video_frame_rate` | 30fps video | frame_rate ≈ 30 | ffprobe available | Extracts frame rate |
| 5 | `test_extract_from_missing_file` | Non-existent file | CalledProcessError raised | ffprobe available | Handles missing files |
| 6 | `test_is_video_file_mime_types` | Various MIME types | True for video types | MIME strings | Identifies video MIME types |
| 7 | `test_extract_raises_error_when_ffprobe_not_available` | Video file, no ffprobe | FileNotFoundError raised | ffprobe not available | Handles missing ffprobe |

### test_live_photos.py

Tests for Live Photos detection and linking (15 tests).

**Rationale**: Ensures Apple Live Photos (photo + video pairs with same base name) are correctly detected and linked in the database, so users can identify which MOV files are Live Photo components rather than standalone videos.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_detects_heic_mov_pair` | Files: IMG_1234.HEIC, IMG_1234.MOV | Pair detected | Both in same directory | Detects HEIC+MOV Live Photo (iPhone default) |
| 2 | `test_detects_jpg_mov_pair` | Files: IMG_5678.JPG, IMG_5678.MOV | Pair detected | Both in same directory | Detects JPG+MOV Live Photo (compatibility mode) |
| 3 | `test_detects_jpeg_mov_pair` | Files: IMG_9999.jpeg, IMG_9999.mov | Pair detected | Both in same directory | Detects JPEG+MOV Live Photo (case variations) |
| 4 | `test_ignores_unpaired_files` | Files: IMG_1234.HEIC, IMG_5678.MOV | No pairs | Different base names | Ignores unpaired files (standalone photo/video) |
| 5 | `test_detects_multiple_pairs` | 3 HEIC+MOV pairs in directory | 3 pairs detected | Multiple pairs | Detects all Live Photo pairs in directory |
| 6 | `test_requires_same_directory` | IMG_1234.HEIC in "Photos/", IMG_1234.MOV in "Videos/" | No pairs | Different folders | Only pairs files in same directory (Apple behavior) |
| 7 | `test_requires_same_base_name` | IMG_1234.HEIC + IMG_5678.MOV | No pairs | Names don't match | Requires exact base name match (IMG_1234) |
| 8 | `test_ignores_non_media_files` | HEIC, MOV, JSON, PDF files | Only media pairs detected | Non-media present | Ignores non-media files like JSON sidecars |
| 9 | `test_case_insensitive_extensions` | IMG_1234.heic + IMG_1234.mov (lowercase) | Pair detected | Case-insensitive | Extension matching is case-insensitive (.HEIC = .heic) |
| 10 | `test_empty_file_list` | Empty list | No pairs | No files | Handles empty input without errors |
| 11 | `test_links_pair_in_database` | DB with HEIC+MOV media items | live_photo_pair_id set on both items | Both in database | Links Live Photo pair with shared UUID in DB |
| 12 | `test_links_multiple_pairs` | DB with 3 HEIC+MOV pairs | All 3 pairs linked with unique pair_ids | Multiple pairs | Batch links all pairs efficiently |
| 13 | `test_links_by_path_when_no_media_item_id` | FileInfo without media_item_id field | Pairs linked by path lookup in DB | No media_item_id | Links using path-based database lookup |
| 14 | `test_end_to_end_detection_and_linking` | DB with files, full workflow | Pairs detected and linked in DB | Complete workflow | Tests entire detection and linking pipeline |
| 15 | `test_no_pairs_found` | Only regular photos (no Live Photos) | Stats: pairs_linked=0 | No Live Photos | Handles case with no Live Photos gracefully |

### test_metadata_coordinator.py

Tests for metadata coordination and MediaItemRecord creation (14 tests).

**Rationale**: The coordinator combines data from multiple sources (FileInfo from discovery, metadata extraction results, JSON sidecars) into a single `MediaItemRecord` ready for database insertion. Tests validate that all data sources are correctly merged and edge cases (missing data, parse errors) are handled.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_coordinate_metadata_basic` | FileInfo (path, size, mtime), metadata_ext (MIME, CRC32), album_id, scan_run_id | MediaItemRecord with all basic fields populated | Valid inputs from all sources | Creates complete media item record by merging FileInfo + metadata_ext + IDs |
| 2 | `test_coordinate_metadata_cpu_data` | FileInfo, metadata_ext with MIME/CRC32/fingerprint/width/height | Record with mime_type='image/jpeg', crc32='a1b2c3d4', fingerprint='fff...', width=1920, height=1080 | Metadata extraction completed successfully | Verifies metadata extraction results (MIME detection, checksums, dimensions) are correctly copied into record |
| 3 | `test_coordinate_metadata_exif_data` | FileInfo, metadata_ext with exif_data dict (camera_make, camera_model, GPS, timestamps) | Record with exif_datetime_original, exif_camera_make='Canon', exif_gps_latitude=37.7749, etc. | EXIF extraction succeeded | Extracts specific EXIF fields from nested dict into flat record fields (datetime_original, camera_make, camera_model, lens_make, lens_model, focal_length, aperture, iso, GPS) |
| 4 | `test_coordinate_metadata_with_json_sidecar` | FileInfo with json_sidecar_path pointing to valid .json file | Record with title, description, people tags, geo_data from JSON | JSON sidecar exists and is valid | Calls parse_google_photos_json() to extract Google Takeout metadata (title, description, photoTakenTime, geoData, people) and merges into record |
| 5 | `test_coordinate_metadata_json_parse_error` | FileInfo with json_sidecar_path pointing to malformed JSON file | Record created WITHOUT JSON metadata, no exception raised | JSON file is corrupted/invalid | Catches JSONDecodeError, logs warning, continues without JSON data (graceful degradation) |
| 6 | `test_coordinate_metadata_video_data` | FileInfo, metadata_ext with video_data dict (duration=120.5, frame_rate=30.0) | Record with duration_seconds=120.5, frame_rate=30.0 | Video metadata extraction succeeded (ffprobe) | Extracts video-specific fields (duration, frame_rate) from metadata_ext into record |
| 7 | `test_coordinate_metadata_no_video_data` | FileInfo, metadata_ext with video_data=None (image file) | Record with duration_seconds=None, frame_rate=None | File is an image, not a video | Handles non-video files by setting video fields to None (no error) |
| 8 | `test_coordinate_metadata_minimal_cpu_result` | FileInfo, metadata_ext with only success=True, mime_type, crc32, fingerprint (no dimensions, no EXIF) | Record created with mime_type, width=None, height=None, exif fields=None | Metadata extraction succeeded but extracted minimal data | Handles sparse metadata_ext without crashing (missing optional fields default to None) |
| 9 | `test_media_item_record_to_dict` | MediaItemRecord object | Dictionary with all record fields as key-value pairs | Record is valid | Tests .to_dict() method for database insertion (converts dataclass to dict) |
| 10 | `test_media_item_record_has_media_item_id` | MediaItemRecord created from inputs | Record has media_item_id field with 36-character UUID string | ID generation enabled | Verifies UUID is generated and formatted correctly (UUID5 based on path+size+mtime) |
| 11 | `test_media_item_record_deterministic_ids` | Call coordinate_metadata() TWICE with identical FileInfo, metadata_ext, album_id, scan_run_id | Both calls return records with SAME media_item_id | UUID5 is deterministic (not random) | Verifies IDs are reproducible (same inputs → same UUID). Critical for idempotent re-scans. If someone changes UUID5 to UUID4 (random), this test catches it. |
| 12 | `test_coordinate_metadata_all_exif_fields` | FileInfo, metadata_ext with exif_data containing ALL possible EXIF fields (datetime_original, datetime_digitized, camera, lens, focal_length, aperture, iso, exposure_time, orientation, GPS) | Record with ALL exif_* fields populated correctly | Complete EXIF data available | Validates coordinator doesn't miss any EXIF fields during extraction (regression test for completeness) |
| 13 | `test_coordinate_metadata_with_exiftool` | FileInfo, metadata_ext with use_exiftool=True | Record with exif_data populated from ExifTool | ExifTool available | Tests ExifTool integration for RAW formats |
| 14 | `test_coordinate_metadata_with_exiftool_error` | FileInfo, metadata_ext with use_exiftool=True, ExifTool returns error | Record created without ExifTool data, no exception raised | ExifTool error | Catches ExifTool errors, logs warning, continues without ExifTool data |

### test_metadata_aggregator.py

Tests for metadata aggregation from multiple sources (13 tests).

**Rationale**: Ensures metadata from different sources (JSON sidecars, EXIF, video data, filenames) is correctly combined with proper precedence, so the most reliable data (JSON from Google Photos) takes priority.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_aggregates_exif_timestamp` | EXIF has timestamp "2023-01-01T12:00:00+00:00", no JSON, no filename timestamp | Result has capture_timestamp from EXIF | Only EXIF source available | Tests that EXIF timestamp CAN be used when it's the only source available |
| 2 | `test_aggregates_json_timestamp` | JSON has timestamp "2023-02-01T14:00:00+00:00", no EXIF, no filename timestamp | Result has capture_timestamp from JSON | Only JSON source available | Tests that JSON timestamp CAN be used when it's the only source available |
| 3 | `test_aggregates_filename_timestamp` | Filename "IMG_20230315_100000.jpg", no EXIF, no JSON | Result has capture_timestamp parsed from filename | Only filename source available | Tests that filename timestamp CAN be parsed when it's the only source available |
| 4 | `test_timestamp_priority_exif_over_json` | EXIF has "2023-01-01T12:00:00+00:00", JSON has "2023-02-01T14:00:00+00:00" | Result uses EXIF timestamp "2023-01-01T12:00:00+00:00" | Both EXIF and JSON present | Tests PRIORITY RULE: when both EXIF and JSON exist, EXIF wins (camera timestamp more reliable than Google's metadata) |
| 5 | `test_timestamp_priority_json_over_filename` | JSON has "2023-02-01T14:00:00+00:00", filename has "IMG_20230315_100000.jpg" | Result uses JSON timestamp "2023-02-01T14:00:00+00:00" | Both JSON and filename present | Tests PRIORITY RULE: when both JSON and filename exist, JSON wins (Google metadata more reliable than filename parsing) |
| 6 | `test_aggregates_geo_data_from_exif` | EXIF has GPS (lat=37.7749, lon=-122.4194), no JSON geo | Result has geo_data from EXIF | Only EXIF GPS available | Tests that EXIF GPS CAN be used when it's the only source |
| 7 | `test_aggregates_geo_data_from_json` | JSON has GPS (lat=40.7128, lon=-74.0060), no EXIF GPS | Result has geo_data from JSON | Only JSON GPS available | Tests that JSON GPS CAN be used when it's the only source |
| 8 | `test_parse_timestamp_from_filename_img_pattern` | Filename: "IMG_20210615_143022.jpg" | "2021-06-15T14:30:22+00:00" (UTC timezone-aware) | IMG_YYYYMMDD_HHMMSS pattern | Parses IMG prefix pattern from Android camera phones, returns ISO format with UTC timezone |
| 9 | `test_parse_timestamp_from_filename_vid_pattern` | Filename: "VID_20210615_143022.mp4" | "2021-06-15T14:30:22+00:00" (UTC timezone-aware) | VID_YYYYMMDD_HHMMSS pattern | Parses VID prefix pattern from Android camera phones, returns ISO format with UTC timezone |
| 10 | `test_parse_timestamp_from_filename_simple_pattern` | Filename: "20210615_143022.jpg" | "2021-06-15T14:30:22+00:00" (UTC timezone-aware) | YYYYMMDD_HHMMSS pattern | Parses simple timestamp pattern without prefix, returns ISO format with UTC timezone |
| 11 | `test_parse_timestamp_from_filename_date_only` | Filename: "2021-06-15.jpg" | "2021-06-15T00:00:00+00:00" (UTC timezone-aware) | YYYY-MM-DD pattern | Parses date-only pattern, sets time to midnight UTC |
| 12 | `test_parse_timestamp_from_filename_no_match` | Filename: "random_photo.jpg" | None | No recognizable pattern | Returns None for unparseable filenames without crashing (graceful fallback) |
| 13 | `test_dimensions_video_priority` | Video file with dimensions in both EXIF (1920×1080) and video metadata (1280×720) | Result uses video metadata dimensions (1280×720) | Both sources present | Tests that video metadata dimensions are more accurate than EXIF for videos (EXIF may be from thumbnail) |

### test_post_scan.py

Tests for post-scan validation and cleanup (9 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_marks_inconsistent_files` | Old scan files with old timestamps | Files marked inconsistent | Files from previous scan | Detects timestamp inconsistencies |
| 2 | `test_marks_missing_files` | Old scan files not in new scan | Files marked missing | Files not re-scanned | Marks files as missing |
| 3 | `test_marks_missing_albums` | Old scan albums not in new scan | Albums marked missing | Albums not re-scanned | Marks albums as missing |
| 4 | `test_validation_statistics` | Scan with various file states | Correct statistics returned | Mixed file states | Calculates validation stats |
| 5 | `test_no_changes_when_all_valid` | All files valid | No status changes | Valid scan | Doesn't modify valid data |
| 6 | `test_keeps_recent_scans` | 5 scans, keep 3 | 2 scans deleted | Cleanup with retention | Keeps most recent scans |
| 7 | `test_deletes_old_errors` | 3 scans with errors, keep 1 | 2 scans + 2 errors deleted | Cleanup with errors | Deletes errors from old scans |
| 8 | `test_no_cleanup_when_under_limit` | 3 scans, keep 10 | Nothing deleted | Under retention limit | Doesn't delete when under limit |
| 9 | `test_preserves_media_items` | Old scan with media items | Media items preserved | Cleanup doesn't affect media | Media items not deleted |

### test_progress.py

Tests for progress tracker (14 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_initialization` | total_files=1000, log_interval=50 | Tracker initialized | Constructor parameters | Initializes progress tracker |
| 2 | `test_update` | Update to 25 | files_processed=25 | Progress update | Updates progress counter |
| 3 | `test_increment` | Increment by 1, then 5 | files_processed=6 | Incremental updates | Increments progress |
| 4 | `test_get_progress_initial` | No progress | 0% complete, 100 remaining | Initial state | Returns initial progress |
| 5 | `test_get_progress_halfway` | 50 of 100 processed | 50% complete, 50 remaining | Halfway through | Returns halfway progress |
| 6 | `test_get_progress_complete` | 100 of 100 processed | 100% complete, 0 remaining | Complete | Returns completion progress |
| 7 | `test_rate_calculation` | 10 files in 0.1s | ~100 files/sec | Time elapsed | Calculates processing rate |
| 8 | `test_eta_calculation` | 50 of 100 processed | ETA > 0 | Halfway through | Calculates estimated time |
| 9 | `test_eta_at_completion` | 100 of 100 processed | ETA = 0 | Complete | ETA is 0 when done |
| 10 | `test_format_time_seconds` | 0-59 seconds | "Xs" format | Seconds only | Formats seconds |
| 11 | `test_format_time_minutes` | 60-3599 seconds | "Xm Ys" format | Minutes + seconds | Formats minutes |
| 12 | `test_format_time_hours` | ≥3600 seconds | "Xh Ym Zs" format | Hours + minutes + seconds | Formats hours |
| 13 | `test_zero_total_files` | total_files=0 | 0%, 0 remaining | Edge case | Handles zero files |
| 14 | `test_log_interval_triggering` | Updates at intervals | Logs at specified intervals | Logging enabled | Logs at intervals |

### test_queue_manager.py

Tests for queue manager (10 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_initialization` | maxsize parameters | QueueManager initialized | Constructor parameters | Initializes queue manager |
| 2 | `test_create_queues` | Create queues | Work and results queues created | Queue creation | Creates Queue objects |
| 3 | `test_get_work_queue_depth_empty` | Empty work queue | Depth = 0 | Empty queue | Returns 0 for empty |
| 4 | `test_get_work_queue_depth_with_items` | Queue with 3 items | Depth = 3 | Items in queue | Returns correct depth |
| 5 | `test_get_results_queue_depth_empty` | Empty results queue | Depth = 0 | Empty queue | Returns 0 for empty |
| 6 | `test_get_results_queue_depth_with_items` | Queue with 2 items | Depth = 2 | Items in queue | Returns correct depth |
| 7 | `test_get_queue_stats` | Queues with items | Stats dict with depths and maxsizes | Queues exist | Returns queue statistics |
| 8 | `test_get_queue_depth_before_creation` | Before queue creation | Depth = 0 | Queues not created | Returns 0 before creation |
| 9 | `test_shutdown` | Shutdown call | Queues set to None | Queues exist | Cleans up queues |
| 10 | `test_backpressure_work_queue` | Fill queue to max | Queue.Full exception | Queue at capacity | Tests backpressure |

### test_summary.py

Tests for scan summary generation (13 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_basic_summary_structure` | Scan run ID | Summary with all required sections | Valid scan | Returns complete summary structure |
| 2 | `test_scan_run_metadata` | Scan run ID | Metadata with ID, status, timestamps | Valid scan | Includes scan run metadata |
| 3 | `test_discovery_statistics` | Scan run ID | Discovery stats (total, media, metadata files) | Valid scan | Includes discovery statistics |
| 4 | `test_processing_statistics` | Scan run ID | Processing stats (new, unchanged, changed, etc.) | Valid scan | Includes processing statistics |
| 5 | `test_album_statistics` | Scan run ID | Album stats (total, present, missing) | Valid scan | Includes album statistics |
| 6 | `test_file_status_breakdown` | Scan run ID | File status counts | Valid scan | Breaks down file statuses |
| 7 | `test_error_breakdown` | Scan run ID | Error counts by type and category | Valid scan | Breaks down errors |
| 8 | `test_performance_metrics` | Scan run ID | Duration and files/sec | Valid scan | Includes performance metrics |
| 9 | `test_nonexistent_scan_run` | Invalid scan ID | ValueError raised | Scan doesn't exist | Validates scan existence |
| 10 | `test_empty_scan_run` | Empty scan | Summary with zeros | No files processed | Handles empty scans |
| 11 | `test_formats_basic_summary` | Summary dict | Human-readable text | Valid summary | Formats as readable text |
| 12 | `test_includes_scan_run_id` | Summary dict | Scan ID in formatted text | Valid summary | Includes scan ID |
| 13 | `test_formats_errors_section` | Summary with errors | Error details in text | Errors present | Formats error section |

### test_worker_thread.py

Tests for worker thread processing (10 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_successful_processing` | FileInfo, mock process pool | Result with media_item type | Valid file | Processes file successfully |
| 2 | `test_cpu_error_handling` | FileInfo, metadata extraction error result | Result with error type | Metadata extraction fails | Handles extraction errors |
| 3 | `test_processes_single_item` | Work queue with 1 item | 1 result in results queue | Worker thread running | Processes single work item |
| 4 | `test_handles_processing_error` | Work item causing exception | Error result in queue | Exception raised | Catches and records errors |
| 5 | `test_shutdown_event` | Shutdown event set | Thread exits immediately | Shutdown requested | Respects shutdown event |
| 6 | `test_processes_multiple_items` | Work queue with 3 items | 3 results in queue | Worker thread running | Processes multiple items |
| 7 | `test_task_done_called` | Work item processed | task_done called on queue | Worker thread running | Marks tasks as done |
| 8 | `test_batch_processing` | Batch of 5 items | All 5 processed | Batch worker running | Processes items in batches |
| 9 | `test_batch_with_errors` | Batch with some errors | Mixed success/error results | Batch worker running | Handles errors in batch |
| 10 | `test_partial_batch` | 2 items, batch size 10 | Both items processed | Batch worker running | Handles partial batches |

### test_writer_thread.py

Tests for writer thread database operations (7 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_writes_media_items` | Results queue with 3 media items | 3 items in database | Writer thread running | Writes media items to DB |
| 2 | `test_writes_errors` | Results queue with 2 errors | 2 errors in database | Writer thread running | Writes errors to DB |
| 3 | `test_batch_writing` | 10 items, batch size 3 | All 10 items written | Writer thread running | Writes in batches |
| 4 | `test_mixed_results` | Mix of media items and errors | Both types written | Writer thread running | Handles mixed result types |
| 5 | `test_shutdown_event` | Shutdown event set | Thread exits quickly | Shutdown requested | Respects shutdown event |
| 6 | `test_empty_queue` | Empty results queue | No items written | Writer thread running | Handles empty queue |
| 7 | `test_write_batch_empty` | Empty batch | No error raised | Batch write function | Handles empty batch |
