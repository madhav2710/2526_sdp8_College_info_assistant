import datetime as dt
import logging
from typing import Any, Optional

from fastapi import HTTPException

from app.core.database import get_service_client

logger = logging.getLogger(__name__)


def _timestamp() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def get_configuration_status() -> dict[str, Any]:
    try:
        from app.core.config import get_config_manager

        config_manager = get_config_manager()
        summary = config_manager.get_config_summary()

        return {
            "status": "success",
            "configuration_status": summary["status"],
            "validation_errors": summary.get("validation_errors", []),
            "config_summary": summary.get("config", {}),
            "timestamp": _timestamp(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve configuration status"
        ) from exc


def validate_configuration() -> dict[str, Any]:
    try:
        from app.core.config import get_config_manager

        config_manager = get_config_manager()
        validation_errors = config_manager.validate_current_config()

        return {
            "status": "success",
            "is_valid": len(validation_errors) == 0,
            "validation_errors": validation_errors,
            "error_count": len(validation_errors),
            "timestamp": _timestamp(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to validate configuration"
        ) from exc


async def get_current_system_health() -> dict[str, Any]:
    try:
        from app.core.rag import get_rag_system_health

        health_status = await get_rag_system_health()
        return {
            "status": "success",
            "system_health": health_status,
            "timestamp": _timestamp(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve system health"
        ) from exc


async def reset_current_system_health(
    service_name: Optional[str] = None,
) -> dict[str, Any]:
    try:
        from app.core.rag import reset_service_health

        if service_name is None:
            result = await reset_service_health()
        else:
            result = await reset_service_health(service_name)

        return {
            "status": "success",
            "reset_result": result,
            "timestamp": _timestamp(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="Failed to reset system health"
        ) from exc


def list_public_colleges() -> dict[str, list[dict[str, Any]]]:
    try:
        client = get_service_client()
        response = (
            client.table("colleges")
            .select("id, name, domain, code")
            .order("name")
            .execute()
        )
        return {"colleges": response.data or []}
    except Exception as exc:
        logger.exception("Failed to load public colleges")
        raise HTTPException(
            status_code=500, detail="Failed to load colleges"
        ) from exc


def get_root_payload() -> dict[str, str]:
    from app.core.config import get_system_config

    config = get_system_config()
    return {
        "app": config.application.app_name,
        "status": "ok",
        "version": config.application.app_version,
    }
