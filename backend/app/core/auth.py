from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.database import supabase

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    if not supabase:
         raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
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
        
        # Get profile for role
        user_id = user.id
        profile_response = supabase.table("profiles").select("role, college_id").eq("id", user_id).execute()
        
        if not profile_response.data:
             raise HTTPException(status_code=404, detail="User profile not found")
             
        profile = profile_response.data[0]
        
        return {
            "user_id": user_id,
            "role": profile["role"],
            "college_id": profile["college_id"]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
