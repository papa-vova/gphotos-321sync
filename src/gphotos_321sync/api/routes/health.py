"""Health check endpoints."""

from fastapi import APIRouter
from ...logging_config import get_logger
from ...config import get_config

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    config = get_config()

    logger.debug("Health check requested")

    return {
        "status": "healthy",
        "version": config.app.version,
        "mode": config.deployment.mode,
    }


@router.get("/config")
async def get_configuration():
    """Get current configuration (sanitized)."""
    config = get_config()

    logger.debug("Configuration requested")

    # Sanitize sensitive values
    config_dict = config.model_dump()
    config_dict["database"]["postgresql"]["password"] = "***"
    config_dict["storage"]["s3"]["secret_access_key"] = "***"
    config_dict["queue"]["redis"]["password"] = "***"

    return config_dict
