from typing import Optional

from pydantic import BaseModel, EmailStr


class AdminCreateRequest(BaseModel):
    name: str
    email: EmailStr
    college_id: str
    password: str


class AdminUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    college_id: Optional[str] = None


class AdminStatusUpdateRequest(BaseModel):
    status: str
