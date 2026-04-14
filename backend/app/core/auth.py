import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.database import supabase

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
logger = logging.getLogger(__name__)

ACTIVE_PROFILE_STATUS = "active"
DISABLED_ACCOUNT_DETAIL = "User account is disabled"


def _normalize_profile_status(raw_status: object) -> str | None:
    if raw_status is None:
        return None
    return str(raw_status).strip().lower()


def ensure_profile_is_active(profile: dict, user_id: str) -> None:
    normalized_status = _normalize_profile_status(profile.get("status"))
    if normalized_status == ACTIVE_PROFILE_STATUS:
        return

    if normalized_status is None:
        logger.warning("Profile %s is missing a status value; denying access", user_id)
    elif normalized_status == "disabled":
        logger.info("Denied access for disabled profile %s", user_id)
    else:
        logger.warning(
            "Profile %s has unsupported status %r; denying access",
            user_id,
            profile.get("status"),
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=DISABLED_ACCOUNT_DETAIL,
    )


async def get_current_user(token: str = Depends(oauth2_scheme)):
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )

    try:
        # Verify token using Supabase Auth
        user_response = supabase.auth.get_user(token)
        user = user_response.user

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get profile for role / status enforcement
        user_id = user.id
        profile_response = (
            supabase.table("profiles")
            .select("role, college_id, status")
            .eq("id", user_id)
            .execute()
        )

        if not profile_response.data:
            raise HTTPException(status_code=404, detail="User profile not found")

        profile = profile_response.data[0]
        ensure_profile_is_active(profile, user_id)

        return {
            "user_id": user_id,
            "role": profile["role"],
            "college_id": profile["college_id"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
