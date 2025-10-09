"""Configuration schema definitions using Pydantic."""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, List
from pathlib import Path
import platformdirs
import os


class AppConfig(BaseModel):
    name: str
    version: str


class DeploymentConfig(BaseModel):
    mode: Literal["local", "hybrid", "cloud_only"]
    environment: Literal["production", "development", "testing"]


class PathsConfig(BaseModel):
    takeout_archives: str
    working_directory: str
    database_path: str
    config_directory: str
    log_directory: str
    cache_directory: str
    temp_directory: str

    @field_validator("*", mode="before")
    @classmethod
    def expand_path_variables(cls, v: str) -> str:
        """Expand ${VAR} in paths."""
        if not isinstance(v, str):
            return v

        import tempfile

        replacements = {
            "${USER_HOME}": str(Path.home()),
            "${USER_DATA}": platformdirs.user_data_dir(),
            "${USER_CONFIG}": platformdirs.user_config_dir(),
            "${USER_CACHE}": platformdirs.user_cache_dir(),
            "${USER_LOGS}": platformdirs.user_log_dir(),
            "${TEMP}": tempfile.gettempdir(),
        }

        for var, value in replacements.items():
            v = v.replace(var, value)

        return v

    @model_validator(mode="after")
    def create_directories(self) -> "PathsConfig":
        """Ensure all directories exist."""
        for field_name in self.model_fields:
            value = getattr(self, field_name)
            if field_name.endswith("_directory") or field_name == "working_directory":
                Path(value).mkdir(parents=True, exist_ok=True)
            elif field_name == "database_path":
                Path(value).parent.mkdir(parents=True, exist_ok=True)
        return self


class ResourcesConfig(BaseModel):
    max_cpu_percent: float = Field(ge=1.0, le=100.0)
    max_workers: int = Field(ge=0)
    io_workers: int = Field(ge=0)
    max_memory_percent: float = Field(ge=1.0, le=100.0)
    max_memory_mb: int = Field(ge=0)
    max_concurrent_reads: int = Field(ge=1)
    max_disk_io_mbps: float = Field(ge=1.0)
    resource_check_interval_seconds: float = Field(ge=0.1)
    enable_adaptive_throttling: bool

    @field_validator("max_workers")
    @classmethod
    def auto_detect_max_workers(cls, v: int) -> int:
        """0 means auto-detect."""
        if v == 0:
            cpu_count = os.cpu_count() or 4
            return max(2, cpu_count - 2)
        return v

    @field_validator("io_workers")
    @classmethod
    def auto_detect_io_workers(cls, v: int) -> int:
        """0 means auto-detect."""
        if v == 0:
            cpu_count = os.cpu_count() or 4
            return max(4, cpu_count * 3)
        return v


class ProcessingConfig(BaseModel):
    batch_size: int = Field(ge=1)
    chunk_size: int = Field(ge=1)
    enable_parallel_processing: bool
    backup_originals: bool
    verify_integrity: bool


class ExtractionConfig(BaseModel):
    extract_to_temp: bool
    cleanup_after_extraction: bool
    verify_checksums: bool
    supported_formats: List[str]
    max_retry_attempts: int = Field(ge=1, default=10)
    initial_retry_delay_seconds: float = Field(ge=0.1)
    enable_resume: bool
    state_file: str
    verify_extracted_files: bool


class MetadataConfig(BaseModel):
    conflict_resolution: Literal["google_json_priority", "exif_priority", "manual"]
    embed_gps: bool
    embed_timestamps: bool
    embed_camera_info: bool
    preserve_original_dates: bool
    supported_image_formats: List[str]
    supported_video_formats: List[str]


class SQLiteConfig(BaseModel):
    journal_mode: str
    synchronous: str
    cache_size_kb: int


class PostgreSQLConfig(BaseModel):
    host: str
    port: int
    database: str
    username: str
    password: str
    ssl_mode: str
    pool_size: int
    max_overflow: int


class DatabaseConfig(BaseModel):
    type: Literal["sqlite", "postgresql"]
    connection_pool_size: int
    connection_timeout_seconds: float
    enable_wal_mode: bool
    backup_enabled: bool
    backup_interval_hours: int
    sqlite: SQLiteConfig
    postgresql: PostgreSQLConfig


class WebSocketConfig(BaseModel):
    ping_interval_seconds: float
    ping_timeout_seconds: float
    max_connections: int


class APIConfig(BaseModel):
    host: str
    port: int = Field(ge=1, le=65535)
    reload: bool
    workers: int = Field(ge=1)
    enable_cors: bool
    cors_origins: List[str]
    enable_compression: bool
    max_upload_size_mb: int
    websocket: WebSocketConfig


class S3Config(BaseModel):
    bucket: str
    region: str
    access_key_id: str
    secret_access_key: str
    endpoint_url: str
    use_ssl: bool


class GCSConfig(BaseModel):
    bucket: str
    project_id: str
    credentials_file: str


class StorageConfig(BaseModel):
    provider: Literal["local", "s3", "gcs", "azure"]
    enable_encryption: bool
    s3: S3Config
    gcs: GCSConfig


class RedisConfig(BaseModel):
    host: str
    port: int
    db: int
    password: str
    ssl: bool


class SQSConfig(BaseModel):
    region: str
    queue_url: str
    access_key_id: str
    secret_access_key: str


class QueueConfig(BaseModel):
    backend: Literal["none", "redis", "sqs", "rabbitmq"]
    result_backend: str
    redis: RedisConfig
    sqs: SQSConfig


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    format: Literal["simple", "detailed", "json"]
    enable_file_logging: bool
    enable_console_logging: bool
    max_file_size_mb: int
    backup_count: int
    log_to_syslog: bool


class MonitoringConfig(BaseModel):
    enable_performance_tracking: bool
    enable_profiling: bool
    profile_threshold_seconds: float
    metrics_export_interval_seconds: float


class UIConfig(BaseModel):
    theme: Literal["light", "dark", "auto"]
    language: str
    enable_animations: bool
    items_per_page: int


class GalleryConfig(BaseModel):
    thumbnail_size: int
    thumbnail_quality: int = Field(ge=1, le=100)
    enable_lazy_loading: bool
    group_by: Literal["year", "month", "day", "album"]


class SecurityConfig(BaseModel):
    enable_authentication: bool
    session_timeout_minutes: int
    enable_rate_limiting: bool
    rate_limit_requests_per_minute: int


class FeaturesConfig(BaseModel):
    enable_face_detection: bool
    enable_duplicate_detection: bool
    enable_auto_tagging: bool
    enable_cloud_sync: bool
    enable_sharing: bool


class DevelopmentConfig(BaseModel):
    enable_debug_mode: bool
    enable_hot_reload: bool
    mock_external_services: bool


class Config(BaseModel):
    """Root configuration model."""

    app: AppConfig
    deployment: DeploymentConfig
    paths: PathsConfig
    resources: ResourcesConfig
    processing: ProcessingConfig
    extraction: ExtractionConfig
    metadata: MetadataConfig
    database: DatabaseConfig
    api: APIConfig
    storage: StorageConfig
    queue: QueueConfig
    logging: LoggingConfig
    monitoring: MonitoringConfig
    ui: UIConfig
    gallery: GalleryConfig
    security: SecurityConfig
    features: FeaturesConfig
    development: DevelopmentConfig

    model_config = {"validate_assignment": True}
