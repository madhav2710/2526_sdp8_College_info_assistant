from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.services.system_service import (
    get_configuration_status,
    get_current_system_health,
    get_root_payload,
    list_public_colleges as list_public_colleges_payload,
    reset_current_system_health,
    validate_configuration,
)

router = APIRouter()


@router.get("/config/status")
async def get_config_status(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "super_admin":
        raise HTTPException(
            status_code=403, detail="Not authorized to view configuration status"
        )
    return get_configuration_status()


@router.post("/config/validate")
async def validate_config(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "super_admin":
        raise HTTPException(
            status_code=403, detail="Not authorized to validate configuration"
        )
    return validate_configuration()


@router.get("/system/health")
async def get_system_health(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["super_admin", "college_admin"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to view system health"
        )
    return await get_current_system_health()


@router.post("/system/health/reset")
async def reset_system_health(
    service_name: Optional[str] = None, current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "super_admin":
        raise HTTPException(
            status_code=403, detail="Not authorized to reset system health"
        )
    return await reset_current_system_health(service_name=service_name)


@router.get("/public/colleges")
async def list_public_colleges():
    return list_public_colleges_payload()


@router.get("/")
async def root():
    return get_root_payload()
