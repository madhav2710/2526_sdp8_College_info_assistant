import logging

from app.core.config import (
    ConfigurationError,
    get_system_config,
    validate_startup_configuration,
)
from app.routers import admin, auth, chat, notifications, superadmin, system, user
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    validate_startup_configuration()
    system_config = get_system_config()
    logger.info(
        "Configuration validated successfully: %s v%s",
        system_config.application.app_name,
        system_config.application.app_version,
    )
    logging.getLogger().setLevel(system_config.application.log_level.value)
except ConfigurationError as e:
    logger.error("Configuration validation failed: %s", str(e))
    raise SystemExit(1)

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
