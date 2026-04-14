from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.schemas.auth import SetCollegeRequest
from app.services.account_service import (
    get_user_profile_for_current_user,
    set_user_college_for_current_user,
)

router = APIRouter()


@router.get("/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    return get_user_profile_for_current_user(current_user=current_user)


@router.post("/user/set-college")
async def set_user_college(
    request: SetCollegeRequest,
    current_user: dict = Depends(get_current_user),
):
    return set_user_college_for_current_user(request=request, current_user=current_user)
