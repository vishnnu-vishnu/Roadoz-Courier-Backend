from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PermissionCreateRequest(BaseModel):
    code: str
    module: str
    action: str
    description: Optional[str] = None
    is_active: bool = True


class PermissionUpdateRequest(BaseModel):
    module: Optional[str] = None
    action: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PermissionOut(BaseModel):
    id: str
    code: str
    module: str
    action: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
