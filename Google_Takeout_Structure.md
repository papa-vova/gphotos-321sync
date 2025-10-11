# Google Photos Takeout JSON Structure

This document describes the metadata fields found in JSON files accompanying photos/videos in Google Photos Takeout exports.

## Overview

When you export your Google Photos library via [Google Takeout](https://takeout.google.com/), each photo/video file is accompanied by a `.json` file containing metadata that Google Photos stored about that media item.

**Important Notes:**

- Not all fields are present in every JSON file
- Field presence depends on: photo source, user actions, device capabilities, Google Photos features used
- Google can change this structure without notice
- This is based on community reverse-engineering, not official Google documentation

## JSON Structure

### Example Structure

```json
{
  "title": "IMG_20230615_143022.jpg",
  "description": "Summer vacation at the beach",
  "imageViews": "42",
  "creationTime": {
    "timestamp": "1686838222",
    "formatted": "Jun 15, 2023, 2:30:22 PM UTC"
  },
  "photoTakenTime": {
    "timestamp": "1686838222",
    "formatted": "Jun 15, 2023, 2:30:22 PM UTC"
  },
  "geoData": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "altitude": 10.5,
    "latitudeSpan": 0.0,
    "longitudeSpan": 0.0
  },
  "geoDataExif": {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "altitude": 10.5,
    "latitudeSpan": 0.0,
    "longitudeSpan": 0.0
  },
  "people": [
    {
      "name": "John Doe"
    }
  ],
  "url": "https://photos.google.com/photo/...",
  "googlePhotosOrigin": {
    "mobileUpload": {
      "deviceType": "ANDROID_PHONE"
    }
  },
  "photoLastModifiedTime": {
    "timestamp": "1686838222",
    "formatted": "Jun 15, 2023, 2:30:22 PM UTC"
  }
}
```

## Field Reference

### Core Timestamp Fields

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `photoTakenTime.timestamp` | string (Unix epoch) | When the photo was taken | Most reliable timestamp; used by most tools |
| `photoTakenTime.formatted` | string | Human-readable date/time | For display only |
| `creationTime.timestamp` | string (Unix epoch) | When uploaded to Google Photos | May differ from photoTakenTime |
| `creationTime.formatted` | string | Human-readable date/time | For display only |
| `modificationTime.timestamp` | string (Unix epoch) | Last modification in Google Photos | Present if photo was edited |
| `modificationTime.formatted` | string | Human-readable date/time | For display only |
| `photoLastModifiedTime.timestamp` | string (Unix epoch) | File system modification time | May be different from above |

### Location Data

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `geoData.latitude` | number | GPS latitude (decimal degrees) | User-set or device GPS |
| `geoData.longitude` | number | GPS longitude (decimal degrees) | User-set or device GPS |
| `geoData.altitude` | number | Altitude in meters | May be 0.0 if not available |
| `geoData.latitudeSpan` | number | Latitude span | Usually 0.0 |
| `geoData.longitudeSpan` | number | Longitude span | Usually 0.0 |
| `geoDataExif.latitude` | number | Original EXIF GPS latitude | From camera EXIF data |
| `geoDataExif.longitude` | number | Original EXIF GPS longitude | From camera EXIF data |
| `geoDataExif.altitude` | number | Original EXIF GPS altitude | From camera EXIF data |

**Note:** `geoData` may be user-corrected, while `geoDataExif` is the original camera data.

### Descriptive Metadata

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `title` | string | Photo title/filename | Usually the original filename |
| `description` | string | User-added caption | Only present if user added description |
| `url` | string | Google Photos URL | Becomes invalid after deletion from Google Photos |
| `imageViews` | string | View count | May not be present; accuracy unclear |

### People & Recognition

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `people` | array | Tagged/detected people | Each entry has `name` field |
| `people[].name` | string | Person's name | Only for manually tagged faces |

**Note:** Google does not export all face detection data, only faces you manually labeled.

### Device & Origin Information

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `googlePhotosOrigin.mobileUpload.deviceType` | string | Device type | Values: `ANDROID_PHONE`, `IOS_PHONE`, etc. |
| `googlePhotosOrigin.mobileUpload.deviceFolder` | object | Device folder info | Camera make/model may be here |

### Organization & Status

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `archived` | boolean | Whether photo was archived | May be absent if false |
| `trashed` | boolean | Whether in trash | May be absent if false |
| `favorited` | boolean | Marked as favorite | May be absent if false |

### Advanced/Rare Fields

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `textAnnotations` | array | Google Vision API detected text | Rarely present |
| `locations` | array | Reverse-geocoded location names | Rarely present |
| `albums` | array | Album membership | Usually handled via folder structure instead |

## What's NOT Included

### Edit Information

- **Crop coordinates** - Not exported
- **Filter settings** - Not exported
- **Adjustment values** (brightness, contrast, etc.) - Not exported
- **Edit history** - Not exported

Google Photos only exports the **final rendered image** for edited photos, with a filename suffix like `-edited`, `-bearbeitet`, `-modifié`, etc. (language-dependent).

### Face Detection Details

- **Bounding boxes** - Not exported
- **Unlabeled faces** - Not exported
- **Face recognition confidence scores** - Not exported

Only manually tagged faces with names are included in the `people` array.

### Private/Internal Metadata

- **Internal Google IDs** - Not exported
- **Sync status** - Not exported
- **Sharing permissions** - Not exported
- **Comments from shared albums** - Not exported

## Sources & References

### Primary Sources

1. **Google Takeout Official Documentation**
   - [Google Takeout Homepage](https://takeout.google.com/)
   - Note: Google provides minimal documentation about JSON structure

2. **Community Reverse Engineering Projects**
   - [TheLastGimbus/GooglePhotosTakeoutHelper](https://github.com/TheLastGimbus/GooglePhotosTakeoutHelper)
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

The structure documented here is based on:

- Analysis of actual Google Takeout exports from multiple users
- Code inspection of open-source tools that parse these files
- Community reports and issue trackers
- Cross-referencing multiple independent implementations

### Reliability Notes

- **High confidence:** Core fields (timestamps, GPS, title, description)
- **Medium confidence:** Advanced fields (people, device info, status flags)
- **Low confidence:** Rare fields (textAnnotations, imageViews)

## Version History

Google Photos Takeout JSON structure has evolved over time:

- **Pre-2018:** Simpler structure, fewer fields
- **2018-2020:** Added `geoDataExif`, improved timestamp handling
- **2020-present:** Current structure, added `googlePhotosOrigin` details

**Note:** Google can change this structure at any time without announcement.

## JSON Sidecar File Matching Logic

The project implements sophisticated logic to match media files to their JSON sidecar files:

### Standard Patterns

For a media file `foo.jpg`, the tool looks for:

1. `foo.json`
2. `foo.jpg.json`

### Edited Files

For edited files like `foo-edited.jpg`, the tool:

- Strips the `-edited` suffix
- Looks for the original file's JSON: `foo.json` or `foo.jpg.json`
- **Rationale:** Google Photos doesn't create separate JSON files for edited versions

### Numbered Duplicates

For files with numeric suffixes like `foo(1).jpg`, the tool looks for:

1. `foo(1).json`
2. `foo(1).jpg.json`
3. `foo.jpg(1).json` ← **Special case:** Google's inconsistent naming

### Trailing Character Edge Cases

The tool handles these filename variations:

- `filename_n-.jpg` → looks for `filename_n.json`
- `filename_n.jpg` → looks for `filename_.json`
- `filename_.jpg` → looks for `filename.json`

## Recommendations for Developers

### When Building Tools

1. **Always check field existence** - Use optional chaining or null checks
2. **Validate timestamp formats** - Some may be strings, some numbers
3. **Handle missing GPS gracefully** - Not all photos have location data
4. **Preserve original JSON** - Keep backup before modifications
5. **Test with diverse exports** - Structure varies by photo source and age

### Priority Fields for Most Use Cases

**Essential:**

- `photoTakenTime.timestamp` - Date/time
- `title` - Filename

**Highly Recommended:**

- `geoData.latitude` / `geoData.longitude` - Location
- `description` - User captions
- `people` - Tagged faces

**Optional:**

- `archived`, `favorited` - Organization
- `googlePhotosOrigin` - Device info
- Everything else - Nice to have
