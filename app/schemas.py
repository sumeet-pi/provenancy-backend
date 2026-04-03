"""
Pydantic schemas for request/response validation.
Schemas define the structure of data exchanged via API.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict


# ============== Enums ==============

class UserRole(str, Enum):
    """User role enumeration."""
    STUDENT = "student"
    SUPERVISOR = "supervisor"


class TrustTier(str, Enum):
    """Trust tier enumeration."""
    INSTITUTIONAL = "institutional"
    INDEPENDENT = "independent"


# ============== Authentication Schemas ==============

class UserSignupRequest(BaseModel):
    """Schema for user signup request."""
    full_name: str
    email: EmailStr
    password: str
    role: UserRole


class UserLoginRequest(BaseModel):
    """Schema for user login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    ledger_id: str


# ============== User Schemas ==============

class UserResponse(BaseModel):
    """Schema for user response data."""
    id: UUID
    email: EmailStr
    role: UserRole
    ledger_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============== Profile Schemas ==============

class StudentProfileResponse(BaseModel):
    """Schema for student profile response."""
    id: UUID
    user_id: UUID
    full_name: str
    title: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    institution: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupervisorProfileResponse(BaseModel):
    """Schema for supervisor profile response."""
    id: UUID
    user_id: UUID
    full_name: str
    designation: Optional[str] = None
    organization: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    email_domain: str
    trust_tier: TrustTier
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============== Complete Response Schemas ==============

class StudentCompleteResponse(BaseModel):
    """Complete response for student including user and profile data."""
    user: UserResponse
    profile: StudentProfileResponse
    profile_complete: bool


class SupervisorCompleteResponse(BaseModel):
    """Complete response for supervisor including user and profile data."""
    user: UserResponse
    profile: SupervisorProfileResponse
    profile_complete: bool


# ============== Profile Completion Schemas ==============

class CompleteProfileRequest(BaseModel):
    """Schema for completing/updating profile (works for both roles)."""
    institution: Optional[str] = None
    bio: Optional[str] = None
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    organization: Optional[str] = None
    designation: Optional[str] = None


class CompleteProfileResponse(BaseModel):
    """Schema for complete profile response."""
    message: str
    profile: StudentProfileResponse | SupervisorProfileResponse


class LogoutResponse(BaseModel):
    """Schema for logout response."""
    message: str


# ============== Health Check Schema ==============

class HealthResponse(BaseModel):
    """Schema for health check endpoint response."""
    status: str
    database: str
    version: str