"""
Pydantic schemas for request/response validation.
Schemas define the structure of data exchanged via API.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, field_serializer


# ============== Enums ==============

class EngagementStatus(str, Enum):
    """Engagement status enumeration."""
    DRAFT = "draft"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EDIT_REQUESTED = "edit_requested"


class VerificationType(str, Enum):
    """Verification type enumeration."""
    INSTITUTIONAL = "institutional"
    INDEPENDENT = "independent"


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

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        """
        Validate full_name: trim whitespace, reject empty/whitespace-only,
        and enforce max length of 150 characters.
        """
        v = v.strip()
        if not v:
            raise ValueError("Full name cannot be empty")
        if len(v) > 150:
            raise ValueError("Full name must not exceed 150 characters")
        return v


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


# ============== Student Profile Update Schemas ==============

class StudentProfileUpdateRequest(BaseModel):
    """Schema for updating student profile."""
    full_name: Optional[str] = None
    title: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    institution: Optional[str] = None

    @field_validator("full_name", "title", "bio", "linkedin_url", "institution")
    @classmethod
    def trim_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
        return v

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            if not v.startswith(("http://", "https://")):
                raise ValueError("LinkedIn URL must start with http:// or https://")
            if "linkedin.com" not in v.lower():
                raise ValueError("LinkedIn URL must be a valid LinkedIn URL")
        return v


class StudentProfileUpdateResponse(BaseModel):
    """Schema for student profile update response."""
    message: str
    profile: "StudentProfileResponse"
    profile_complete: bool
    ledger_id: str


# ============== Student Public Profile Schemas ==============

class StudentPublicResponse(BaseModel):
    """Schema for public student profile view."""
    id: UUID
    ledger_id: str
    full_name: str
    title: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    institution: Optional[str] = None
    created_at: datetime
    verified_engagements: List["VerifiedEngagementPublic"] = []

    model_config = ConfigDict(from_attributes=True)


class VerifiedEngagementPublic(BaseModel):
    """Schema for verified engagement in public view."""
    id: UUID
    organization_name: str
    role: str
    start_date: datetime
    end_date: Optional[datetime] = None
    verification_type: Optional[VerificationType] = None
    verified_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============== Supervisor Profile Update Schemas ==============

class SupervisorProfileUpdateRequest(BaseModel):
    """Schema for updating supervisor profile."""
    full_name: Optional[str] = None
    designation: Optional[str] = None
    organization: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None

    @field_validator("full_name", "designation", "organization", "bio", "linkedin_url")
    @classmethod
    def trim_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
        return v

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            if not v.startswith(("http://", "https://")):
                raise ValueError("LinkedIn URL must start with http:// or https://")
            if "linkedin.com" not in v.lower():
                raise ValueError("LinkedIn URL must be a valid LinkedIn URL")
        return v


class SupervisorProfileUpdateResponse(BaseModel):
    """Schema for supervisor profile update response."""
    message: str
    profile: "SupervisorProfileResponse"
    profile_complete: bool
    ledger_id: str


# ============== Supervisor Public Profile Schemas ==============

class VerifiedEngagementSupervisorPublic(BaseModel):
    """Schema for verified engagement in supervisor public view."""
    id: UUID
    student_full_name: str
    organization_name: str
    role: str
    start_date: datetime
    end_date: Optional[datetime] = None
    verification_type: Optional[VerificationType] = None
    verified_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SupervisorPublicResponse(BaseModel):
    """Schema for public supervisor profile view."""
    id: UUID
    ledger_id: str
    full_name: str
    designation: Optional[str] = None
    organization: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    trust_tier: TrustTier
    created_at: datetime
    verified_engagements: List["VerifiedEngagementSupervisorPublic"] = []

    model_config = ConfigDict(from_attributes=True)


# Update forward references
StudentProfileUpdateResponse.model_rebuild()
StudentPublicResponse.model_rebuild()
SupervisorProfileUpdateResponse.model_rebuild()
SupervisorPublicResponse.model_rebuild()


# ============== Health Check Schema ==============

class HealthResponse(BaseModel):
    """Schema for health check endpoint response."""
    status: str
    database: str
    version: str


# ============== Skill Schemas ==============

class SkillCreate(BaseModel):
    """Schema for creating a declared skill."""
    name: str
    category: Optional[str] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Skill name cannot be empty")
        if len(v) < 2 or len(v) > 50:
            raise ValueError("Skill name must be between 2 and 50 characters")
        return v


class SkillResponse(BaseModel):
    """Schema for skill response."""
    id: UUID
    name: str
    category: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeclaredSkillResponse(BaseModel):
    """Schema for declared skill response."""
    id: UUID
    skill: SkillResponse

    model_config = ConfigDict(from_attributes=True)


class SkillListResponse(BaseModel):
    """Schema for skill list response."""
    declared: List[SkillResponse] = []
    verified: List[SkillResponse] = []


class PublicSkillResponse(BaseModel):
    """Schema for public skill response."""
    declared: List[SkillResponse] = []
    verified: List[SkillResponse] = []


# ============== Engagement Schemas ==============

class EngagementCreate(BaseModel):
    """Schema for creating an engagement."""
    organization_name: str
    role: str
    start_date: datetime
    end_date: Optional[datetime] = None
    summary: Optional[str] = None
    highlights: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    links: Optional[List[str]] = None

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            words = v.split()
            if not (150 <= len(words) <= 250):
                raise ValueError("Summary must be between 150 and 250 words")
        return v

    @field_validator("highlights")
    @classmethod
    def validate_highlights(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None and len(v) > 5:
            raise ValueError("Highlights must have at most 5 items")
        return v

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None and len(v) > 5:
            raise ValueError("Skills must have at most 5 items")
        return v

    @field_validator("links")
    @classmethod
    def validate_links(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            for link in v:
                if link and not (link.startswith("http://") or link.startswith("https://")):
                    raise ValueError("Links must be valid URLs starting with http:// or https://")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: Optional[datetime], info) -> Optional[datetime]:
        start_date = info.data.get("start_date")
        if start_date is not None and v is not None and v < start_date:
            raise ValueError("End date must be after or equal to start date")
        return v


class EngagementUpdate(BaseModel):
    """
    Schema for updating an engagement. All fields are optional for partial updates.

    Note: Cannot modify engagement if status = "verified" (enforced at API layer, not schema).
    """
    organization_name: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    summary: Optional[str] = None
    highlights: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    links: Optional[List[str]] = None

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            words = v.split()
            if not (150 <= len(words) <= 250):
                raise ValueError("Summary must be between 150 and 250 words")
        return v

    @field_validator("highlights")
    @classmethod
    def validate_highlights(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None and len(v) > 5:
            raise ValueError("Highlights must have at most 5 items")
        return v

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None and len(v) > 5:
            raise ValueError("Skills must have at most 5 items")
        return v

    @field_validator("links")
    @classmethod
    def validate_links(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            for link in v:
                if link and not (link.startswith("http://") or link.startswith("https://")):
                    raise ValueError("Links must be valid URLs starting with http:// or https://")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: Optional[datetime], info) -> Optional[datetime]:
        start_date = info.data.get("start_date")
        if start_date is not None and v is not None and v < start_date:
            raise ValueError("End date must be after or equal to start date")
        return v


class EngagementResponse(BaseModel):
    """Schema for engagement response."""
    id: UUID
    student_profile_id: UUID
    supervisor_profile_id: Optional[UUID] = None
    supervisor_ref: Optional[str] = None
    organization_name: str
    role: str
    start_date: datetime
    end_date: Optional[datetime] = None
    summary: Optional[str] = None
    highlights: Optional[List[str]] = None
    links: Optional[List[str]] = None
    status: EngagementStatus
    rejection_reason: Optional[str] = None
    verified_at: Optional[datetime] = None
    block_hash: Optional[str] = None
    verification_type: Optional[VerificationType] = None
    created_at: datetime
    updated_at: datetime
    skills: List[SkillResponse] = []

    model_config = ConfigDict(from_attributes=True)


class EngagementListResponse(BaseModel):
    """Schema for engagement list response."""
    id: UUID
    organization_name: str
    role: str
    start_date: datetime
    end_date: Optional[datetime] = None
    status: EngagementStatus
    verified_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)