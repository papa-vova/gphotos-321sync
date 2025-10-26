# Google Photos Takeout Structure

This document provides a comprehensive reference for the file structure, naming conventions, and metadata format of Google Photos Takeout exports, along with the actual implementation details of our media scanner.

## Overview

When you export your Google Photos library via [Google Takeout](https://takeout.google.com/), you receive an archive containing:

- **Media files** - Your photos and videos
- **JSON metadata files** - Sidecar files with timestamps, location, people tags, and other metadata
- **Album metadata** - JSON files describing album properties
- **HTML viewer** - For offline browsing

**Important Notes:**

- Not all JSON fields are present in every file
- Field presence depends on: photo source, user actions, device capabilities, Google Photos features used
- Google can change this structure without notice
- This documentation is based on community reverse-engineering and analysis of actual exports

## Directory Structure

```text
Takeout/
└── Google Photos/
    ├── archive_browser.html          # Offline HTML viewer
    ├── Photos from YYYY/             # Chronological organization
    │   ├── [media files]
    │   └── [metadata files]
    └── [Album Name]/                 # Named albums/collections
        ├── metadata.json             # Album-level metadata
        ├── [media files]
        └── [metadata files]
```

**Purpose of each element:**

- **`archive_browser.html`** - HTML file for browsing the archive offline in a web browser
- **`Photos from YYYY/`** - Chronological folders containing media organized by year
- **`[Album Name]/`** - Named albums or collections you created in Google Photos
- **`metadata.json`** - Album-level metadata (one per album folder)
- **Media files** - Your actual photos and videos
- **Metadata files** - JSON sidecar files containing metadata for each media file

## File Types

### Media Files

#### Images

- **`.jpg`, `.JPG`, `.jpeg`** - JPEG photos (most common format)
- **`.png`, `.PNG`** - PNG images (screenshots, graphics)
- **`.gif`** - (Animated) GIFs
- **`.webp`** - WebP format (modern web images)
- **`.heic`** - HEIC format (iPhone photos)

#### Videos

- **`.mp4`, `.MP4`** - MP4 videos (most common)
- **`.m4v`** - M4V videos (Apple format)
- **`.3gp`** - 3GP videos (older mobile phones)
- **`.avi`** - AVI videos
- **`.MOV`** - QuickTime videos

### Metadata Files

#### Media Metadata (`.supplemental-metadata.json`)

Every photo/video has an associated JSON file with the pattern:

```text
[filename].[ext].supplemental-metadata.json
```

**Examples:**

- `IMG_20200920_131207.jpg` → `IMG_20200920_131207.jpg.supplemental-metadata.json`
- `VID_20200930_155021.mp4` → `VID_20200930_155021.mp4.supplemental-metadata.json`

**Truncated Variants:**

Google Takeout creates truncated sidecar filenames when the full path would be too long:

- `.supplemental-metadata.json` (full)
- `.supplemental-metadat.json` (truncated)
- `.supplemental-metad.json` (truncated)
- `.supplemental-me.json` (truncated)
- `.supplemen.json` (truncated)
- `.suppl.json` (truncated)

#### Album Metadata File (`metadata.json`)

One `metadata.json` file exists per album/collection folder.

### Special Files

#### Edited Versions

- **Pattern:** `[filename]-edited.[ext]`
- **Example:** `IMG_20200920_131207-edited.jpg`
- **Language variants:** `-bearbeitet` (German), `-modifié` (French), etc.

**Important:** Edited files do NOT have separate metadata files - they share the original file's metadata.

#### Google Photos Creations

- **`-COLLAGE.jpg`** - Auto-generated photo collages
- **`-ANIMATION.gif`** - Auto-generated animations from burst photos
- **`-MOVIE.m4v`** - Auto-generated movies/compilations

#### Special Cases

- **`[UNSET].jpg`** - Files with missing/corrupted original filenames
- **Files without extensions** - Legacy files (e.g., "03.03.13 - 1")

### Duplicates

#### Google Photos Duplicates

Files with identical names in Google Photos get numeric or tilde suffixes:

**Numeric suffix pattern:**

```text
image.png
image(1).png
image(2).png
```

**Tilde suffix pattern:**

```text
IMG20240221145914.jpg
IMG20240221145914~2.jpg
IMG20240221145914~3.jpg
```

**Important:** Each duplicate has its own metadata file:

- `image.png.supplemental-metadata.json`
- `image(1).png.supplemental-metadata.json`
- `image(2).png.supplemental-metadata.json`

#### Google Photos Duplicates (Numbered)

When Google Photos has multiple files with identical names, it creates numbered duplicates:

**Media files:**

```text
image.png
image(1).png
image(2).png
```

**Sidecar files:**

```text
image.png.supplemental-metadata.json
image.png.supplemental-metadata(1).json
image.png.supplemental-metadata(2).json
```

**Critical difference:** The `(N)` appears in **different positions**:

- Media: `image(1).png` - before extension
- Sidecar: `image.png.supplemental-metadata(1).json` - before `.json`

**Note:** This is the observed pattern in Google Takeout exports. The exact reason for this placement difference is not documented by Google, but our matching algorithm handles both patterns correctly.

## JSON Metadata Structure

### Album Metadata (`metadata.json`)

**Location:** One per album folder (e.g., `Takeout/Google Photos/Chair yoga/metadata.json`)

**Structure:**

```json
{
  "title": "Chair yoga",
  "description": "",
  "access": "protected",
  "date": {
    "timestamp": "1672477816",
    "formatted": "Dec 31, 2022, 9:10:16 AM UTC"
  }
}
```

**Field Purposes:**

| Field | Type | Purpose |
|-------|------|---------|
| `title` | string | Album name as shown in Google Photos |
| `description` | string | User-added album description (often empty) |
| `access` | string | Access level (e.g., "protected", "shared") |
| `date.timestamp` | string | Album creation time (Unix epoch seconds) |
| `date.formatted` | string | Human-readable creation date (for display) |

### Photo/Video Metadata (`.supplemental-metadata.json`)

**Location:** Next to each media file

**Example Structure:**

```json
{
  "title": "IMG_20200920_131207.jpg",
  "description": "",
  "imageViews": "9",
  "creationTime": {
    "timestamp": "1600598769",
    "formatted": "Sep 20, 2020, 10:46:09 AM UTC"
  },
  "photoTakenTime": {
    "timestamp": "1600596727",
    "formatted": "Sep 20, 2020, 10:12:07 AM UTC"
  },
  "geoData": {
    "latitude": 55.269422999999996,
    "longitude": 37.665591,
    "altitude": 214.492,
    "latitudeSpan": 0.0,
    "longitudeSpan": 0.0
  },
  "geoDataExif": {
    "latitude": 55.269422999999996,
    "longitude": 37.665591,
    "altitude": 214.492,
    "latitudeSpan": 0.0,
    "longitudeSpan": 0.0
  },
  "people": [{
    "name": "Дочь"
  }],
  "url": "https://photos.google.com/photo/AF1QipOyLtYKtmMPyLhse9O8lOcWmb6LND5-jHBh9wUC",
  "googlePhotosOrigin": {
    "mobileUpload": {
      "deviceFolder": {
        "localFolderName": ""
      },
      "deviceType": "ANDROID_PHONE"
    }
  },
  "photoLastModifiedTime": {
    "timestamp": "1600598769",
    "formatted": "Sep 20, 2020, 10:46:09 AM UTC"
  },
  "modificationTime": {
    "timestamp": "1600598800",
    "formatted": "Sep 20, 2020, 10:46:40 AM UTC"
  },
  "archived": false,
  "favorited": true
}
```

## JSON Field Reference

### Core Timestamp Fields

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| `photoTakenTime.timestamp` | string | **When the photo was taken** | **Most important for sync** - Unix epoch seconds |
| `photoTakenTime.formatted` | string | Human-readable taken time | For display only |
| `creationTime.timestamp` | string | When uploaded to Google Photos | May differ from photoTakenTime |
| `creationTime.formatted` | string | Human-readable upload time | For display only |
| `modificationTime.timestamp` | string | Last edit in Google Photos | Present if photo was edited |
| `modificationTime.formatted` | string | Human-readable edit time | For display only |
| `photoLastModifiedTime.timestamp` | string | File system modification time | May differ from above |

**Sync recommendation:** Use `photoTakenTime.timestamp` as the primary timestamp. Fall back to `creationTime.timestamp` if `photoTakenTime` is missing.

### Location Data

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| `geoData.latitude` | number | GPS latitude | User-corrected or device GPS |
| `geoData.longitude` | number | GPS longitude | User-corrected or device GPS |
| `geoData.altitude` | number | Altitude in meters | May be 0.0 if unavailable |
| `geoData.latitudeSpan` | number | Latitude span | Usually 0.0 |
| `geoData.longitudeSpan` | number | Longitude span | Usually 0.0 |
| `geoDataExif.latitude` | number | **Original EXIF GPS latitude** | From camera EXIF data |
| `geoDataExif.longitude` | number | **Original EXIF GPS longitude** | From camera EXIF data |
| `geoDataExif.altitude` | number | Original EXIF GPS altitude | From camera EXIF data |

**Important difference:**

- **`geoData`** - May be manually adjusted by user in Google Photos
- **`geoDataExif`** - Original location from camera, unchanged

**Sync recommendation:** Prefer `geoDataExif` for original location. Use `geoData` if you want user corrections.

### Descriptive Metadata

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| `title` | string | Photo filename | Usually the original filename |
| `description` | string | User-added caption | Only present if user added text |
| `url` | string | Google Photos web URL | Becomes invalid after deletion |
| `imageViews` | string | View count in Google Photos | **Note: string, not number!** |

### People & Face Recognition

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| `people` | array | Tagged people in photo | Each entry has `name` field |
| `people[].name` | string | Person's name | Only manually tagged faces |

**Important limitations:**

- Only manually tagged faces are exported
- Bounding boxes (face locations) are NOT exported
- Unlabeled detected faces are NOT exported
- Face recognition confidence scores are NOT exported

**Example:**

```json
"people": [
  {"name": "John Doe"},
  {"name": "Дочь"}
]
```

**Note:** Names can be in any language (Unicode support required).

### Device & Origin Information

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| `googlePhotosOrigin.mobileUpload.deviceType` | string | Device type | `ANDROID_PHONE`, `IOS_PHONE`, etc. |
| `googlePhotosOrigin.mobileUpload.deviceFolder` | object | Device folder info | **May be absent entirely** |
| `googlePhotosOrigin.mobileUpload.deviceFolder.localFolderName` | string | Original device folder | Often empty `""`, or `"WhatsApp Images"`, `"Camera"` |
| `googlePhotosOrigin.fromSharedAlbum` | object | Photo from shared album | Empty object `{}` |
| `googlePhotosOrigin.composition.type` | string | Google Photos creation type | `AUTO` or `MANUAL` for collages/animations |
| `appSource.androidPackageName` | string | Source Android app | e.g., `com.whatsapp`, `com.android.chrome` |

**Important notes:**

- `googlePhotosOrigin` always has exactly **one** property: `mobileUpload`, `fromSharedAlbum`, or `composition`
- `deviceFolder` may be completely absent (not just empty)
- `appSource` is only present for certain apps (WhatsApp, Chrome, etc.)

### Organization & Status

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| `archived` | boolean | Photo was archived | May be absent if false |
| `trashed` | boolean | Photo was in trash | May be absent if false |
| `favorited` | boolean | Marked as favorite | May be absent if false |

**Note:** These fields may be absent (not present in JSON) if the value is `false`.

## Media & Metadata Scanning Implementation

Our scanner implements a comprehensive file discovery and matching system that handles all Google Takeout patterns and edge cases.

### File Discovery Process

1. **Directory Scanning**: Recursively scans the Google Photos directory structure
2. **File Classification**: Separates media files from JSON metadata files
3. **Album Detection**: Identifies album boundaries and metadata
4. **Sidecar Indexing**: Builds efficient lookup structures for matching

### Core Functions

#### `discover_files(target_media_path: Path) -> DiscoveryResult`

**Purpose**: Main public API for file discovery

**Process:**

1. Detects Google Takeout structure (`Takeout/Google Photos/` vs direct path)
2. Collects all media and JSON files
3. Builds sidecar index for efficient matching
4. Processes each media file to find matching sidecars
5. Returns comprehensive results with statistics

**Returns:** `DiscoveryResult` containing:

- `files`: List of `FileInfo` objects for each media file
- `json_sidecar_count`: Number of successfully paired sidecars
- `paired_sidecars`: Set of sidecar paths that were matched
- `all_sidecars`: Set of all discovered sidecar paths (for orphan detection)

#### `_collect_files(scan_root: Path) -> tuple[list[Path], list[Path], dict[Path, set[str]]]`

**Purpose**: Collects all files in the directory tree

**Returns:**

- `media_files`: List of all potential media files
- `json_files`: List of all JSON sidecar files
- `all_files`: Dictionary mapping directories to their file sets

#### `_build_sidecar_index(sidecar_filenames: List[str]) -> Dict[str, List[ParsedSidecar]]`

**Purpose**: Builds efficient index for sidecar lookup

**Key Format**: `"album_path/filename.extension"` (e.g., `"Album1/IMG_1234.jpg"`)

**Benefits:**

- Prevents cross-album collisions
- Handles multiple sidecars per media file
- Enables O(1) lookup performance

#### `_parse_sidecar_filename(sidecar_path: Path) -> ParsedSidecar`

**Purpose**: Parses sidecar filenames into structured components

**Returns:** `ParsedSidecar` with:

- `filename`: Base filename (e.g., "IMG_1234")
- `extension`: Media extension (e.g., "jpg", may be truncated)
- `numeric_suffix`: Duplicate suffix (e.g., "(1)" or "")
- `full_sidecar_path`: Complete path to sidecar file
- `photo_taken_time`: Timestamp from JSON content (if available)

## Sidecar Matching Algorithm

Our implementation uses a comprehensive three-phase matching algorithm that handles all Google Takeout patterns and edge cases.

### Phase 1: Exact Filename Matching

#### Case 1: Single Exact Match

**Pattern**: `media_file.jpg` ↔ `media_file.jpg.supplemental-metadata.json`

**Process:**

1. Create lookup key: `"album_path/media_file.jpg"`
2. Check if exactly one sidecar exists for this key
3. If no numeric suffix → **SUCCESS** (immediate match)
4. If has numeric suffix → validate suffix matches media filename

**Example:**

```text
Media: Album1/IMG_1234.jpg
Sidecar: Album1/IMG_1234.jpg.supplemental-metadata.json
Result: ✅ Match found
```

#### Case 2: Multiple Candidates

**Pattern**: Multiple sidecars for same media file

**Process:**

1. Check if ONLY ONE sidecar has no numeric suffix
2. If yes → **SUCCESS** (take the no-suffix one)
3. If no → **ERROR** (log all candidates, no match)

**Example:**

```text
Media: Album1/IMG_1234.jpg
Sidecars: 
  - Album1/IMG_1234.jpg.supplemental-metadata.json (no suffix)
  - Album1/IMG_1234.jpg.supplemental-metadata(1).json (suffix)
Result: ✅ Match found (takes the no-suffix one)
```

### Phase 2: Alternative Pattern Matching

#### Case 3.1: Edited File Pattern

**Pattern**: `media_file-edited.jpg` → `media_file.jpg.supplemental-metadata.json`

**Process:**

1. Check if media filename ends with edited suffix (case-insensitive)
2. Strip edited suffix from filename
3. Retry Phase 1 matching with stripped filename
4. Handle multiple languages: `-edited`, `-bearbeitet`, `-modifié`, etc.

**Example:**

```text
Media: Album1/IMG_1234-edited.jpg
Strip: IMG_1234
Lookup: Album1/IMG_1234.jpg
Sidecar: Album1/IMG_1234.jpg.supplemental-metadata.json
Result: ✅ Match found
```

#### Case 3.2: Numeric Suffix Matching

**Pattern**: Media file has numeric suffix, find matching sidecar

**Process:**

1. Extract numeric suffix from media filename (e.g., "(2)")
2. Search all sidecars in same album for matching suffix
3. Validate suffix appears in correct position

**Example:**

```text
Media: Album1/IMG_1234(2).jpg
Suffix: "(2)"
Search: Find sidecar with numeric_suffix="(2)"
Sidecar: Album1/IMG_1234.jpg.supplemental-metadata(2).json
Result: ✅ Match found
```

### Phase 3: Numeric Suffix Validation

#### Suffix Position Rules

Our algorithm validates numeric suffixes using two mutually exclusive patterns:

1. **At the very end**: `"(n)$"` (e.g., `"photo(2)"`)
2. **Somewhere within**: `"(n)\."` (e.g., `"21.12(2).11"`)

**Example:**

```text
Media: "21.12(2).11 - 1.jpg"
Suffix: "(2)"
Pattern: "(2)\." matches "21.12(2).11"
Result: ✅ Valid match
```

### Algorithm Benefits

#### Performance Optimizations

1. **Album-Scoped Matching**: Prevents cross-album collisions
2. **Efficient Indexing**: O(1) lookup performance
3. **Early Exit**: Stops at first successful match
4. **Batch Processing**: Processes all files in single pass

#### Robustness Features

1. **Case-Insensitive Matching**: Handles filename case variations
2. **Multi-Language Support**: Supports edited file patterns in multiple languages
3. **Truncated Filename Handling**: Handles Google's path length limitations
4. **Comprehensive Logging**: DEBUG for matches, INFO for unmatched files, ERROR for conflicts

#### Error Handling

1. **Graceful Degradation**: Continues processing when individual matches fail
2. **Detailed Logging**: Provides clear information about matching decisions
3. **Orphan Detection**: Identifies unmatched media files and sidecars
4. **Statistics Tracking**: Provides comprehensive matching statistics

### Matching Examples

#### Standard Pattern

```text
Media: Album1/IMG_20200920_131207.jpg
Sidecar: Album1/IMG_20200920_131207.jpg.supplemental-metadata.json
Algorithm: Phase 1, Case 1 (exact match)
Result: ✅ Match found
```

#### Truncated Sidecar

```text
Media: Album1/Screenshot_20190317-234331.jpg
Sidecar: Album1/Screenshot_20190317-234331.jpg.supplemental-me.json
Algorithm: Phase 1, Case 1 (exact match with truncated pattern)
Result: ✅ Match found
```

#### Duplicate with Numeric Suffix

```text
Media: Album1/image(1).png
Sidecar: Album1/image.png.supplemental-metadata(1).json
Algorithm: Phase 1, Case 1 (numeric suffix validation)
Result: ✅ Match found
```

#### Edited File

```text
Media: Album1/IMG_1234-edited.jpg
Sidecar: Album1/IMG_1234.jpg.supplemental-metadata.json
Algorithm: Phase 2, Case 3.1 (edited pattern)
Result: ✅ Match found
```

#### Complex Numeric Suffix

```text
Media: Album1/21.12(2).11 - 1.jpg
Sidecar: Album1/21.12(2).11 - 1.jpg.supplemental-metadata(2).json
Algorithm: Phase 2, Case 3.2 (numeric suffix matching)
Result: ✅ Match found
```

## What's NOT Included in Exports

### Edit Information (NOT Exported)

- **Crop coordinates** - You only get the final cropped image
- **Filter settings** - Which filter was applied
- **Adjustment values** - Brightness, contrast, saturation levels
- **Edit history** - Sequence of edits

**What you DO get:** The final rendered image as `[filename]-edited.[ext]`

### Face Detection Details (NOT Exported)

- **Bounding boxes** - Where faces are located in the image
- **Unlabeled faces** - Faces detected but not manually tagged
- **Face recognition confidence scores** - How confident the AI was

**What you DO get:** Only manually tagged faces in the `people` array

### Private/Internal Metadata (NOT Exported)

- **Internal Google IDs** - Internal database identifiers
- **Sync status** - Whether file is synced across devices
- **Sharing permissions** - Who has access to shared albums
- **Comments from shared albums** - Comments from other users

## Statistics (from example export)

- **Total files:** ~91,900
- **Media files:** ~45,950 (50%)
- **Metadata files:** ~45,950 (50%)
- **Date range:** 2007-2025+
- **Languages:** English, Russian (Cyrillic), others
- **Video formats:** MP4 (most common), M4V, 3GP, AVI, MOV
- **Image formats:** JPG (most common), PNG, GIF, WEBP, HEIC

## References

### Primary Sources

1. **Google Takeout Official Documentation**
   - [Google Takeout Homepage](https://takeout.google.com/)
   - Note: Google provides minimal documentation about JSON structure

2. **Community Reverse Engineering Projects**
   - [TheLastGimbus/GooglePhotosTakeoutHelper](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper) - Popular takeout processing tool
   - [mattwilson1024/google-photos-exif](https://github.com/mattwilson1024/google-photos-exif) - Writes JSON metadata back to EXIF
   - [gilesknap/gphotos-sync](https://github.com/gilesknap/gphotos-sync) - Python sync tool
   - [simon987/gpth](https://github.com/simon987/gpth) - Original Python version of GPTH

3. **GitHub Issues & Discussions**
   - [GPTH Issue #136](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper/issues/136) - GPS data discussion
   - [GPTH Issue #137](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper/issues/137) - Writing data back to EXIF
   - Various issues across multiple Google Photos tools

### Verification Method

This documentation is based on:

- Analysis of actual Google Takeout exports
- Code inspection of open-source tools that parse these files
- Community reports and issue trackers
- Cross-referencing multiple independent implementations
- Implementation and testing of our own comprehensive matching algorithm
