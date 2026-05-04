from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List




class TicketCreate(BaseModel):
    order_id: str
    subject: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    priority: Optional[str] = "medium"
    notify_email: Optional[bool] = False



class TicketOut(BaseModel):
    id: str
    order_id: str
    subject: str
    description: Optional[str]
    priority: str
    status: str
    notify_email: bool
    created_at: datetime

    class Config:
        from_attributes = True



class TicketListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[TicketOut]