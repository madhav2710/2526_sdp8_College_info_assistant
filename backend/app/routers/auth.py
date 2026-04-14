from fastapi import APIRouter

from app.schemas.auth import LoginRequest, SignupRequest
from app.services.account_service import login_user_account, signup_user_account

router = APIRouter()


@router.post("/auth/signup")
async def signup(request: SignupRequest):
    return signup_user_account(request=request)


@router.post("/auth/login")
async def login(request: LoginRequest):
    return login_user_account(request=request)
