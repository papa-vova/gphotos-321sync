"""FastAPI server setup."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ..config.schema import Config
from ..logging_config import get_logger

logger = get_logger(__name__)


def create_app(config: Config) -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=config.app.name,
        version=config.app.version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS middleware
    if config.api.enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.api.cors_origins or ["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Register routes
    from .routes import health

    app.include_router(health.router, prefix="/api", tags=["health"])

    logger.info(
        "FastAPI application created",
        extra={"extra_fields": {"app_name": config.app.name, "version": config.app.version}},
    )

    return app
