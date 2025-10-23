-- Media Scanner Database Schema
-- Version: 001
-- Description: Initial schema for media scanning and cataloging
--
-- TIMEZONE POLICY: All timestamps in this database use UTC with timezone info.
-- Application code MUST use datetime.now(timezone.utc) for ALL timestamp operations.
-- DO NOT use SQLite's CURRENT_TIMESTAMP (naive datetime) - always set timestamps explicitly from Python.

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL  -- Set explicitly from Python with timezone.utc
);

-- Scan runs tracking
CREATE TABLE IF NOT EXISTS scan_runs (
    scan_run_id TEXT PRIMARY KEY,  -- UUID4
    start_timestamp TIMESTAMP NOT NULL,  -- Set explicitly from Python with timezone.utc
    end_timestamp TIMESTAMP,
    status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
    
    -- Statistics
    total_files_discovered INTEGER DEFAULT 0 CHECK(total_files_discovered >= 0),
    media_files_discovered INTEGER DEFAULT 0 CHECK(media_files_discovered >= 0),
    metadata_files_discovered INTEGER DEFAULT 0 CHECK(metadata_files_discovered >= 0),
    media_files_with_metadata INTEGER DEFAULT 0 CHECK(media_files_with_metadata >= 0),
    media_files_processed INTEGER DEFAULT 0 CHECK(media_files_processed >= 0),
    metadata_files_processed INTEGER DEFAULT 0 CHECK(metadata_files_processed >= 0),
    media_new_files INTEGER DEFAULT 0 CHECK(media_new_files >= 0),
    media_unchanged_files INTEGER DEFAULT 0 CHECK(media_unchanged_files >= 0),
    media_changed_files INTEGER DEFAULT 0 CHECK(media_changed_files >= 0),
    missing_files INTEGER DEFAULT 0 CHECK(missing_files >= 0),
    media_error_files INTEGER DEFAULT 0 CHECK(media_error_files >= 0),
    inconsistent_files INTEGER DEFAULT 0 CHECK(inconsistent_files >= 0),
    albums_total INTEGER DEFAULT 0 CHECK(albums_total >= 0),
    
    -- Performance
    duration_seconds REAL CHECK(duration_seconds IS NULL OR duration_seconds >= 0),
    files_per_second REAL CHECK(files_per_second IS NULL OR files_per_second >= 0),
    
    -- Timestamp consistency
    CHECK(end_timestamp IS NULL OR end_timestamp >= start_timestamp)
);

CREATE TABLE IF NOT EXISTS albums (
    album_id TEXT PRIMARY KEY,  -- UUID5(namespace, album_folder_path)
    album_folder_path TEXT NOT NULL UNIQUE,  -- Normalized NFC
    google_album_id TEXT UNIQUE,  -- Google Photos API album ID (from API sync, NULL for Takeout-only)
    title TEXT,
    description TEXT,
    creation_timestamp TIMESTAMP,
    access_level TEXT,
    status TEXT NOT NULL CHECK(status IN ('present', 'error', 'missing')) DEFAULT 'present',
    first_seen_timestamp TIMESTAMP NOT NULL,  -- Set explicitly from Python with timezone.utc
    last_seen_timestamp TIMESTAMP NOT NULL,  -- Set explicitly from Python with timezone.utc
    scan_run_id TEXT NOT NULL,  -- References scan_runs(scan_run_id)
    
    -- Timestamp consistency
    CHECK(last_seen_timestamp >= first_seen_timestamp)
);

-- Media items
CREATE TABLE IF NOT EXISTS media_items (
    media_item_id TEXT PRIMARY KEY,  -- UUID4
    relative_path TEXT NOT NULL UNIQUE,  -- Normalized NFC
    album_id TEXT NOT NULL,  -- References albums(album_id), every file is in an album
    google_media_item_id TEXT UNIQUE,  -- Google Photos API media item ID (from API sync, NULL for Takeout-only)
    title TEXT,
    mime_type TEXT,
    file_size INTEGER NOT NULL CHECK(file_size >= 0),
    crc32 TEXT CHECK(crc32 IS NULL OR length(crc32) = 8),  -- 8 hex chars for CRC32
    content_fingerprint TEXT CHECK(content_fingerprint IS NULL OR length(content_fingerprint) = 64),  -- 64 hex chars for SHA-256
    sidecar_fingerprint TEXT CHECK(sidecar_fingerprint IS NULL OR length(sidecar_fingerprint) = 64),  -- 64 hex chars for SHA-256 of JSON sidecar
    
    -- Dimensions
    width INTEGER CHECK(width IS NULL OR width >= 0),
    height INTEGER CHECK(height IS NULL OR height >= 0),
    
    -- Video-specific
    duration_seconds REAL CHECK(duration_seconds IS NULL OR duration_seconds >= 0),
    frame_rate REAL CHECK(frame_rate IS NULL OR frame_rate > 0),
    
    -- Timestamps
    capture_timestamp TIMESTAMP,  -- When photo was taken (JSON > EXIF > filename > NULL)
    first_seen_timestamp TIMESTAMP NOT NULL,  -- Set explicitly from Python with timezone.utc
    last_seen_timestamp TIMESTAMP NOT NULL,  -- Set explicitly from Python with timezone.utc
    scan_run_id TEXT NOT NULL,  -- References scan_runs(scan_run_id)
    
    -- Status
    status TEXT NOT NULL CHECK(status IN ('present', 'missing', 'error', 'inconsistent')) DEFAULT 'present',
    
    -- Relationships
    original_media_item_id TEXT,  -- For edited variants (-edited suffix)
    live_photo_pair_id TEXT,  -- For Live Photos (HEIC+MOV pairs)
    
    -- EXIF metadata
    exif_datetime_original TIMESTAMP,
    exif_datetime_digitized TIMESTAMP,
    exif_gps_latitude REAL CHECK(exif_gps_latitude IS NULL OR (exif_gps_latitude >= -90 AND exif_gps_latitude <= 90)),
    exif_gps_longitude REAL CHECK(exif_gps_longitude IS NULL OR (exif_gps_longitude >= -180 AND exif_gps_longitude <= 180)),
    exif_gps_altitude REAL,
    exif_camera_make TEXT,
    exif_camera_model TEXT,
    exif_lens_make TEXT,
    exif_lens_model TEXT,
    exif_focal_length REAL,
    exif_f_number REAL,
    exif_exposure_time TEXT,
    exif_iso INTEGER CHECK(exif_iso IS NULL OR exif_iso >= 0),
    exif_orientation INTEGER CHECK(exif_orientation IS NULL OR (exif_orientation >= 1 AND exif_orientation <= 8)),
    exif_flash TEXT,
    exif_white_balance TEXT,
    
    -- Google Photos metadata
    google_description TEXT,
    google_geo_data_latitude REAL CHECK(google_geo_data_latitude IS NULL OR (google_geo_data_latitude >= -90 AND google_geo_data_latitude <= 90)),
    google_geo_data_longitude REAL CHECK(google_geo_data_longitude IS NULL OR (google_geo_data_longitude >= -180 AND google_geo_data_longitude <= 180)),
    google_geo_data_altitude REAL,
    google_geo_data_latitude_span REAL,
    google_geo_data_longitude_span REAL,
    media_google_url TEXT,  -- URL from Google Photos JSON sidecar
    
    -- Timestamp consistency
    CHECK(last_seen_timestamp >= first_seen_timestamp)
);

-- People (from Google Photos face tags)
CREATE TABLE IF NOT EXISTS people (
    person_id TEXT PRIMARY KEY,  -- UUID4
    person_name TEXT NOT NULL UNIQUE
);

-- People tags (many-to-many relationship)
CREATE TABLE IF NOT EXISTS people_tags (
    media_item_id TEXT NOT NULL,  -- References media_items(media_item_id)
    person_id TEXT NOT NULL,  -- References people(person_id)
    tag_order INTEGER NOT NULL CHECK(tag_order >= 0),  -- Position in array (0-based)
    PRIMARY KEY (media_item_id, person_id),
    UNIQUE (media_item_id, tag_order)
);

-- Processing errors
CREATE TABLE IF NOT EXISTS processing_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_run_id TEXT NOT NULL,  -- References scan_runs(scan_run_id)
    relative_path TEXT NOT NULL,
    error_type TEXT NOT NULL CHECK(error_type IN ('media_file', 'json_sidecar', 'album_metadata')),
    error_category TEXT NOT NULL CHECK(error_category IN ('permission_denied', 'corrupted', 'io_error', 'parse_error', 'unsupported_format')),
    error_message TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL  -- Set explicitly from Python with timezone.utc
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_media_items_path ON media_items(relative_path);
CREATE INDEX IF NOT EXISTS idx_media_items_google_id ON media_items(google_media_item_id);
CREATE INDEX IF NOT EXISTS idx_media_items_scan_run ON media_items(scan_run_id);
CREATE INDEX IF NOT EXISTS idx_media_items_status ON media_items(status);
CREATE INDEX IF NOT EXISTS idx_media_items_last_seen ON media_items(last_seen_timestamp);
CREATE INDEX IF NOT EXISTS idx_media_items_album ON media_items(album_id);
CREATE INDEX IF NOT EXISTS idx_media_items_duplicate ON media_items(file_size, crc32);
CREATE INDEX IF NOT EXISTS idx_media_items_fingerprint ON media_items(content_fingerprint);
CREATE INDEX IF NOT EXISTS idx_media_items_album_time ON media_items(album_id, capture_timestamp);
CREATE INDEX IF NOT EXISTS idx_media_items_original ON media_items(original_media_item_id);
CREATE INDEX IF NOT EXISTS idx_media_items_live_pair ON media_items(live_photo_pair_id);

CREATE INDEX IF NOT EXISTS idx_albums_path ON albums(album_folder_path);
CREATE INDEX IF NOT EXISTS idx_albums_google_id ON albums(google_album_id);
CREATE INDEX IF NOT EXISTS idx_albums_scan_run ON albums(scan_run_id);
CREATE INDEX IF NOT EXISTS idx_albums_status ON albums(status);

CREATE INDEX IF NOT EXISTS idx_errors_scan_run ON processing_errors(scan_run_id);
CREATE INDEX IF NOT EXISTS idx_errors_path ON processing_errors(relative_path);
CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON processing_errors(timestamp);
CREATE INDEX IF NOT EXISTS idx_errors_path_time ON processing_errors(relative_path, timestamp);

CREATE INDEX IF NOT EXISTS idx_people_tags_media ON people_tags(media_item_id);
CREATE INDEX IF NOT EXISTS idx_people_tags_person ON people_tags(person_id);

CREATE INDEX IF NOT EXISTS idx_media_items_google_url ON media_items(media_google_url);

-- Insert initial schema version
-- Note: applied_at will be set by migration.py after executing this script
-- We cannot use datetime('now') here as it creates naive datetime
-- Migration runner will update this timestamp with timezone-aware UTC
