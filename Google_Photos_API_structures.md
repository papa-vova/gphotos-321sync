# Google Photos API Structures

## Overview

This document summarizes the album, media item, and search resources provided by the [Google Photos Library REST API](https://developers.google.com/photos/library/reference/rest). It lists every documented field for the album and media item resources and explains how to list the media items contained in an album.

## Album resource (`v1.albums`)

[https://developers.google.com/photos/library/reference/rest/v1/albums](https://developers.google.com/photos/library/reference/rest/v1/albums)

```jsonc
{
  "id": "ALBUM_ID", // string: persistent album identifier
  "title": "Summer Vacation 2024", // string (≤500 chars): album name shown to users
  "productUrl": "https://photos.google.com/lr/album/ALBUM_ID", // string: signed-in Google Photos URL
  "isWriteable": true, // boolean: caller can add media if true
  "mediaItemsCount": "128", // string(int64): output-only count of media items
  "coverPhotoBaseUrl": "https://lh3.googleusercontent.com/...", // string: append parameters like "=w2048-h1024"
  "coverPhotoMediaItemId": "MEDIA_ITEM_ID", // string: ID of the cover media item
  "shareInfo": {
    "shareableUrl": "https://photos.app.goo.gl/...", // string: link share URL (when link sharing enabled)
    "shareToken": "AF1QipNj...", // string: token for join/leave/retrieve shared album details
    "isJoined": true, // boolean: caller is joined (always true for owner)
    "isOwned": true, // boolean: caller owns the album
    "isJoinable": true, // boolean: album currently accepts joins
    "sharedAlbumOptions": {
      "isCollaborative": true, // boolean: collaborators may add media
      "isCommentable": true // boolean: collaborators may comment
    }
  }
}
```

## MediaItem resource (`v1.mediaItems`)

[https://developers.google.com/photos/library/reference/rest/v1/mediaItems](https://developers.google.com/photos/library/reference/rest/v1/mediaItems)

```jsonc
{
  "id": "MEDIA_ITEM_ID", // string: persistent media identifier
  "description": "Sunset over Waikiki", // string (<1000 chars): user-provided description
  "productUrl": "https://photos.google.com/lr/photo/MEDIA_ITEM_ID", // string: signed-in Google Photos URL
  "baseUrl": "https://lh3.googleusercontent.com/...", // string: append sizing params before download
  "mimeType": "image/jpeg", // string: MIME type of the media
  "filename": "IMG_20240715_183025.jpg", // string: filename displayed in Google Photos
  "mediaMetadata": {
    "creationTime": "2024-07-15T18:30:25Z", // string (Timestamp): capture time
    "width": "4032", // string (int64): original width in pixels
    "height": "3024", // string (int64): original height in pixels
    "photo": { // present only when media is a photo
      "cameraMake": "Google", // string: camera brand
      "cameraModel": "Pixel 8", // string: camera model
      "focalLength": 6.81, // number: lens focal length
      "apertureFNumber": 1.8, // number: aperture f-number
      "isoEquivalent": 50, // integer: ISO value
      "exposureTime": "0.0025s" // string (Duration): exposure duration
    },
    "video": { // present only when media is a video
      "cameraMake": "Google", // string: camera brand
      "cameraModel": "Pixel 8", // string: camera model
      "fps": 29.97, // number: frames per second
      "status": "READY" // enum: processing status (UNSPECIFIED | PROCESSING | READY | FAILED)
    }
  },
  "contributorInfo": {
    "profilePictureBaseUrl": "https://lh3.googleusercontent.com/profile...", // string: contributor profile photo URL
    "displayName": "Alice Example" // string: contributor display name (only returned when searching by a shared album ID)
  }
}
```

## Listing media items in an album (`mediaItems.search`)

[https://developers.google.com/photos/library/reference/rest/v1/mediaItems/search](https://developers.google.com/photos/library/reference/rest/v1/mediaItems/search)

### Request

```jsonc
POST https://photoslibrary.googleapis.com/v1/mediaItems:search // HTTP POST endpoint
{
  "albumId": "ALBUM_ID", // string: list items from this album; omit when using filters
  "pageSize": 50, // integer: max items per page (default 25, max 100)
  "pageToken": "NEXT_TOKEN", // string: pagination cursor from previous response
  "filters": { // MUST be omitted when albumId is set
    "includeArchivedMedia": true, // boolean: include archived items when true
    "excludeNonAppCreatedData": false, // boolean: exclude items not created by this app
    "dateFilter": {
      "ranges": [
        {
          "startDate": { "year": 2024, "month": 7, "day": 1 }, // Date object: inclusive start
          "endDate": { "year": 2024, "month": 7, "day": 31 } // Date object: inclusive end
        }
      ]
    },
    "contentFilter": { // Not supported with orderBy
      "includedContentCategories": ["LANDSCAPES", "SUNSETS"], // ContentCategory enum values to include
      "excludedContentCategories": ["SCREENSHOTS"] // ContentCategory enum values to exclude
    },
    "mediaTypeFilter": { // Not supported with orderBy
      "mediaTypes": ["PHOTO"] // array must contain only one type (PHOTO or VIDEO) or ALL_MEDIA
    },
    "featureFilter": { // Not supported with orderBy
      "includedFeatures": ["FAVORITES"]
    }
  },
  "orderBy": "MediaMetadata.creation_time desc", // string: sort order valid only with dateFilter
}
```

### Response

```jsonc
{
  "mediaItems": [
    {
      "id": "MEDIA_ITEM_ID", // string: media identifier
      "description": "Sunset over Waikiki", // string: user description
      "productUrl": "https://photos.google.com/lr/photo/MEDIA_ITEM_ID", // string: signed-in URL
      "baseUrl": "https://lh3.googleusercontent.com/...", // string: base media download URL
      "mimeType": "image/jpeg", // string: MIME type
      "mediaMetadata": {
        "creationTime": "2024-07-15T18:30:25Z", // string (Timestamp): capture time
        "width": "4032", // string (int64): width in pixels
        "height": "3024" // string (int64): height in pixels
      },
      "filename": "IMG_20240715_183025.jpg"
    }
  ],
  "nextPageToken": "NEXT_TOKEN" // string: pagination cursor; omit when no more results
}
```
