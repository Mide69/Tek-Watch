"""Customer Pydantic models."""
from typing import List, Optional
from pydantic import BaseModel, EmailStr, field_validator
import re


class CustomerProfile(BaseModel):
    """Customer profile as stored in DynamoDB."""
    customer_id: str
    name: str
    email: Optional[str] = None
    subscription_tier: str
    aws_account_ids: List[str] = []
    status: str = "active"
    agent_status: str = "unknown"
    last_agent_seen: Optional[str] = None
    created_at: Optional[str] = None

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, v: str) -> str:
        if not re.match(r'^TT-\d{4}$', v):
            raise ValueError("customer_id must match TT-XXXX format")
        return v

    @field_validator("subscription_tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        allowed = {"foundation", "growth", "scale", "enterprise"}
        if v not in allowed:
            raise ValueError(f"subscription_tier must be one of {allowed}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"active", "suspended", "deleted"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class CreateCustomerRequest(BaseModel):
    name: str
    email: EmailStr
    subscription_tier: str = "foundation"
    aws_account_ids: List[str] = []

    @field_validator("subscription_tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        allowed = {"foundation", "growth", "scale", "enterprise"}
        if v not in allowed:
            raise ValueError(f"subscription_tier must be one of {allowed}")
        return v


class UpdateCustomerRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    subscription_tier: Optional[str] = None
    aws_account_ids: Optional[List[str]] = None
    status: Optional[str] = None


class CreateCustomerResponse(BaseModel):
    customer_id: str
    api_key: str
    message: str
    profile: CustomerProfile
