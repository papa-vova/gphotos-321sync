# Google Photos Takeout Structure

This document provides a comprehensive reference for the file structure, naming conventions, and metadata format of Google Photos Takeout exports.

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
- This documentation is based on community reverse-engineering and analysis of A LOT of files from actual exports

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

**Purpose:** These are your actual photo files. Each has an associated JSON metadata file.

#### Videos

- **`.mp4`, `.MP4`** - MP4 videos (most common)
- **`.m4v`** - M4V videos (Apple format)
- **`.3gp`** - 3GP videos (older mobile phones)
- **`.avi`** - AVI videos
- **`.MOV`** - QuickTime videos

**Purpose:** Your video files. Each has an associated JSON metadata file.

### Metadata Files

#### Media Metadata (`.supplemental-metadata.json`)

Every photo/video has an associated JSON file with the pattern:

```text
[filename].[ext].supplemental-metadata.json
```

**Examples:**

- `IMG_20200920_131207.jpg` → `IMG_20200920_131207.jpg.supplemental-metadata.json`
- `VID_20200930_155021.mp4` → `VID_20200930_155021.mp4.supplemental-metadata.json`

**Purpose:** Contains all metadata Google Photos stored about the media file:

- Timestamps (when taken, when uploaded, when modified)
- GPS location data
- People tags (face recognition)
- User-added descriptions
- View counts
- Device information

**Truncated Variants:**

Due to Windows path length limits (260 characters), you may see truncated filenames:

- `.supplemental-metadata.json` (full)
- `.supplemental-metadat.json` (truncated)
- `.supplemental-metad.json` (truncated)
- `.supplemental-me.json` (truncated)
- `.supplemen.json` (truncated)
- `.suppl.json` (truncated)

**Purpose:** Same as above, but filename was truncated to fit Windows path limits.

#### Album Metadata File (`metadata.json`)

One `metadata.json` file exists per album/collection folder.

**Purpose:** Contains album-level information:

- Album title
- Album description
- Creation date
- Access level (e.g., "protected")

### Special Files

#### Edited Versions

- **Pattern:** `[filename]-edited.[ext]`
- **Example:** `IMG_20200920_131207-edited.jpg`
- **Language variants:** `-bearbeitet` (German), `-modifié` (French), etc.

**Purpose:** Google Photos edits (crops, filters, adjustments). The edited file is the final rendered image.

**Important:** Edited files do NOT have separate metadata files - they share the original file's metadata.

**Matching logic:**

- `IMG_20200920_131207-edited.jpg` uses `IMG_20200920_131207.jpg.supplemental-metadata.json`
- The metadata file belongs to the original, not the edited version

#### Google Photos Creations

- **`-COLLAGE.jpg`** - Auto-generated photo collages
- **`-ANIMATION.gif`** - Auto-generated animations from burst photos
- **`-MOVIE.m4v`** - Auto-generated movies/compilations

**Purpose:** Automatic creations made by Google Photos. Each has its own metadata file.

#### Special Cases

- **`[UNSET].jpg`** - Files with missing/corrupted original filenames
- **Files without extensions** - Legacy files (e.g., "03.03.13 - 1")

**Purpose:** Files that lost their original metadata or were imported without proper filenames.

### Duplicates

Files with identical names get numeric suffixes:

```text
image.png
image(1).png
image(2).png
```

**Alternative duplicate pattern (tilde suffix):**

```text
IMG20240221145914.jpg
IMG20240221145914~2.jpg
IMG20240221145914~3.jpg
```

**Purpose:** Handles filename conflicts when multiple files have the same name.

**Important:** Each duplicate has its own metadata file:

- `image.png.supplemental-metadata.json`
- `image(1).png.supplemental-metadata.json`
- `image(2).png.supplemental-metadata.json`
- `IMG20240221145914.jpg.supplemental-metadata.json`
- `IMG20240221145914~2.jpg.supplemental-metadata.json`

## File Naming Patterns

### Camera/Phone Photos

- **`IMG_YYYYMMDD_HHMMSS.jpg`** - Android/Google Camera format
  - Example: `IMG_20200920_131207.jpg` = September 20, 2020, 13:12:07
  - **Purpose:** Timestamp-based naming from Android devices

- **`DSC_NNNN.JPG`** - DSLR cameras (Nikon, Canon, etc.)
  - Example: `DSC_0529.JPG`
  - **Purpose:** Sequential numbering from digital cameras

- **`IMG_NNNN.JPG`** - iPhones and other devices
  - Example: `IMG_1234.JPG`
  - **Purpose:** Sequential numbering from iOS devices

- **`IMG_NNNN.png`** - Screenshots
  - **Purpose:** Screenshots saved as PNG

### WhatsApp Files

- **`IMG-YYYYMMDD-WANNNN.jpg`** - WhatsApp images
  - Example: `IMG-20200920-WA0009.jpg`
  - **Purpose:** Images received or sent via WhatsApp

- **`VID-YYYYMMDD-WANNNN.mp4`** - WhatsApp videos
  - Example: `VID-20200920-WA0005.mp4`
  - **Purpose:** Videos received or sent via WhatsApp

### Screenshots

- **`Screenshot_YYYY-MM-DD-HH-MM-SS.png`** - Detailed timestamp format
- **`Screenshot_YYYYMMDD-HHMMSS.jpg`** - Compact timestamp format

**Purpose:** Screenshots taken on your device.

### Social Media

- **`FB_IMG_*.jpg`** - Facebook images
  - **Purpose:** Photos downloaded from Facebook

- **`received_*.jpeg`** - Facebook Messenger
  - **Purpose:** Images received via Facebook Messenger

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

**Purpose:** These timestamps allow you to:

- Restore original capture dates when syncing
- Track when files were uploaded vs. taken
- Identify edited photos
- Preserve chronological order

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

**Purpose:** Preserve location information for:

- Geotagging photos
- Creating maps of your photos
- Organizing by location
- Privacy (you may want to strip this)

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
| `imageViews` | string | View count in Google Photos | May not be present; accuracy unclear |

**Purpose:**

- **`title`** - Restore original filenames
- **`description`** - Preserve user captions/notes
- **`url`** - Reference back to Google Photos (while it exists)
- **`imageViews`** - Track engagement (optional)

### People & Face Recognition

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| `people` | array | Tagged people in photo | Each entry has `name` field |
| `people[].name` | string | Person's name | Only manually tagged faces |

**Purpose:** Preserve face tags for:

- Organizing photos by person
- Searching for people
- Creating person-specific albums

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

**Purpose:** Track where photos came from:

- Identify device type
- Organize by device
- Understand upload source
- Identify photos from shared albums
- Track which app uploaded the photo

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

**Purpose:** Preserve organization state:

- **`archived`** - Hidden from main view but not deleted
- **`trashed`** - In trash (may want to skip these)
- **`favorited`** - Starred/favorite photos

**Note:** These fields may be absent (not present in JSON) if the value is `false`.

### Advanced/Rare Fields

| Field | Type | Purpose | Notes |
|-------|------|---------|-------|
| `imageViews` | string | View count in Google Photos | **Note: string, not number!** Always present |
| `textAnnotations` | array | Detected text in image | Google Vision API results; rarely present |
| `locations` | array | Reverse-geocoded location names | Place names; rarely present |
| `albums` | array | Album membership | Usually handled via folder structure |
| `photoLastModifiedTime` | object | File modification timestamp | **Rarely present in modern exports** |
| `modificationTime` | object | Last edit timestamp | **Rarely present in modern exports** |

**Purpose:** Additional metadata that may be useful but is rarely present.

**Important:** Many fields documented in older exports may not be present in modern (2024+) exports. Always check for field existence before accessing.

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

## JSON Sidecar File Matching Logic

When building a sync tool, you need to match media files to their JSON metadata files. Google uses several naming patterns:

### Standard Patterns

For a media file `photo.jpg`, look for:

1. `photo.jpg.supplemental-metadata.json` (most common)
2. `photo.jpg.supplemental-metadat.json` (truncated)
3. `photo.jpg.supplemental-metad.json` (truncated)
4. `photo.jpg.supplemental-me.json` (truncated)
5. `photo.jpg.supplemen.json` (truncated)
6. `photo.jpg.suppl.json` (truncated)
7. `photo.json` (alternative pattern for long filenames)

**Note:** Pattern #7 (`.json` without `.supplemental-metadata`) is used when the full filename is very long or contains special patterns like UUIDs.

### Edited Files

For edited files like `photo-edited.jpg`:

- **Strip the `-edited` suffix**
- Look for the original file's JSON: `photo.jpg.supplemental-metadata.json` or `photo.json`
- **Rationale:** Google Photos doesn't create separate JSON files for edited versions

**Example:**

- `IMG_20200920_131207-edited.jpg` → uses `IMG_20200920_131207.jpg.supplemental-metadata.json`

### Numbered Duplicates

For files with numeric suffixes like `photo(1).jpg`, look for:

1. `photo(1).jpg.supplemental-metadata.json`
2. `photo(1).json`
3. `photo.jpg(1).json` ← **Special case:** Google's inconsistent naming

### Tilde Suffix Duplicates

For files with tilde suffixes like `photo~2.jpg`, look for:

1. `photo~2.jpg.supplemental-metadata.json` (exact match)
2. `photo.jpg.supplemental-metadata.json` (original file's sidecar)

**Rationale:** Google may create separate metadata for tilde duplicates or reuse the original's metadata.

### Trailing Character Edge Cases

Handle these filename variations:

- `filename_n-.jpg` → looks for `filename_n.json`
- `filename_n.jpg` → looks for `filename_.json`
- `filename_.jpg` → looks for `filename.json`

### Truncated Metadata Filenames

Due to Windows path length limits, metadata filenames may be truncated:

- `.supplemental-metadata.json` (full, 27 chars)
- `.supplemental-metadat.json` (truncated, 25 chars)
- `.supplemental-metad.json` (truncated, 22 chars)
- `.supplemental-me.json` (truncated, 18 chars)
- `.supplemen.json` (truncated, 15 chars)
- `.suppl.json` (truncated, 11 chars)
- `.json` (alternative pattern, 5 chars)

**Matching strategy:** Try all variants when looking for metadata files. Start with the full pattern and work down to shorter variants.

## Statistics (from example export)

- **Total files:** ~91,900
- **Media files:** ~45,950 (50%)
- **Metadata files:** ~45,950 (50%)
- **Date range:** 2007-2025+
- **Languages:** English, Russian (Cyrillic), others
- **Video formats:** MP4 (most common), M4V, 3GP, AVI, MOV
- **Image formats:** JPG (most common), PNG, GIF, WEBP, HEIC

## Sync Tool Recommendations

### Essential Implementation Steps

1. **Parse metadata first** - Build an index of all media with timestamps before processing
2. **Handle edited files** - Link edited versions to originals using the `-edited` suffix
3. **Preserve timestamps** - Use `photoTakenTime.timestamp` to set file modification dates
4. **Extract geolocation** - Write GPS data back to EXIF if desired
5. **Preserve people tags** - Store face tags in EXIF or separate database
6. **Handle duplicates** - Detect and handle `(1)`, `(2)` suffixes appropriately
7. **Unicode support** - Handle international characters in filenames and metadata
8. **Path length limits** - Handle Windows 260-character path limit
9. **Incremental sync** - Track processed files to avoid re-processing on subsequent runs
10. **Error handling** - Gracefully handle missing metadata, corrupted files, etc.

### Priority Fields for Sync Tools

**Essential (must have):**

- `photoTakenTime.timestamp` - For chronological organization
- `title` - For filename restoration

**Highly Recommended:**

- `geoData` / `geoDataExif` - Location preservation
- `description` - User captions
- `people` - Face tags

**Optional (nice to have):**

- `archived`, `favorited` - Organization state
- `googlePhotosOrigin` - Device tracking
- `imageViews` - Engagement metrics

### Developer Best Practices

1. **Always check field existence** - Use optional chaining or null checks (not all fields are present)
2. **Validate timestamp formats** - Some may be strings, some numbers
3. **Handle missing GPS gracefully** - Not all photos have location data
4. **Preserve original JSON** - Keep backups before modifications
5. **Test with diverse exports** - Structure varies by photo source and age
6. **Handle special characters** - Cyrillic, emoji, and other Unicode in filenames
7. **Respect privacy** - Consider stripping GPS data if user requests

## Version History

Google Photos Takeout structure has evolved over time:

- **Pre-2018:** Simpler structure, fewer JSON fields
- **2018-2020:** Added `geoDataExif`, improved timestamp handling
- **2020-present:** Current structure with `googlePhotosOrigin` details

**Note:** Google can change this structure at any time without announcement.

## Sources & References

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

4. **Community Forums & Blogs**
   - Reddit r/DataHoarder - Google Takeout discussions
   - Stack Overflow - Google Takeout parsing questions
   - Personal blogs documenting Takeout structure

### Verification Method

This documentation is based on:

- Analysis of actual Google Takeout exports
- Code inspection of open-source tools that parse these files
- Community reports and issue trackers
- Cross-referencing multiple independent implementations

### Reliability Notes

- **High confidence:** Core fields (timestamps, GPS, title, description)
- **Medium confidence:** Advanced fields (people, device info, status flags)
- **Low confidence:** Rare fields (textAnnotations, imageViews)
