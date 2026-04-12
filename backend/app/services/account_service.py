from typing import Any

from fastapi import HTTPException

from app.core.database import get_service_client, supabase
from app.schemas.auth import LoginRequest, SetCollegeRequest, SignupRequest


def _extract_auth_user(auth_response: Any) -> Any:
    if hasattr(auth_response, "user") and auth_response.user:
        return auth_response.user
    if hasattr(auth_response, "data") and auth_response.data:
        if isinstance(auth_response.data, dict):
            return auth_response.data.get("user")
        return getattr(auth_response.data, "user", None)
    return None


def _extract_auth_user_id(user: Any) -> str:
    raw_user_id = getattr(user, "id", None)
    if raw_user_id is None and isinstance(user, dict):
        raw_user_id = user.get("id")
    if raw_user_id is None:
        raise HTTPException(status_code=500, detail="Auth user record is missing an id")
    return str(raw_user_id)


def _extract_auth_user_email(auth_user_response: Any) -> str | None:
    auth_user = getattr(auth_user_response, "user", None)
    if auth_user is not None:
        return getattr(auth_user, "email", None)

    if isinstance(auth_user_response, dict) and "user" in auth_user_response:
        user_data = auth_user_response["user"]
        if isinstance(user_data, dict):
            return user_data.get("email")

    response_data = getattr(auth_user_response, "data", None)
    if isinstance(response_data, dict) and "user" in response_data:
        data_user = response_data["user"]
        if isinstance(data_user, dict):
            return data_user.get("email")
    if response_data is not None:
        return getattr(response_data, "email", None)

    return None


def signup_user_account(request: SignupRequest) -> dict[str, Any]:
    try:
        try:
            auth_response = supabase.auth.sign_up(
                {
                    "email": request.email,
                    "password": request.password,
                }
            )
        except Exception as exc:
            message = str(exc)
            if (
                "User already registered" in message
                or "email_already_in_use" in message
                or "already registered" in message.lower()
            ):
                raise HTTPException(
                    status_code=400, detail="An account with this email already exists"
                ) from exc
            raise

        user = _extract_auth_user(auth_response)
        if not user:
            raise HTTPException(status_code=500, detail="Failed to create auth user")

        user_id = _extract_auth_user_id(user)
        client = get_service_client()

        college_id = None
        if request.college_id:
            college_check = (
                client.table("colleges")
                .select("id")
                .eq("id", request.college_id)
                .limit(1)
                .execute()
            )
            if not (college_check.data or []):
                raise HTTPException(status_code=400, detail="Invalid college selected")
            college_id = request.college_id

        client.table("profiles").insert(
            {
                "id": user_id,
                "full_name": request.full_name,
                "role": "student",
                "college_id": college_id,
            }
        ).execute()

        return {
            "message": "Signup successful! Please check your email to confirm your account before logging in.",
            "email_sent": True,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Signup failed: {str(exc)}"
        ) from exc


def login_user_account(request: LoginRequest) -> dict[str, Any]:
    try:
        auth_response = supabase.auth.sign_in_with_password(
            {"email": request.email, "password": request.password}
        )

        user_id = auth_response.user.id
        user_email = auth_response.user.email
        profile_response = (
            supabase.table("profiles")
            .select("role, college_id, full_name")
            .eq("id", user_id)
            .execute()
        )

        if not profile_response.data:
            raise HTTPException(status_code=404, detail="User profile not found")

        profile = profile_response.data[0]

        return {
            "access_token": auth_response.session.access_token,
            "token_type": "bearer",
            "user_id": user_id,
            "email": user_email,
            "full_name": profile.get("full_name"),
            "role": profile["role"],
            "college_id": profile["college_id"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        if "Invalid login credentials" in str(exc):
            raise HTTPException(
                status_code=401, detail="Invalid login credentials"
            ) from exc
        raise HTTPException(
            status_code=400,
            detail="Login failed due to a server error. Please try again.",
        ) from exc


def get_user_profile_for_current_user(current_user: dict[str, Any]) -> dict[str, Any]:
    try:
        client = get_service_client()
        user_id = current_user["user_id"]

        user_email = None
        try:
            auth_user_response = client.auth.admin.get_user_by_id(user_id)
            user_email = _extract_auth_user_email(auth_user_response)
        except Exception:
            user_email = None

        profile_query = (
            client.table("profiles")
            .select("full_name, role, college_id")
            .eq("id", user_id)
            .execute()
        )

        if not profile_query.data:
            raise HTTPException(status_code=404, detail="User profile not found")

        profile = profile_query.data[0]
        college_name = None

        if profile.get("college_id"):
            college_query = (
                client.table("colleges")
                .select("name")
                .eq("id", profile["college_id"])
                .execute()
            )
            if college_query.data:
                college_name = college_query.data[0]["name"]

        return {
            "user_id": user_id,
            "email": user_email,
            "full_name": profile.get("full_name"),
            "role": profile["role"],
            "college_id": profile.get("college_id"),
            "college_name": college_name,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch user profile: {str(exc)}"
        ) from exc


def set_user_college_for_current_user(
    request: SetCollegeRequest, current_user: dict[str, Any]
) -> dict[str, str]:
    try:
        client = get_service_client()
        user_id = current_user["user_id"]

        college_check = (
            client.table("colleges")
            .select("id")
            .eq("id", request.college_id)
            .limit(1)
            .execute()
        )
        if not (college_check.data or []):
            raise HTTPException(status_code=400, detail="Invalid college selected")

        client.table("profiles").update({"college_id": request.college_id}).eq(
            "id", user_id
        ).execute()
        return {"status": "success", "college_id": request.college_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to set college: {str(exc)}"
        ) from exc
