"""
Pydantic schemas for request/response validation.
Schemas define the structure of data exchanged via API.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


# ============== User Schemas ==============

class UserBase(BaseModel):
    """Base schema with common user attributes."""
    name: str
    email: EmailStr


class UserCreate(UserBase):
    """
    Schema for creating a new user.
    Only requires name and email.
    """
    pass


class UserResponse(UserBase):
    """
    Schema for user response data.
    Includes all user fields with timestamps.
    """
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """Schema for updating a user (partial update allowed)."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None


# ============== Health Check Schema ==============

class HealthResponse(BaseModel):
    """Schema for health check endpoint response."""
    status: str
    database: str
    version: str
