# Test Suite Documentation

Comprehensive documentation of all test suites in the gphotos-321sync project.

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

---

## gphotos-321sync-takeout-extractor

### test_config.py (takeout-extractor)

Tests for extractor-specific configuration (3 tests).

**Rationale**: Tests ONLY extractor-specific parameters and their defaults/overrides. Common validation patterns (extra='forbid', dict/object input) are tested in gphotos-321sync-common.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_extraction_config_defaults` | No parameters | source_dir=".", target_media_path="./extracted", verify_checksums=True, max_retry_attempts=10 | Using defaults | Tests extractor-specific default values |
| 2 | `test_extraction_config_custom_values` | Extractor-specific parameters | Config with custom values | Parameters provided | Tests extractor-specific parameter overrides |
| 3 | `test_takeout_extractor_config_defaults` | No parameters | Root config with nested defaults | Using defaults | Tests root configuration structure with extractor defaults |

### test_extractor.py

Tests for archive extraction functionality (17 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_discover_archives` | Directory with ZIP and TAR.GZ | 2 archives discovered | Archives present | Discovers archives by extension |
| 2 | `test_discover_no_archives` | Empty directory | Empty list | No archives | Handles empty directory |
| 3 | `test_discover_recursive` | Nested directory with archive | Archive found recursively | Recursive=True | Discovers archives in subdirectories |
| 4 | `test_invalid_source_dir` | Non-existent directory | FileNotFoundError raised | Invalid path | Validates source directory |
| 5 | `test_source_is_file` | Path to file | NotADirectoryError raised | Path is file | Validates source is directory |
| 6 | `test_extract_zip` | ZIP archive | Files extracted to target | Valid ZIP | Extracts ZIP archive |
| 7 | `test_extract_tar_gz` | TAR.GZ archive | Files extracted to target | Valid TAR.GZ | Extracts TAR.GZ archive |
| 8 | `test_extract_with_progress` | Archive with progress callback | Progress callbacks invoked | Callback provided | Reports extraction progress |
| 9 | `test_extract_all` | Multiple archives | All archives extracted | Multiple archives | Extracts all archives |
| 10 | `test_preserve_structure` | Archive with preserve_structure flag | Structure preserved or flattened | Flag setting | Respects preserve_structure option |
| 11 | `test_run` | Source dir with archives | All archives extracted | Valid setup | Complete extraction workflow |
| 12 | `test_run_with_progress` | Extraction with progress callback | Progress callbacks invoked | Callback provided | Reports overall progress |
| 13 | `test_run_no_archives` | Empty source directory | Empty results | No archives | Handles no archives gracefully |
| 14 | `test_state_save_and_load` | Extraction state | State saved and loaded | State file used | Persists extraction state |
| 15 | `test_resume_extraction` | Interrupted extraction | Extraction resumes | State file exists | Resumes from saved state |
| 16 | `test_retry_on_transient_failure` | Flaky operation | Operation succeeds after retries | Transient failures | Retries with exponential backoff |
| 17 | `test_retry_gives_up_after_max_attempts` | Always-failing operation | RuntimeError after max attempts | Persistent failure | Gives up after max retries |

### test_extractor_verification.py

Tests for archive verification and selective re-extraction (27 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_all_files_missing` | Archive, no extracted files | all_valid=False, all files in bad_files | Files not extracted | Detects all missing files |
| 2 | `test_some_files_missing` | Archive, some files deleted | all_valid=False, missing files in bad_files | Some files deleted | Detects specific missing files |
| 3 | `test_one_file_missing` | Archive, one file deleted | all_valid=False, 1 file in bad_files | One file deleted | Detects single missing file |
| 4 | `test_file_size_mismatch_smaller` | Archive, file truncated | all_valid=False, file in bad_files | File truncated | Detects size mismatch |
| 5 | `test_file_size_mismatch_larger` | Archive, file appended | all_valid=False, file in bad_files | File enlarged | Detects size mismatch |
| 6 | `test_file_crc32_mismatch` | Archive, file content changed | all_valid=False, file in bad_files | Content corrupted | Detects CRC32 mismatch |
| 7 | `test_missing_and_corrupted_files` | Archive, mixed issues | all_valid=False, issues detected | Mixed corruption | Detects multiple issue types |
| 8 | `test_first_file_corrupted` | Archive, first file corrupted | all_valid=False, file in bad_files | First file bad | Detects corruption in first file |
| 9 | `test_last_file_corrupted` | Archive, last file corrupted | all_valid=False, file in bad_files | Last file bad | Detects corruption in last file |
| 10 | `test_multiple_scattered_corrupted_files` | Archive, multiple files corrupted | all_valid=False, all bad files listed | Multiple corruptions | Collects all corrupted files |
| 11 | `test_reextract_single_corrupted_file` | Archive, 1 corrupted file | File re-extracted, all_valid=True | Selective re-extraction | Re-extracts only corrupted file |
| 12 | `test_reextract_multiple_files` | Archive, multiple corrupted files | Files re-extracted, all_valid=True | Selective re-extraction | Re-extracts multiple files |
| 13 | `test_resume_with_completed_archive_verified` | Completed extraction, resume | Archive verified and skipped | State shows completed | Verifies and skips completed archives |
| 14 | `test_resume_with_corrupted_file_reextracts` | Completed extraction, file corrupted | Corrupted file re-extracted | Corruption detected on resume | Detects and fixes corruption on resume |
| 15 | `test_corrupted_zip_file_fails` | Corrupted ZIP file | BadZipFile or RuntimeError raised | Invalid ZIP | Handles corrupted archives |
| 16 | `test_empty_zip_file` | Empty ZIP archive | Extraction succeeds, no files | Empty archive | Handles empty archives |
| 17 | `test_filename_sanitization_verification` | Archive with special filenames | Files extracted and verified | Filename sanitization | Handles sanitized filenames |
| 18 | `test_normalize_unicode_path_nfc` | NFD Unicode path | NFC normalized path | Unicode normalization | Normalizes to NFC form |
| 19 | `test_cyrillic_filenames` | Archive with Cyrillic names | Files extracted and verified | Cyrillic characters | Handles Cyrillic filenames |
| 20 | `test_chinese_filenames` | Archive with Chinese names | Files extracted and verified | Chinese characters | Handles Chinese filenames |
| 21 | `test_arabic_filenames` | Archive with Arabic names | Files extracted and verified | Arabic characters | Handles Arabic filenames |
| 22 | `test_japanese_filenames` | Archive with Japanese names | Files extracted and verified | Japanese characters | Handles Japanese filenames |
| 23 | `test_korean_filenames` | Archive with Korean names | Files extracted and verified | Korean characters | Handles Korean filenames |
| 24 | `test_mixed_unicode_languages` | Archive with mixed languages | All files extracted and verified | Multiple languages | Handles mixed Unicode |
| 25 | `test_unicode_normalization_forms` | Archive with NFC/NFD variants | Files extracted and verified | Different normalization forms | Handles normalization variants |
| 26 | `test_emoji_in_filenames` | Archive with emoji names | Files extracted and verified | Emoji characters | Handles emoji in filenames |

---

## gphotos-321sync-media-scanner

### test_album_discovery.py

Tests for album discovery and metadata parsing (17 tests).

**Rationale**: Ensures albums are correctly discovered from Google Photos Takeout structure (top-level folders only, as Google Photos doesn't support nested albums), metadata is parsed from JSON files, and album IDs remain consistent across scans for proper tracking.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_parse_album_metadata_complete` | metadata.json with title, description, access, date | Dict with all parsed fields | Complete metadata.json | Parses all Google Photos album metadata fields correctly |
| 2 | `test_parse_album_metadata_minimal` | metadata.json with only {"title": "My Album"} | Dict with title="My Album", others None | Minimal metadata | Handles sparse metadata gracefully without errors |
| 3 | `test_parse_album_metadata_invalid_json` | Malformed JSON file (syntax error) | ParseError raised | Invalid JSON syntax | Validates error handling for corrupted metadata files |
| 4 | `test_parse_album_metadata_missing_file` | Path to non-existent metadata.json | ParseError raised | File doesn't exist | Validates error handling for missing metadata files |
| 5 | `test_extract_year_from_folder_valid` | Folder name "Photos from 2023" | Integer 2023 | Valid year pattern (1900-2200) | Extracts year from Google Photos year-based album folders |
| 6 | `test_extract_year_from_folder_invalid` | "Photos", "Photos from 1899", "Photos from 2201" | None | No valid year pattern or out of range | Returns None for non-matching or invalid year patterns |
| 7 | `test_discover_albums_user_album` | Directory containing metadata.json | AlbumInfo with is_user_album=True, parsed metadata | Album has metadata.json | Discovers user-created albums (have metadata.json) |
| 8 | `test_discover_albums_year_based` | Folder "Photos from 2023" (no metadata.json) | AlbumInfo with is_user_album=False, year in title | Folder matches year pattern | Identifies Google Photos year-based albums |
| 9 | `test_discover_albums_regular_folder` | Regular folder "Vacation" (no metadata, no year) | AlbumInfo using folder name as title | Generic folder | Treats any top-level folder as potential album |
| 10 | `test_discover_albums_invalid_metadata` | Album with corrupted metadata.json | AlbumInfo using folder name as fallback, warning logged | Invalid JSON in metadata | Gracefully handles metadata parsing errors, logs warning, uses folder name |
| 11 | `test_discover_albums_database_insertion` | Discovered albums + DB connection | Albums inserted into albums table | Valid DB connection | Verifies albums are persisted to database correctly |
| 12 | `test_discover_albums_album_id_generation` | Same album path in different scans | Identical album_ids (UUID5 based on path) | Deterministic ID generation | Ensures album IDs remain consistent across scans for tracking |
| 13 | `test_discover_albums_empty_directory` | Empty directory (no folders) | Empty list, warning logged | No folders to discover | Handles empty directories without errors, logs warning |
| 14 | `test_discover_albums_nonexistent_path` | Path that doesn't exist | Empty list, warning logged | Invalid path | Handles missing paths gracefully without crashing, logs warning |
| 15 | `test_discover_albums_count` | Test fixture with 4 top-level folders | Exactly 4 albums discovered | Only top-level folders | Verifies only top-level folders are discovered (no recursion) |
| 16 | `test_discover_albums_update_existing` | Re-scan with new scan_run_id | Albums updated with new scan_run_id | Albums already in database | Updates existing albums rather than creating duplicates |

### test_config.py (media-scanner)

Tests for scanner-specific configuration (3 tests).

**Rationale**: Tests ONLY scanner-specific parameters and their defaults/overrides. Common validation patterns (extra='forbid', dict/object input) are tested in gphotos-321sync-common.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_scanner_config_defaults` | No parameters | target_media_path="", batch_size=100, worker_threads>0, use_ffprobe=False, use_exiftool=False | Using defaults | Tests scanner-specific default values |
| 2 | `test_scanner_config_custom_values` | Scanner-specific parameters | Config with custom values | Parameters provided | Tests scanner-specific parameter overrides |
| 3 | `test_media_scanner_config_defaults` | No parameters | Root config with nested defaults | Using defaults | Tests root configuration structure with scanner defaults |

### test_database.py

Tests for database connection and DAL operations (8 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_database_connection` | Database path | Active connection, file created | Valid path | Tests SQLite connection creation |
| 2 | `test_database_pragmas` | Database connection | WAL mode, busy_timeout=5000ms | Connection established | Verifies SQLite pragmas |
| 3 | `test_migration_initial_schema` | Empty database | Schema version 1 | First-time migration | Tests initial schema migration |
| 4 | `test_scan_run_dal` | Database connection | CRUD operations succeed | Valid database | Tests scan run DAL |
| 5 | `test_album_dal` | DB + scan_run_id | Album CRUD operations | Valid DB and scan | Tests album DAL |
| 6 | `test_media_item_dal` | DB + album_id + scan_run_id | Media item CRUD operations | Valid DB, album, scan | Tests media item DAL |
| 7 | `test_processing_error_dal` | DB + scan_run_id | Error tracking operations | Valid DB and scan | Tests error DAL |
| 8 | `test_transaction_rollback` | Transaction with error | No data persisted | Transaction fails | Validates rollback behavior |

### test_discovery.py

Tests for file discovery functionality (14 tests).

**Rationale**: Ensures all media files are discovered correctly, JSON sidecars are paired with their media files, and hidden/system files are filtered out to avoid processing unwanted files.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_discover_files_basic` | Directory: "Photos/" with IMG_001.jpg, IMG_002.jpg | List of 2 FileInfo objects | Media files present | Discovers all non-hidden, non-system files |
| 2 | `test_discover_files_sidecar_pairing` | IMG_001.jpg + IMG_001.jpg.json | FileInfo with json_sidecar_path=Path("IMG_001.jpg.json") | JSON files match media names | Pairs JSON sidecars with corresponding media files |
| 3 | `test_discover_files_relative_paths` | Root: "/media", File: "/media/Photos/2023/img.jpg" | FileInfo with relative_path="Photos/2023/img.jpg" | Files at various depths | Calculates correct relative paths from root |
| 4 | `test_discover_files_album_folder` | File: "Photos/Vacation/img.jpg" | FileInfo with album_folder_path="Photos/Vacation" | Files in subdirectories | Identifies immediate parent folder as album |
| 5 | `test_discover_files_excludes_json` | Directory with .json files | JSON files not in results | JSON files present | Filters out JSON metadata files (processed separately) |
| 6 | `test_discover_files_excludes_hidden` | Files: .hidden, .DS_Store, IMG_001.jpg | Only IMG_001.jpg in results | Hidden files present | Filters out Unix hidden files (starting with .) |
| 7 | `test_discover_files_empty_directory` | Empty directory | Empty list | No files | Handles empty directories without errors |
| 8 | `test_discover_files_nonexistent_path` | Path: "/does/not/exist" | Empty list | Path doesn't exist | Handles missing paths gracefully |
| 9 | `test_discover_files_file_not_directory` | Path to file instead of directory | Empty list | Path is a file | Handles file paths gracefully |
| 10 | `test_discover_files_no_extension` | Files: "photo", "image" | Files discovered | Files lack extensions | Discovers extensionless files (MIME detection later) |
| 11 | `test_discover_files_wrong_extension` | File: "image.txt" (actually JPEG) | File discovered | Extension doesn't match content | Discovers all files, relies on MIME detection |
| 12 | `test_discover_files_file_size` | Files with various sizes | FileInfo with correct file_size in bytes | Files exist | Captures file size from filesystem metadata |
| 13 | `test_discover_files_large_tree` | 10 albums × 5 files = 50 files | All 50 files discovered with sidecars paired | Large file set | Tests scalability of discovery algorithm |

### test_edited_variants.py

Tests for edited variant detection and linking (17 tests).

**Rationale**: Ensures edited photos (created by Google Photos editor with "-edited" suffix) are correctly linked to their originals, allowing users to track photo editing history and maintain relationships between versions.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_detects_edited_variant` | Files: IMG_1234.JPG, IMG_1234-edited.JPG | Mapping: {edited → original} | Both in same directory | Detects Google Photos `-edited` suffix pattern |
| 2 | `test_detects_multiple_variants` | 3 original/edited pairs | Mapping with 3 entries | Multiple pairs present | Detects all edited variants in directory |
| 3 | `test_requires_original_to_exist` | Only IMG_1234-edited.JPG (no original) | Empty mapping | Original missing | Requires original file to establish relationship |
| 4 | `test_requires_same_directory` | Original in "Photos/", edited in "Photos/Edited/" | Empty mapping | Different folders | Only links files in same directory (Google Photos behavior) |
| 5 | `test_requires_same_extension` | IMG_1234.JPG + IMG_1234-edited.PNG | Empty mapping | Different extensions | Requires matching extensions (same file type) |
| 6 | `test_ignores_non_edited_files` | Regular files without "-edited" | Empty mapping | No `-edited` suffix | Only processes files matching edited pattern |
| 7 | `test_handles_nested_directories` | Variants in "Photos/2023/", "Photos/2024/" | Mappings for all nested pairs | Files at various depths | Processes all directories recursively |
| 8 | `test_empty_file_list` | Empty list | Empty mapping | No files | Handles empty input without errors |
| 9 | `test_multiple_edits_of_same_original` | IMG.JPG, IMG-edited.JPG, IMG-edited-edited.JPG | Chain: IMG-edited-edited → IMG-edited → IMG | Multiple edit generations | Links each edited version to its immediate predecessor |
| 10 | `test_links_variant_to_original` | DB with original + edited items | original_media_item_id field populated | Both in database | Updates database to link edited photo to original |
| 11 | `test_links_multiple_variants` | DB with 3 original/edited pairs | All 3 pairs linked in DB | Multiple pairs | Batch links all variants efficiently |
| 12 | `test_handles_missing_original` | Edited in DB, original not in DB | Stats: originals_missing=1 | Original not in DB | Tracks failures when original not found |
| 13 | `test_handles_missing_edited_variant` | Original in DB, edited not in DB | Original found, variant not updated | Edited not in DB | Handles case where edited file wasn't scanned |
| 14 | `test_end_to_end_detection_and_linking` | DB with files, full workflow | Variants detected and linked in DB | Complete workflow | Tests entire detection and linking pipeline |
| 15 | `test_no_variants_found` | Only regular files (no edited variants) | Stats: variants_linked=0 | No edited variants | Handles case with no variants gracefully |
| 16 | `test_multiple_variants_in_different_albums` | Variants in "Vacation/", "Family/" albums | All variants linked correctly | Variants in different albums | Processes each album independently |

### test_errors.py

Tests for error classification system (12 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_scanner_error_inherits_from_gpsync_error` | ScannerError instance | Is both ScannerError and GPSyncError | Error hierarchy | Validates inheritance chain |
| 2 | `test_all_errors_inherit_from_scanner_error` | All specific error types | All inherit from ScannerError | Error hierarchy | Validates all errors follow hierarchy |
| 3 | `test_classify_permission_denied_error` | PermissionDeniedError | "permission" | Specific error type | Maps error to category string |
| 4 | `test_classify_corrupted_file_error` | CorruptedFileError | "corrupted" | Specific error type | Maps error to category string |
| 5 | `test_classify_io_error` | IOError | "io" | Specific error type | Maps error to category string |
| 6 | `test_classify_parse_error` | ParseError | "parse" | Specific error type | Maps error to category string |
| 7 | `test_classify_unsupported_format_error` | UnsupportedFormatError | "unsupported" | Specific error type | Maps error to category string |
| 8 | `test_classify_tool_not_found_error` | ToolNotFoundError | "tool_missing" | Specific error type | Maps error to category string |
| 9 | `test_classify_builtin_permission_error` | Built-in PermissionError | "permission" | Python built-in | Handles built-in exceptions |
| 10 | `test_classify_builtin_os_error` | Built-in OSError | "io" | Python built-in | Handles built-in exceptions |
| 11 | `test_classify_builtin_value_error` | Built-in ValueError | "parse" | Python built-in | Handles built-in exceptions |
| 12 | `test_classify_unknown_error` | RuntimeError (unknown) | "unknown" | Unrecognized type | Provides fallback classification |

### test_exif_extractor.py

Tests for EXIF metadata extraction (8 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_extract_resolution` | Image file (800×600) | Tuple (800, 600) | Valid image | Extracts dimensions using PIL |
| 2 | `test_extract_resolution_with_exif` | Image with EXIF (1920×1080) | Tuple (1920, 1080) | Image has EXIF | Extracts resolution from EXIF image |
| 3 | `test_extract_resolution_missing_file` | Non-existent file path | None | File doesn't exist | Returns None on error |
| 4 | `test_extract_exif_no_data` | Image without EXIF | Empty/minimal dictionary | No EXIF present | Returns empty dict |
| 5 | `test_extract_exif_with_data` | Image with camera EXIF | Dict with camera_make, model, orientation | EXIF data present | Extracts and parses EXIF fields |
| 6 | `test_extract_exif_missing_file` | Non-existent file path | Empty dictionary | File doesn't exist | Returns empty dict on error |
| 7 | `test_extract_exif_invalid_file` | File with garbage data | Empty dictionary | Invalid image data | Handles corrupted files |
| 8 | `test_resolution_extraction_png` | PNG file (640×480) | Tuple (640, 480) | PNG format | Extracts resolution from PNG |

### test_exif_extractor_integration.py

Integration tests for EXIF extraction (10 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_extract_camera_info` | Image with Canon EOS EXIF | Dict with camera_make, camera_model | Complete camera EXIF | Extracts camera information |
| 2 | `test_extract_timestamps` | Image with datetime EXIF | ISO-formatted timestamp strings | EXIF timestamps present | Converts EXIF datetime to ISO |
| 3 | `test_extract_exposure_settings` | Image with exposure EXIF | Dict with iso, f_number, focal_length, exposure_time | Exposure EXIF present | Extracts exposure settings |
| 4 | `test_extract_orientation` | Image with orientation EXIF | Orientation value (1-8) | Orientation tag present | Extracts image orientation |
| 5 | `test_extract_gps_coordinates` | Image with GPS EXIF | Decimal lat, lon, altitude | GPS EXIF present | Converts GPS rationals to decimal |
| 6 | `test_gps_coordinate_conversion` | Image with N/W GPS | Positive lat, negative lon | GPS with N/W references | Applies correct signs |
| 7 | `test_extract_resolution_from_real_image` | Real image (1920×1080) | Tuple (1920, 1080) | Valid image | Extracts resolution from real image |
| 8 | `test_extract_from_png` | PNG file | Resolution extracted, EXIF empty | PNG format | Handles PNG files |
| 9 | `test_extract_from_image_without_exif` | Image with no EXIF | Empty EXIF dict, resolution works | No EXIF present | Handles images without EXIF |
| 10 | `test_rational_value_parsing` | Image with rational EXIF (28/10, 50/1) | Float values (2.8, 50.0) | Rational EXIF values | Converts rationals to floats |

### test_file_processor.py

Tests for CPU-intensive file processing (19 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_calculate_crc32_deterministic` | Same file read twice | Identical 8-char hex CRC32 | File unchanged | Verifies CRC32 is deterministic |
| 2 | `test_calculate_crc32_different_files` | Two different files | Different CRC32 values | Different content | Verifies CRC32 detects differences |
| 3 | `test_calculate_crc32_large_file` | File >64KB | Valid 8-char hex CRC32 | Large file | Tests chunked CRC32 |
| 4 | `test_process_file_cpu_work_success` | Valid image file | Dict with success=True, mime_type, crc32, fingerprint | Valid file | Performs all CPU operations |
| 5 | `test_process_file_cpu_work_mime_type` | Image file | MIME type detected | Valid file | Detects file MIME type |
| 6 | `test_process_file_cpu_work_crc32` | Text file | CRC32 matches direct calculation | Valid file | Verifies CRC32 calculation |
| 7 | `test_process_file_cpu_work_fingerprint` | Text file | 64-char hex SHA-256 | Valid file | Calculates content fingerprint |
| 8 | `test_process_file_cpu_work_exif_data` | Image file | Dict with exif_data (may be empty) | Valid image | Attempts EXIF extraction |
| 9 | `test_process_file_cpu_work_resolution` | Image file | Width and height fields | Valid image | Attempts resolution extraction |
| 10 | `test_process_file_cpu_work_video_data` | Non-video file | video_data=None | Image file | Returns None for non-video |
| 11 | `test_process_file_cpu_work_nonexistent_file` | Non-existent path | success=False, error fields | File doesn't exist | Handles missing files |
| 12 | `test_process_file_cpu_work_error_handling` | Invalid file data | Result with success/error, no exception | Invalid file | Catches all exceptions |
| 13 | `test_process_file_cpu_work_use_exiftool_flag` | File with use_exiftool flag | Success with flag respected | Flag parameter | Accepts exiftool flag |
| 14 | `test_process_file_cpu_work_use_ffprobe_flag` | File with use_ffprobe flag | Success with flag respected | Flag parameter | Accepts ffprobe flag |
| 15 | `test_process_file_cpu_work_small_file` | File <128KB | CRC32 and fingerprint | Small file | Processes small files |
| 16 | `test_process_file_cpu_work_large_file` | File >128KB | CRC32 and fingerprint | Large file | Handles large files with chunking |
| 17 | `test_process_file_cpu_work_empty_file` | Empty file (0 bytes) | Result with success and crc32 | Empty file | Handles empty files |

### test_fingerprint.py

Tests for content fingerprinting utilities (8 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_small_file` | File <16KB | 64-char hex SHA-256 | Small file | Computes SHA-256 of entire file |
| 2 | `test_large_file` | File >16KB | 64-char hex SHA-256 | Large file | Computes SHA-256 with chunking |
| 3 | `test_change_detection` | File before/after modification | Different fingerprints | Content changed | Verifies fingerprint detects changes |
| 4 | `test_identical_files_same_fingerprint` | Two identical files | Same fingerprint | Identical content | Verifies identical files match |
| 5 | `test_crc32_computation` | File content | 32-bit unsigned integer | Valid file | Tests basic CRC32 |
| 6 | `test_crc32_consistency` | Same content twice | Identical CRC32 | Same content | Verifies CRC32 consistency |

### test_imports.py

Basic import tests (5 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_common_import` | Import common module | Successful import | Dependencies installed | Verifies common package imports |
| 2 | `test_pillow_import` | Import PIL.Image | Successful import | Pillow installed | Verifies Pillow available |
| 3 | `test_filetype_import` | Import filetype | Successful import | filetype installed | Verifies filetype available |
| 4 | `test_platformdirs_import` | Import platformdirs | Successful import | platformdirs installed | Verifies platformdirs available |
| 5 | `test_media_scanner_import` | Import media_scanner | Successful import | Package installed | Verifies media_scanner imports |

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

### test_live_photos.py

Tests for Live Photos detection and linking (17 tests).

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
| 11 | `test_pairs_in_nested_directories` | Pairs in "Photos/2023/", "Photos/2024/" | All pairs detected | Files at various depths | Processes all directories recursively |
| 12 | `test_links_pair_in_database` | DB with HEIC+MOV media items | live_photo_pair_id set on both items | Both in database | Links Live Photo pair with shared UUID in DB |
| 13 | `test_links_multiple_pairs` | DB with 3 HEIC+MOV pairs | All 3 pairs linked with unique pair_ids | Multiple pairs | Batch links all pairs efficiently |
| 14 | `test_links_by_path_when_no_media_item_id` | FileInfo without media_item_id field | Pairs linked by path lookup in DB | No media_item_id | Links using path-based database lookup |
| 15 | `test_end_to_end_detection_and_linking` | DB with files, full workflow | Pairs detected and linked in DB | Complete workflow | Tests entire detection and linking pipeline |
| 16 | `test_no_pairs_found` | Only regular photos (no Live Photos) | Stats: pairs_linked=0 | No Live Photos | Handles case with no Live Photos gracefully |

### test_metadata_aggregator.py

Tests for metadata aggregation from multiple sources (13 tests).

**Rationale**: Ensures metadata from different sources (JSON sidecars, EXIF, video data, filenames) is correctly combined with proper precedence, so the most reliable data (JSON from Google Photos) takes priority.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_aggregate_metadata_all_sources` | Path: "IMG_20210101_120000.jpg", JSON (title, GPS), EXIF (camera, GPS), video data | Aggregated dict: JSON GPS used, EXIF camera kept, video dimensions | All sources present | Combines metadata with precedence: JSON > EXIF > video > filename |
| 2 | `test_aggregate_metadata_json_only` | Path + JSON metadata (title, description, timestamp) | Dict with JSON fields only | Only JSON present | Handles single source without errors |
| 3 | `test_aggregate_metadata_exif_only` | Path + EXIF metadata (camera, GPS) | Dict with EXIF fields + title from filename | Only EXIF present | Handles EXIF-only case, falls back to filename for title |
| 4 | `test_aggregate_metadata_no_sources` | Path: "vacation.jpg", no metadata | Dict with title="vacation" from filename | No metadata sources | Handles no metadata gracefully, extracts title from filename |
| 5 | `test_timestamp_precedence` | JSON timestamp, EXIF timestamp, filename timestamp | JSON timestamp used in result | Multiple timestamp sources | Validates precedence: JSON > EXIF > filename for timestamps |
| 6 | `test_gps_precedence` | JSON GPS (37.7749, -122.4194), EXIF GPS (40.7128, -74.0060) | JSON GPS used, EXIF GPS stored separately | Multiple GPS sources | JSON GPS takes precedence, EXIF GPS preserved in separate fields |
| 7 | `test_parse_timestamp_from_filename_img_pattern` | Filename: "IMG_20210615_143022.jpg" | "2021-06-15T14:30:22" | IMG_YYYYMMDD_HHMMSS pattern | Parses IMG prefix pattern from camera phones |
| 8 | `test_parse_timestamp_from_filename_vid_pattern` | Filename: "VID_20210615_143022.mp4" | "2021-06-15T14:30:22" | VID_YYYYMMDD_HHMMSS pattern | Parses VID prefix pattern from camera phones |
| 9 | `test_parse_timestamp_from_filename_simple_pattern` | Filename: "20210615_143022.jpg" | "2021-06-15T14:30:22" | YYYYMMDD_HHMMSS pattern | Parses simple timestamp pattern without prefix |
| 10 | `test_parse_timestamp_from_filename_date_only` | Filename: "2021-06-15.jpg" | "2021-06-15T00:00:00" | YYYY-MM-DD pattern | Parses date-only pattern, sets time to midnight |
| 11 | `test_parse_timestamp_from_filename_no_match` | Filename: "random_photo.jpg" | None | No recognizable pattern | Returns None for unparseable filenames without crashing |

### test_metadata_coordinator.py

Tests for metadata coordination and MediaItemRecord creation (14 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_coordinate_metadata_basic` | FileInfo, CPU result, album_id, scan_run_id | MediaItemRecord with basic fields | Valid inputs | Creates basic media item record |
| 2 | `test_coordinate_metadata_cpu_data` | FileInfo, CPU result | Record with MIME, CRC32, fingerprint, dimensions | CPU data present | Includes CPU processing results |
| 3 | `test_coordinate_metadata_exif_data` | FileInfo, CPU result with EXIF | Record with EXIF fields | EXIF present | Extracts EXIF data into record |
| 4 | `test_coordinate_metadata_with_json_sidecar` | FileInfo with JSON sidecar | Record with JSON metadata | JSON sidecar present | Parses and includes JSON metadata |
| 5 | `test_coordinate_metadata_json_parse_error` | FileInfo with invalid JSON | Record without JSON metadata | Invalid JSON | Handles JSON parse errors gracefully |
| 6 | `test_coordinate_metadata_video_data` | FileInfo, CPU result with video data | Record with duration, frame_rate | Video data present | Includes video metadata |
| 7 | `test_coordinate_metadata_no_video_data` | FileInfo, CPU result without video | Record with duration=None, frame_rate=None | Image file | Handles non-video files |
| 8 | `test_coordinate_metadata_minimal_cpu_result` | FileInfo, minimal CPU result | Record with minimal data | Sparse CPU result | Handles minimal CPU data |
| 9 | `test_media_item_record_to_dict` | MediaItemRecord | Dictionary representation | Valid record | Converts record to dict |
| 10 | `test_media_item_record_has_media_item_id` | MediaItemRecord | Record with 36-char UUID | ID generated | Generates media_item_id |
| 11 | `test_media_item_record_deterministic_ids` | Same inputs twice | Identical media_item_ids | UUID5 generation | IDs are deterministic |

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

### test_mime_detector.py

Tests for MIME type detection (7 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_jpeg_detection` | File with JPEG header | "image/jpeg" | Valid JPEG | Detects JPEG by magic bytes |
| 2 | `test_png_detection` | File with PNG signature | "image/png" | Valid PNG | Detects PNG by magic bytes |
| 3 | `test_mp4_detection` | File with MP4 ftyp box | "video/mp4" | Valid MP4 | Detects MP4 by ftyp box |
| 4 | `test_unknown_extension` | File with .xyz extension | "application/octet-stream" | Unknown type | Returns default MIME type |
| 5 | `test_case_insensitive_extension` | File with .JPG (uppercase) | "image/jpeg" | Case variation | Extension matching is case-insensitive |
| 6 | `test_is_image_mime_type` | Various MIME types | True for images, False otherwise | MIME type strings | Identifies image MIME types |
| 7 | `test_is_video_mime_type` | Various MIME types | True for videos, False otherwise | MIME type strings | Identifies video MIME types |

### test_path_utils.py

Tests for path utilities (9 tests).

**Rationale**: Ensures paths are normalized consistently across platforms (Windows/Unix) and Unicode forms, and that hidden/system/temp files are correctly filtered to avoid processing unwanted files.

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_forward_slashes` | Path: "Photos\\2023\\image.jpg" (Windows) | "Photos/2023/image.jpg" | Windows backslashes | Converts backslashes to forward slashes for cross-platform consistency |
| 2 | `test_unicode_normalization` | Path: "café" (NFD: cafe\u0301) | "café" (NFC: caf\u00e9) | Decomposed Unicode | Normalizes to NFC form for consistent string comparison |
| 3 | `test_relative_path` | Path: "Photos/2023/image.jpg" | "Photos/2023/image.jpg" (normalized) | Relative path | Handles relative paths correctly |
| 4 | `test_unix_hidden_files` | Files: .hidden, .DS_Store, .gitignore | is_hidden=True for all | Unix hidden files | Identifies files starting with . as hidden |
| 5 | `test_regular_files_not_hidden` | Files: photo.jpg, document.pdf | is_hidden=False for all | Normal files | Regular files not marked as hidden |
| 6 | `test_regular_files_should_scan` | Files: photo.jpg, video.mp4 | should_scan=True for all | Normal files | All regular media files should be scanned |
| 7 | `test_hidden_files_should_skip` | Files: .hidden, .DS_Store | should_scan=False for all | Hidden files | Skips Unix hidden files (system metadata) |
| 8 | `test_system_files_should_skip` | Files: Thumbs.db, desktop.ini, .DS_Store | should_scan=False for all | Windows/Mac system files | Skips system-generated files |
| 9 | `test_temp_files_should_skip` | Files: file.tmp, cache.cache, backup.bak | should_scan=False for all | Temporary file extensions | Skips temporary and backup files |

### test_post_scan.py

Tests for post-scan validation and cleanup (10 tests).

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

Tests for progress tracker (17 tests).

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

Tests for queue manager (12 tests).

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

Tests for scan summary generation (17 tests).

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

### test_video_extractor_integration.py

Integration tests for video metadata extraction (8 tests, requires ffprobe).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_extract_video_metadata_real_file` | Real video file | Dict with width, height, duration, frame_rate | ffprobe available | Extracts metadata from real video |
| 2 | `test_extract_video_resolution` | Video file (640×480) | width=640, height=480 | ffprobe available | Extracts video resolution |
| 3 | `test_extract_video_duration` | 2-second video | duration ≈ 2 seconds | ffprobe available | Extracts video duration |
| 4 | `test_extract_video_frame_rate` | 30fps video | frame_rate ≈ 30 | ffprobe available | Extracts frame rate |
| 5 | `test_extract_from_missing_file` | Non-existent file | CalledProcessError raised | ffprobe available | Handles missing files |
| 6 | `test_is_video_file_mime_types` | Various MIME types | True for video types | MIME strings | Identifies video MIME types |
| 7 | `test_extract_raises_error_when_ffprobe_not_available` | Video file, no ffprobe | FileNotFoundError raised | ffprobe not available | Handles missing ffprobe |

### test_worker_thread.py

Tests for worker thread processing (10 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_successful_processing` | FileInfo, mock process pool | Result with media_item type | Valid file | Processes file successfully |
| 2 | `test_cpu_error_handling` | FileInfo, CPU error result | Result with error type | CPU processing fails | Handles CPU errors |
| 3 | `test_processes_single_item` | Work queue with 1 item | 1 result in results queue | Worker thread running | Processes single work item |
| 4 | `test_handles_processing_error` | Work item causing exception | Error result in queue | Exception raised | Catches and records errors |
| 5 | `test_shutdown_event` | Shutdown event set | Thread exits immediately | Shutdown requested | Respects shutdown event |
| 6 | `test_processes_multiple_items` | Work queue with 3 items | 3 results in queue | Worker thread running | Processes multiple items |
| 7 | `test_task_done_called` | Work item processed | task_done called on queue | Worker thread running | Marks tasks as done |
| 8 | `test_batch_processing` | Batch of 5 items | All 5 processed | Batch worker running | Processes items in batches |
| 9 | `test_batch_with_errors` | Batch with some errors | Mixed success/error results | Batch worker running | Handles errors in batch |
| 10 | `test_partial_batch` | 2 items, batch size 10 | Both items processed | Batch worker running | Handles partial batches |

### test_writer_thread.py

Tests for writer thread database operations (9 tests).

| # | Test | Input | Output | Conditions/Assumptions | Logic |
|---|------|-------|--------|----------------------|-------|
| 1 | `test_writes_media_items` | Results queue with 3 media items | 3 items in database | Writer thread running | Writes media items to DB |
| 2 | `test_writes_errors` | Results queue with 2 errors | 2 errors in database | Writer thread running | Writes errors to DB |
| 3 | `test_batch_writing` | 10 items, batch size 3 | All 10 items written | Writer thread running | Writes in batches |
| 4 | `test_mixed_results` | Mix of media items and errors | Both types written | Writer thread running | Handles mixed result types |
| 5 | `test_shutdown_event` | Shutdown event set | Thread exits quickly | Shutdown requested | Respects shutdown event |
| 6 | `test_empty_queue` | Empty results queue | No items written | Writer thread running | Handles empty queue |
| 7 | `test_write_batch_empty` | Empty batch | No error raised | Batch write function | Handles empty batch |

---

## Summary

**Total: 341 tests** (9 + 286 + 46)

- **gphotos-321sync-common**: 9 tests
- **gphotos-321sync-media-scanner**: 286 tests
- **gphotos-321sync-takeout-extractor**: 46 tests
