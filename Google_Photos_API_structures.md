# Google Photos API Structures

## Overview

This document summarizes the primary resource models exposed by the [Google Photos Library REST API](https://developers.google.com/photos/library/reference/rest). It focuses on album- and media-related entities and links directly to the official reference for deeper detail.

## Album (`v1.albums`)

- **Docs**: [Album resource](https://developers.google.com/photos/library/reference/rest/v1/albums)

### Album Fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `string` | Stable album identifier. |
| `title` | `string` | Display name, up to 500 characters. |
| `productUrl` | `string` | Web URL visible to signed-in owner or collaborators. |
| `isWriteable` | `boolean` | Indicates whether the calling app can add media. Scope-dependent. |
| `shareInfo` | `ShareInfo` | Present only for albums shared by the app with sharing scope. |
| `mediaItemsCount` | `string (int64)` | Output-only total media items. |
| `coverPhotoBaseUrl` | `string` | Base URL for cover photo bytes; append sizing parameters (for example, `=w2048-h1024`). |
| `coverPhotoMediaItemId` | `string` | Identifier of the media item used as cover. |

### Album JSON Representation

```json
{
  "id": "string",
  "title": "string",
  "productUrl": "string",
  "isWriteable": true,
  "shareInfo": {
    "sharedAlbumOptions": {
      "isCollaborative": true,
      "isCommentable": true
    },
    "shareableUrl": "string",
    "shareToken": "string",
    "isJoined": true,
    "isOwned": true,
    "isJoinable": true
  },
  "mediaItemsCount": "string",
  "coverPhotoBaseUrl": "string",
  "coverPhotoMediaItemId": "string"
}
```

### Album Methods

- `albums.create`: [Create album](https://developers.google.com/photos/library/reference/rest/v1/albums/create)
- `albums.get`: [Get album by ID](https://developers.google.com/photos/library/reference/rest/v1/albums/get)
- `albums.list`: [List albums](https://developers.google.com/photos/library/reference/rest/v1/albums/list)
- `albums.patch`: [Update album metadata](https://developers.google.com/photos/library/reference/rest/v1/albums/patch)
- `albums.batchAddMediaItems`: [Add media to album](https://developers.google.com/photos/library/reference/rest/v1/albums/batchAddMediaItems)
- `albums.batchRemoveMediaItems`: [Remove media from album](https://developers.google.com/photos/library/reference/rest/v1/albums/batchRemoveMediaItems)
- `albums.addEnrichment`: [Insert enrichment item](https://developers.google.com/photos/library/reference/rest/v1/albums/addEnrichment)

## ShareInfo

- **Docs**: [ShareInfo definition](https://developers.google.com/photos/library/reference/rest/v1/albums#ShareInfo)

| Field | Type | Notes |
| --- | --- | --- |
| `sharedAlbumOptions` | `SharedAlbumOptions` | Controls collaborator abilities. |
| `shareableUrl` | `string` | Optional public link (present when link sharing enabled). |
| `shareToken` | `string` | Token for joining/leaving shared album. |
| `isJoined` | `boolean` | Whether current user is joined. |
| `isOwned` | `boolean` | Whether current user owns the album. |
| `isJoinable` | `boolean` | Whether album accepts new collaborators. |

## Shared Album Options

- **Docs**: [SharedAlbumOptions definition](https://developers.google.com/photos/library/reference/rest/v1/albums#SharedAlbumOptions)

| Field | Type | Notes |
| --- | --- | --- |
| `isCollaborative` | `boolean` | Allows collaborators to add media when true. |
| `isCommentable` | `boolean` | Allows collaborators to add comments when true. |

## Media Item (`v1.mediaItems`)

- **Docs**: [MediaItem resource](https://developers.google.com/photos/library/reference/rest/v1/mediaItems)

### Media Item Fields

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `string` | Stable media identifier. |
| `description` | `string` | User-supplied description (< 1000 characters). |
| `productUrl` | `string` | Web URL visible to signed-in owner or collaborators. |
| `baseUrl` | `string` | Base download URL; specify size parameters before use. |
| `mimeType` | `string` | Media MIME type (for example, `image/jpeg`). |
| `mediaMetadata` | `MediaMetadata` | Size, creation time, and type-specific metadata. |
| `contributorInfo` | `ContributorInfo` | Available only for shared albums created by your app with sharing scope. |
| `filename` | `string` | Original filename shown in UI. |

### Media Item JSON Representation

```json
{
  "id": "string",
  "description": "string",
  "productUrl": "string",
  "baseUrl": "string",
  "mimeType": "string",
  "mediaMetadata": {
    "creationTime": "timestamp",
    "width": "string",
    "height": "string",
    "photo": {
      "cameraMake": "string",
      "cameraModel": "string",
      "focalLength": 0,
      "apertureFNumber": 0,
      "isoEquivalent": 0,
      "exposureTime": "duration"
    },
    "video": {
      "cameraMake": "string",
      "cameraModel": "string",
      "fps": 0,
      "status": "READY"
    }
  },
  "contributorInfo": {
    "profilePictureBaseUrl": "string",
    "displayName": "string"
  },
  "filename": "string"
}
```

### Media Item Methods

- `mediaItems.batchCreate`: [Create items after upload](https://developers.google.com/photos/library/reference/rest/v1/mediaItems/batchCreate)
- `mediaItems.batchGet`: [Batch retrieve items](https://developers.google.com/photos/library/reference/rest/v1/mediaItems/batchGet)
- `mediaItems.get`: [Get item by ID](https://developers.google.com/photos/library/reference/rest/v1/mediaItems/get)
- `mediaItems.list`: [List items created by app](https://developers.google.com/photos/library/reference/rest/v1/mediaItems/list)
- `mediaItems.patch`: [Update item metadata](https://developers.google.com/photos/library/reference/rest/v1/mediaItems/patch)
- `mediaItems.search`: [Search items by filters or album](https://developers.google.com/photos/library/reference/rest/v1/mediaItems/search)

## MediaMetadata

- **Docs**: [MediaMetadata definition](https://developers.google.com/photos/library/reference/rest/v1/mediaItems#MediaMetadata)

| Field | Type | Notes |
| --- | --- | --- |
| `creationTime` | `string (Timestamp)` | RFC 3339 creation timestamp (capture time). |
| `width` | `string (int64)` | Original width in pixels. |
| `height` | `string (int64)` | Original height in pixels. |
| `photo` | `Photo` | Present for photo media. |
| `video` | `Video` | Present for video media. |

## Photo Metadata

- **Docs**: [Photo definition](https://developers.google.com/photos/library/reference/rest/v1/mediaItems#Photo)

| Field | Type | Notes |
| --- | --- | --- |
| `cameraMake` | `string` | Camera brand. |
| `cameraModel` | `string` | Camera model. |
| `focalLength` | `number` | Lens focal length. |
| `apertureFNumber` | `number` | Aperture F-number. |
| `isoEquivalent` | `integer` | ISO value. |
| `exposureTime` | `string (Duration)` | Exposure time (for example, `"3.5s"`). |

## Video Metadata

- **Docs**: [Video definition](https://developers.google.com/photos/library/reference/rest/v1/mediaItems#Video)

| Field | Type | Notes |
| --- | --- | --- |
| `cameraMake` | `string` | Camera brand. |
| `cameraModel` | `string` | Camera model. |
| `fps` | `number` | Frames per second. |
| `status` | `enum (VideoProcessingStatus)` | Upload processing status. |

### VideoProcessingStatus Enum

- **Docs**: [VideoProcessingStatus enumeration](https://developers.google.com/photos/library/reference/rest/v1/mediaItems#VideoProcessingStatus)
- Values: `UNSPECIFIED`, `PROCESSING`, `READY`, `FAILED`.

## ContributorInfo

- **Docs**: [ContributorInfo definition](https://developers.google.com/photos/library/reference/rest/v1/mediaItems#ContributorInfo)

| Field | Type | Notes |
| --- | --- | --- |
| `profilePictureBaseUrl` | `string` | Base URL for contributor profile image. |
| `displayName` | `string` | Contributor display name. |

## Usage Notes

- Append sizing or formatting parameters to any `baseUrl` or `coverPhotoBaseUrl` before downloading, per [media access guidance](https://developers.google.com/photos/library/guides/access-media-items).
- Descriptions should contain user-authored text only; avoid auto-generated metadata when setting `MediaItem.description` via `mediaItems.patch`.
- Access to shared album metadata (`shareInfo`, `contributorInfo`) requires the `https://www.googleapis.com/auth/photoslibrary.sharing` scope.
