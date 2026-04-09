"""
Pydantic schemas for request/response validation.
Schemas define the structure of data exchanged via API.
"""
import re
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, field_serializer, ValidationInfo


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
    skills: Optional["SkillListResponse"] = None

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




# ============== Health Check Schema ==============

class HealthResponse(BaseModel):
    """Schema for health check endpoint response."""
    status: str
    database: str
    version: str


# ============== Skill Schemas ==============

class SkillCreateRequest(BaseModel):
    """Schema for creating a declared skill."""
    name: str

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        """Normalize skill name: trim whitespace, convert to lowercase."""
        v = v.strip().lower()
        if not v:
            raise ValueError("Skill name cannot be empty")
        if len(v) < 2 or len(v) > 100:
            raise ValueError("Skill name must be between 2 and 100 characters")
        return v


class SkillBulkCreateRequest(BaseModel):
    """Schema for creating multiple declared skills at once."""
    skills: List[str]

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: List[str]) -> List[str]:
        """Validate each skill name and remove duplicates."""
        if not v:
            raise ValueError("Skills list cannot be empty")
        if len(v) > 10:
            raise ValueError("Cannot add more than 10 skills at once")

        normalized = []
        seen = set()
        for skill in v:
            skill = skill.strip().lower()
            if not skill:
                raise ValueError("Skill name cannot be empty")
            if len(skill) < 2 or len(skill) > 100:
                raise ValueError(f"Skill name '{skill}' must be between 2 and 100 characters")
            if skill not in seen:
                normalized.append(skill)
                seen.add(skill)

        return normalized


class SkillResponse(BaseModel):
    """Schema for a single skill response."""
    id: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class SkillBulkResponse(BaseModel):
    """Schema for bulk skill creation response."""
    created: List[SkillResponse] = []
    skipped: List[str] = []


class VerifiedSkillItem(BaseModel):
    """Schema for a verified skill item (with count)."""
    name: str
    count: int


class SkillListResponse(BaseModel):
    """Schema for skills list response with declared and verified skills."""
    declared: List[SkillResponse] = []
    verified: List[VerifiedSkillItem] = []


class SkillDeleteResponse(BaseModel):
    """Schema for skill deletion response."""
    message: str


# ============== Supervisor Engagement Review Schemas ==============

class RejectEngagementRequest(BaseModel):
    """Schema for rejecting an engagement."""
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate rejection reason: must be non-empty, max 500 chars."""
        v = v.strip()
        if not v:
            raise ValueError("Rejection reason cannot be empty")
        if len(v) > 500:
            raise ValueError("Rejection reason must not exceed 500 characters")
        return v


class RequestEditEngagementRequest(BaseModel):
    """Schema for requesting edits on an engagement."""
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate edit request reason: must be non-empty, max 500 chars."""
        v = v.strip()
        if not v:
            raise ValueError("Edit request reason cannot be empty")
        if len(v) > 500:
            raise ValueError("Edit request reason must not exceed 500 characters")
        return v


# ============== Engagement Schemas ==============

# Generic/meaningless org names to reject at business logic level
GENERIC_ORG_NAMES: frozenset = frozenset({
    "test", "abc", "company", "temp", "dummy", "fake", "example",
    "my company", "test company", "intern", "internship"
})

# Generic/meaningless roles to flag for review
GENERIC_ROLES: frozenset = frozenset({
    "intern", "employee", "worker", "staff", "team member",
    "internship", "trainee", "volunteer"
})


# Ledger ID pattern for supervisor_ref validation
LEDGER_ID_PATTERN = re.compile(r"^PRV-(?:SUP-)?[A-Z0-9]{4}$", re.IGNORECASE)


class EngagementBaseValidator:
    """Shared validation mixin for engagement schemas."""

    @field_validator("organization_name")
    @classmethod
    def validate_organization_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate organization_name: trim whitespace, enforce min/max length, reject generic names."""
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Organization name must be at least 2 characters")
            if len(v) > 150:
                raise ValueError("Organization name must not exceed 150 characters")
            # Check generic names
            if v.lower() in GENERIC_ORG_NAMES:
                raise ValueError("Please provide a more specific organization name")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """Validate role: trim whitespace, enforce min/max length, reject generic roles."""
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Role must be at least 2 characters")
            if len(v) > 150:
                raise ValueError("Role must not exceed 150 characters")
            # Check generic roles
            if v.lower() in GENERIC_ROLES:
                raise ValueError("Please provide a more specific role")
        return v

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v: Optional[str]) -> Optional[str]:
        """Validate summary: trim whitespace, min 20 words if provided, max 500 words."""
        if v is not None:
            v = v.strip()
            words = v.split()
            if len(words) < 20:
                raise ValueError("Summary must be at least 20 words")
            if len(words) > 500:
                raise ValueError("Summary must not exceed 500 words")
            if len(v) > 3000:
                raise ValueError("Summary must not exceed 3000 characters")
        return v

    @field_validator("highlights")
    @classmethod
    def validate_highlights(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate highlights: max 3 items, each max 200 chars, no empty strings."""
        if v is not None:
            if len(v) > 3:
                raise ValueError("Highlights must have at most 3 items")
            for i, item in enumerate(v):
                if item is None:
                    raise ValueError(f"Highlight {i + 1} cannot be empty")
                item = item.strip()
                if not item:
                    raise ValueError(f"Highlight {i + 1} cannot be empty")
                if len(item) > 200:
                    raise ValueError(f"Highlight {i + 1} must not exceed 200 characters")
                v[i] = item
        return v

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate skills: max 5 items, no empty strings, min 2 chars each."""
        if v is not None:
            if len(v) > 5:
                raise ValueError("Skills must have at most 5 items")
            for item in v:
                item = item.strip() if item else ""
                if not item:
                    raise ValueError("Skills cannot contain empty items")
                if len(item) < 2:
                    raise ValueError("Each skill must be at least 2 characters")
        return v

    @field_validator("links")
    @classmethod
    def validate_links(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate links: max 5 items, each must be valid URL."""
        if v is not None:
            if len(v) > 5:
                raise ValueError("Links must have at most 5 items")
            for link in v:
                if link is None or not link.strip():
                    raise ValueError("Links cannot contain empty items")
                link = link.strip()
                if not (link.startswith("http://") or link.startswith("https://")):
                    raise ValueError(f"Invalid link '{link}': must start with http:// or https://")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: Optional[datetime], info: ValidationInfo) -> Optional[datetime]:
        """Validate end_date: must be >= start_date if provided."""
        if v is not None:
            start_date = info.data.get("start_date")
            if start_date is not None:
                from datetime import timezone
                if v.tzinfo is None:
                    v = v.replace(tzinfo=timezone.utc)
                if start_date.tzinfo is None:
                    start_date = start_date.replace(tzinfo=timezone.utc)
                if v < start_date:
                    raise ValueError("End date must be on or after start date")
        return v


class EngagementCreate(BaseModel, EngagementBaseValidator):
    """
    Schema for creating an engagement.

    Validation rules:
    - organization_name: 2-150 chars, required, reject generic names
    - role: 2-150 chars, required, reject generic roles
    - summary: optional, min 20 words, max 500 words (~3000 chars)
    - highlights: optional list, max 3 items, each max 200 chars
    - links: optional list, max 5 items, valid URLs
    - start_date: required, must be <= today
    - end_date: optional, must be >= start_date
    - supervisor_ref: optional, valid email or ledger_id
    """
    organization_name: str
    role: str
    start_date: datetime
    end_date: Optional[datetime] = None
    summary: Optional[str] = None
    highlights: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    links: Optional[List[str]] = None
    supervisor_ref: Optional[str] = None

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: datetime) -> datetime:
        """Validate start_date: must be <= today."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v > now:
            raise ValueError("Start date cannot be in the future")
        return v

    @field_validator("supervisor_ref")
    @classmethod
    def validate_supervisor_ref(cls, v: Optional[str]) -> Optional[str]:
        """Validate supervisor_ref: must be valid email or ledger_id format."""
        if v is not None and v.strip():
            v = v.strip()
            # Check if it's a valid email
            if "@" in v:
                # Basic email validation
                if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
                    raise ValueError("Invalid email format for supervisor reference")
            else:
                # Check if it's a ledger_id format
                if not LEDGER_ID_PATTERN.match(v):
                    raise ValueError("Supervisor reference must be a valid email or ledger ID (e.g., PRV-SUP-1234)")
        return v


class EngagementUpdate(BaseModel, EngagementBaseValidator):
    """
    Schema for updating an engagement. All fields are optional for partial updates.

    Validation rules (when provided):
    - organization_name: 2-150 chars, reject generic names
    - role: 2-150 chars, reject generic roles
    - summary: min 20 words, max 500 words
    - highlights: max 3 items, each max 200 chars
    - links: max 5 items, valid URLs
    - start_date: must be <= today
    - end_date: must be >= start_date

    Note: Cannot modify engagement if status = "verified" (enforced at API layer).
    """
    organization_name: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    summary: Optional[str] = None
    highlights: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    links: Optional[List[str]] = None
    supervisor_ref: Optional[str] = None

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate start_date: must be <= today."""
        if v is not None:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            if v > now:
                raise ValueError("Start date cannot be in the future")
        return v

    @field_validator("supervisor_ref")
    @classmethod
    def validate_supervisor_ref(cls, v: Optional[str]) -> Optional[str]:
        """Validate supervisor_ref: must be valid email or ledger_id format."""
        if v is not None and v.strip():
            v = v.strip()
            if "@" in v:
                if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
                    raise ValueError("Invalid email format for supervisor reference")
            else:
                if not LEDGER_ID_PATTERN.match(v):
                    raise ValueError("Supervisor reference must be a valid email or ledger ID")
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

# Update forward references
StudentProfileUpdateResponse.model_rebuild()
StudentPublicResponse.model_rebuild()
SupervisorProfileUpdateResponse.model_rebuild()
SupervisorPublicResponse.model_rebuild()