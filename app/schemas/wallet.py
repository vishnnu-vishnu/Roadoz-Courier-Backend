from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TransactionType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


# ── Wallet ────────────────────────────────────────────────────────────────


class WalletOut(BaseModel):
    id: str
    franchise_id: str
    balance: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Wallet Transaction ───────────────────────────────────────────────────


class WalletTransactionOut(BaseModel):
    id: str
    wallet_id: str
    order_id: Optional[str] = None
    amount: float
    type: str
    opening_balance: float
    closing_balance: float
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WalletTransactionListResponse(BaseModel):
    items: List[WalletTransactionOut]
    total: int
    page: int
    limit: int
    pages: int


# ── Requests ─────────────────────────────────────────────────────────────


class WalletRechargeRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Recharge amount (must be positive)")
    description: Optional[str] = Field(None, max_length=500, description="Optional note for the recharge")


class WalletAdminAdjustRequest(BaseModel):
    franchise_id: str = Field(..., description="Franchise to adjust wallet for")
    amount: float = Field(..., gt=0, description="Adjustment amount")
    type: TransactionType = Field(..., description="credit or debit")
    description: str = Field(..., min_length=1, max_length=500)
