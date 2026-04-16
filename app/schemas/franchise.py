from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class FranchiseCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    address: Optional[str] = None
    franchise_code: str


class FranchiseUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class FranchiseResponse(BaseModel):
    id: str
    user_id: str
    franchise_code: str
    name: str
    email: str
    phone: Optional[str]
    address: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FranchiseListResponse(BaseModel):
    items: List[FranchiseResponse]
    total: int
    page: int
    limit: int
    pages: int
