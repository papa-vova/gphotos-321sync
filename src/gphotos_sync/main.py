"""Main entry point for gphotos-sync application."""

import sys
from .config import get_config
from .logging_config import setup_logging, get_logger


def main() -> int:
    """Main application entry point."""
    try:
        # Load configuration
        config = get_config()

        # Setup logging
        setup_logging()
        logger = get_logger(__name__)

        logger.info(
            "Starting gphotos-sync",
            extra={
                "extra_fields": {
                    "version": config.app.version,
                    "mode": config.deployment.mode,
                    "environment": config.deployment.environment,
                }
            },
        )

        # Import here to avoid circular dependencies
        from .api.server import create_app
        import uvicorn

        # Create FastAPI app
        app = create_app(config)

        # Start server
        logger.info(
            "Starting API server",
            extra={
                "extra_fields": {
                    "host": config.api.host,
                    "port": config.api.port,
                    "workers": config.api.workers,
                }
            },
        )

        uvicorn.run(
            app,
            host=config.api.host,
            port=config.api.port,
            reload=config.api.reload,
            workers=config.api.workers,
            log_config=None,  # Use our custom logging
        )

        return 0

    except KeyboardInterrupt:
        logger = get_logger(__name__)
        logger.info("Application interrupted by user")
        return 0

    except Exception as e:
        logger = get_logger(__name__)
        logger.error("Application failed to start", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
