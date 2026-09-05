from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, EmailStr


class AccountStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class CustomerTier(str, Enum):
    STANDARD = "standard"
    SILVER = "silver"
    GOLD = "gold"


class Customer(BaseModel):
    customer_id: str
    name: str
    email: EmailStr
    account_status: AccountStatus
    country: str
    customer_tier: CustomerTier = CustomerTier.STANDARD
