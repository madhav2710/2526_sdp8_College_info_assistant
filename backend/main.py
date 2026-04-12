import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import (
    ConfigurationError,
    get_system_config,
    validate_startup_configuration,
)
from app.routers import admin, auth, chat, notifications, superadmin, system, user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    try:
        validate_startup_configuration()
        system_config = get_system_config()
        logger.info(
            "Configuration validated successfully: %s v%s",
            system_config.application.app_name,
            system_config.application.app_version,
        )
        logging.getLogger().setLevel(system_config.application.log_level.value)

        if not system_config.ai.gemini_api_key:
            logger.warning(
                "GEMINI_API_KEY not configured - RAG functionality will be limited"
            )
        else:
            logger.info("RAG system fully configured and ready")
    except ConfigurationError as exc:
        logger.error("Configuration validation failed: %s", str(exc))
        logger.error("Application startup failed due to invalid configuration")
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error during configuration validation: %s", str(exc))
        logger.error("Application startup failed")
        raise SystemExit(1) from exc

    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, tags=["Auth"])
    app.include_router(user.router, tags=["User"])
    app.include_router(chat.router, tags=["Chat"])
    app.include_router(admin.router, tags=["Admin"])
    app.include_router(superadmin.router, tags=["Super Admin"])
    app.include_router(notifications.router, tags=["Notifications"])
    app.include_router(system.router, tags=["System"])

    return app


app = create_app()
