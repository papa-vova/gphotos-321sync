# Google Photos Takeout Structure

## Overview

When you export your Google Photos library via [Google Takeout](https://takeout.google.com/), you receive an archive with the following structure:

```text
Takeout/
└── Google Photos/
    ├── archive_browser.html          # Static HTML desctiption of the archive
    ├── Photos from YYYY/             # Chronological albums
    │   ├── [media files]             # Your actual photos and videos
    │   └── [metadata files]          # JSON sidecar files containing metadata for each media file
    └── [Album Name]/                 # Named albums/collections
        ├── metadata.json             # Album-level metadata — the only difference with chronological albums
        ├── [media files]             # Your actual photos and videos
        └── [metadata files]          # JSON sidecar files containing metadata for each media file
```

## Media Files

- **Images:** JPEG, PNG, GIF, WEBP, SVG, HEIC
- **Videos:** MPEG, MP4/M4V, MKV, 3GP, AVI, MOV

## Metadata Files

### Album Metadata

One `metadata.json` file exists per album folder.

### Media Metadata

Every photo/video has an associated sidecar JSON file with metadata.
The full ideal naming pattern:

```bash
[filename].[ext].supplemental-metadata.json
```

**Examples:**

- `IMG_20200920_131207.jpg` → `IMG_20200920_131207.jpg.supplemental-metadata.json`
- `VID_20200930_155021.mp4` → `VID_20200930_155021.mp4.supplemental-metadata.json`

**Truncated Variants:**

Google Takeout truncates sidecar filenames when it finds the full path to be too long. Examples:

- `.supplemental-metadat.json`
- `.supplemental-me.json`
- `.suppl.json`
- `.s.json`
- `..json`

### Special Naming of Media Files

#### Edited Versions

- **Pattern:** `[filename]-edited.[ext]`
- **Example:** `IMG_20200920_131207-edited.jpg`
- **Language variants:** `-bearbeitet` (German), `-modifié` (French), etc.

Edited files **do NOT** have separate metadata files — they share the original file's metadata.

#### Google Photos Creations

- **`-COLLAGE.jpg`** — Auto-generated photo collages
- **`-ANIMATION.gif`** — Auto-generated animations from burst photos
- **`-MOVIE.m4v`** — Auto-generated movies/compilations

These files **DO** have separate metadata files.

#### Special Cases

- **`[UNSET].jpg`** — Files with missing/corrupted original filenames
- **Files without extensions** — E.g., "03.03.13 - 1"

These files **DO** have separate metadata files.

### Duplicates

Files with identical names in Google Photos get numeric suffixes:

```bash
image.png
image(1).png
image(2).png
```

**Important:** numeric suffixes can be present in different parts of the file name. E.g.:

- `DSC_0245-COLLAGE(1).jpg` — most common
- `21.12(1).11 - 1` — rare

Each duplicate has its own metadata file, e.g.:

- `21.12.11 - 1.supplemental-metadata(1).json`
- `DSC_0245-COLLAGE.jpg.supplemental-metadata(1).json`
- `image(2).png.supplemental-metadata.json`

**Tilde suffix pattern:**

```bash
IMG20240221145914.jpg
IMG20240221145914~2.jpg
IMG20240221145914~3.jpg
```

These are normal file names and do not result in a specially numbered metadata sidecars.

## JSON Metadata Structure

### Album Metadata Structure

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

### Photo/Video Metadata Structure

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

| Field | Type | Purpose |
|-------|------|---------|
| `photoTakenTime.timestamp` | string | When the photo was taken |
| `photoTakenTime.formatted` | string | Human-readable taken time |
| `creationTime.timestamp` | string | When uploaded to Google Photos |
| `creationTime.formatted` | string | Human-readable upload time |
| `modificationTime.timestamp` | string | Last edit in Google Photos |
| `modificationTime.formatted` | string | Human-readable edit time |
| `photoLastModifiedTime.timestamp` | string | File system modification time |

### Location Data

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| `geoData.latitude` | number | GPS latitude | User-corrected or device GPS |
| `geoData.longitude` | number | GPS longitude | User-corrected or device GPS |
| `geoData.altitude` | number | Altitude in meters | May be 0.0 if unavailable |
| `geoData.latitudeSpan` | number | Latitude span | Usually 0.0 |
| `geoData.longitudeSpan` | number | Longitude span | Usually 0.0 |
| `geoDataExif.latitude` | number | Original EXIF GPS latitude | From camera EXIF data |
| `geoDataExif.longitude` | number | Original EXIF GPS longitude | From camera EXIF data |
| `geoDataExif.altitude` | number | Original EXIF GPS altitude | From camera EXIF data |

**Important difference:**

- **`geoData`** - May be manually adjusted by user in Google Photos
- **`geoDataExif`** - Original location from camera, unchanged

### Descriptive Metadata

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| `title` | string | Photo filename | The original file name (there can be other files with the same name, hence the duplicates with numeric suffixes) |
| `description` | string | User-added caption | Only present if user added text |
| `url` | string | Google Photos web URL | Becomes invalid after deletion |
| `imageViews` | string | View count in Google Photos | Note: string, not number! |

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

### Device & Origin Information

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| `googlePhotosOrigin.mobileUpload.deviceType` | string | Device type | `ANDROID_PHONE`, `IOS_PHONE`, etc. |
| `googlePhotosOrigin.mobileUpload.deviceFolder` | object | Device folder info | |
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

## Sidecar Matching Algorithm

Our implementation uses a comprehensive four-phase matching algorithm with exclusion that processes all media files in an album together. The algorithm extracts key components from sidecar filenames: base filename (e.g., "IMG_1234" from "IMG_1234.jpg.supplemental-metadata.json"), extension (e.g., "jpg" - may be truncated like "jp"), and numeric suffix (e.g., "(2)" - may be empty).

### Phase 1: Happy Path Matching

**Process:**

1. Look for exact filename match with no numeric suffix
2. If found → **SUCCESS** (immediate match)
3. Exclude matched pair from further processing

**Example:**

```text
Media: Album1/IMG_1234.jpg
Sidecar: Album1/IMG_1234.jpg.supplemental-metadata.json
Algorithm: Phase 1 (exact match, no numeric suffix)
Result: ✅ Match found
```

### Phase 2: Numbered Files Matching

**Process:**

1. Extract numeric suffix from media filename (e.g., "(2)")
2. Remove numeric suffix to get base filename
3. Look for sidecar with matching numeric suffix
4. If found → **SUCCESS**
5. Exclude matched pair from further processing

**Example:**

```text
Media: Album1/IMG_1234(2).jpg
Extract: numeric suffix "(2)", base filename "IMG_1234"
Sidecar: Album1/IMG_1234.jpg.supplemental-metadata(2).json
Algorithm: Phase 2 (numbered files matching)
Result: ✅ Match found
```

### Phase 3: Edited Files Matching

**Process:**

1. Check if media filename contains "-edited" (case-insensitive)
2. Strip "-edited" from filename
3. Extract numeric suffix from stripped filename (if any)
4. Remove numeric suffix to get base filename
5. Look for sidecar with matching numeric suffix (or no suffix)
6. If found → **SUCCESS**
7. Exclude matched pair from further processing

**Example:**

```text
Media: Album1/IMG_1234-edited.jpg
Strip: "IMG_1234" (no numeric suffix)
Sidecar: Album1/IMG_1234.jpg.supplemental-metadata.json
Algorithm: Phase 3 (edited files matching)
Result: ✅ Match found
```

**Example with numeric suffix:**

```text
Media: Album1/IMG_1234-edited(2).jpg
Strip: "IMG_1234(2)", extract suffix "(2)", base "IMG_1234"
Sidecar: Album1/IMG_1234.jpg.supplemental-metadata(2).json
Algorithm: Phase 3 (edited files matching with numeric suffix)
Result: ✅ Match found
```

### Phase 4: Unmatched Files

**Process:**

1. Log remaining unmatched media files at INFO level
2. Log remaining unmatched sidecars at INFO level
3. Report final statistics

### Exclusion Logic

**Key Feature:** Once a media file and sidecar are matched in any phase, they are excluded from further processing. This prevents double-matching and ensures each file is processed only once.

**Batch Processing:** All media files in an album are processed together, allowing the exclusion logic to work effectively across all phases.

### Numeric Suffix Validation

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

### Matching Examples

#### Standard Pattern

```text
Media: Album1/IMG_20200920_131207.jpg
Sidecar: Album1/IMG_20200920_131207.jpg.supplemental-metadata.json
Algorithm: Phase 1 (happy path)
Result: ✅ Match found
```

#### Truncated Sidecar

```text
Media: Album1/Screenshot_20190317-234331.jpg
Sidecar: Album1/Screenshot_20190317-234331.jpg.supplemental-me.json
Algorithm: Phase 1 (happy path with truncated pattern)
Result: ✅ Match found
```

#### Duplicate with Numeric Suffix

```text
Media: Album1/image(1).png
Sidecar: Album1/image.png.supplemental-metadata(1).json
Algorithm: Phase 2 (numbered files matching)
Result: ✅ Match found
```

#### Edited File

```text
Media: Album1/IMG_1234-edited.jpg
Sidecar: Album1/IMG_1234.jpg.supplemental-metadata.json
Algorithm: Phase 3 (edited files matching)
Result: ✅ Match found
```

#### Complex Numeric Suffix

```text
Media: Album1/21.12(2).11 - 1.jpg
Sidecar: Album1/21.12(2).11 - 1.jpg.supplemental-metadata(2).json
Algorithm: Phase 2 (numbered files matching)
Result: ✅ Match found
```

#### Multiple Candidates (Error Case)

```text
Media: Album1/IMG_1234.jpg
Sidecars: 
  - Album1/IMG_1234.jpg.supplemental-metadata(1).json
  - Album1/IMG_1234.jpg.supplemental-metadata(2).json
Algorithm: Phase 1 (multiple candidates, no clear winner)
Result: ❌ ERROR logged, no match
```

### Logging Levels

- **DEBUG**: Successful matches (media file ↔ sidecar)
- **INFO**: Unmatched media files and sidecars, album processing start/end
- **ERROR**: Multiple sidecar candidates with no clear winner

## What's NOT Included in Exports

### Edit Information

- **Crop coordinates** - You only get the final cropped image
- **Filter settings** - Which filter was applied
- **Adjustment values** - Brightness, contrast, saturation levels
- **Edit history** - Sequence of edits

**What you DO get:** The final rendered image as `[filename]-edited.[ext]`

### Face Detection Details

- **Bounding boxes** - Where faces are located in the image
- **Unlabeled faces** - Faces detected but not manually tagged
- **Face recognition confidence scores** - How confident the AI was

**What you DO get:** Only manually tagged faces in the `people` array

### Private/Internal Metadata

- **Internal Google IDs** - Internal database identifiers
- **Sync status** - Whether file is synced across devices
- **Sharing permissions** - Who has access to shared albums
- **Comments from shared albums** - Comments from other users

## References

This documentation is based on:

- Analysis of actual Google Takeout exports
- Code inspection of open-source tools that parse these files
- Community reports and issue trackers
- Cross-referencing multiple independent implementations
- Implementation and testing of our own comprehensive matching algorithm

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
