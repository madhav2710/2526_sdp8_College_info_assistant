from typing import Optional

from pydantic import BaseModel


class CollegeCreateRequest(BaseModel):
    name: str
    code: str
    domain: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = True


class CollegeUpdateRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None
