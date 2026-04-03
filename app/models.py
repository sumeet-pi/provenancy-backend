"""
SQLAlchemy models for the database tables.
Each class represents a table in the database.
"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Enum, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy import Index

from app.database import Base


class EngagementStatus(str, enum.Enum):
    """Enum for engagement status."""
    DRAFT = "draft"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EDIT_REQUESTED = "edit_requested"


class VerificationType(str, enum.Enum):
    """Enum for verification type."""
    INSTITUTIONAL = "institutional"
    INDEPENDENT = "independent"


class UserRole(str, enum.Enum):
    """Enum for user roles."""
    STUDENT = "student"
    SUPERVISOR = "supervisor"


class TrustTier(str, enum.Enum):
    """Enum for supervisor trust tiers."""
    INSTITUTIONAL = "institutional"
    INDEPENDENT = "independent"


class User(Base):
    """
    User model representing the central users table.

    Attributes:
        id: Primary key (UUID)
        email: Unique email address
        hashed_password: Bcrypt hashed password
        role: User role (student or supervisor)
        ledger_id: Unique ledger identifier
        is_active: Whether the account is active
        created_at: Timestamp when user was created
        updated_at: Timestamp when user was last updated
    """

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    ledger_id = Column(String(50), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    student_profile = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    supervisor_profile = relationship(
        "SupervisorProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role.value}')>"


class StudentProfile(Base):
    """
    Student profile model for student-specific data.

    Attributes:
        id: Primary key (UUID)
        user_id: Foreign key to users table
        full_name: Student's full name
        title: Job title/internship title (nullable)
        bio: Student bio (nullable)
        linkedin_url: LinkedIn profile URL (nullable)
        institution: Educational institution (nullable)
        created_at: Timestamp when profile was created
        updated_at: Timestamp when profile was last updated
    """

    __tablename__ = "student_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    full_name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    bio = Column(String(1000), nullable=True)
    linkedin_url = Column(String(255), nullable=True)
    institution = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="student_profile")
    declared_skills = relationship("DeclaredSkill", back_populates="student_profile", cascade="all, delete-orphan")
    engagements = relationship("Engagement", back_populates="student_profile", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<StudentProfile(id={self.id}, user_id={self.user_id}, full_name='{self.full_name}')>"


class SupervisorProfile(Base):
    """
    Supervisor profile model for supervisor-specific data.

    Attributes:
        id: Primary key (UUID)
        user_id: Foreign key to users table
        full_name: Supervisor's full name
        designation: Job designation (nullable)
        organization: Organization name (nullable)
        bio: Supervisor bio (nullable)
        linkedin_url: LinkedIn profile URL (nullable)
        email_domain: Derived from user's email
        trust_tier: Trust tier based on email domain vs organization
        created_at: Timestamp when profile was created
        updated_at: Timestamp when profile was last updated
    """

    __tablename__ = "supervisor_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    full_name = Column(String(255), nullable=False)
    designation = Column(String(255), nullable=True)
    organization = Column(String(255), nullable=True)
    bio = Column(String(1000), nullable=True)
    linkedin_url = Column(String(255), nullable=True)
    email_domain = Column(String(255), nullable=False)
    trust_tier = Column(Enum(TrustTier), nullable=False, default=TrustTier.INDEPENDENT)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="supervisor_profile")
    engagements = relationship("Engagement", back_populates="supervisor_profile")

    def __repr__(self) -> str:
        return f"<SupervisorProfile(id={self.id}, user_id={self.user_id}, full_name='{self.full_name}')>"


class Skill(Base):
    """
    Skill model representing a skill definition.

    Attributes:
        id: Primary key (UUID)
        name: Skill name (unique)
        category: Skill category (optional)
    """

    __tablename__ = "skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True, index=True)
    category = Column(String(100), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    engagement_skills = relationship(
        "EngagementSkill",
        back_populates="skill",
        cascade="all, delete-orphan"
    )
    declared_skills = relationship(
        "DeclaredSkill",
        back_populates="skill",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name='{self.name}')>"


class DeclaredSkill(Base):
    """
    DeclaredSkill model representing user-added skills.

    Attributes:
        id: Primary key (UUID)
        student_profile_id: Foreign key to student_profiles
        skill_id: Foreign key to skills
        created_at: Timestamp when skill was declared
    """

    __tablename__ = "declared_skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    skill_id = Column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    student_profile = relationship("StudentProfile", back_populates="declared_skills")
    skill = relationship("Skill", back_populates="declared_skills")

    __table_args__ = (
        Index("ix_declared_skills_unique", "student_profile_id", "skill_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<DeclaredSkill(id={self.id}, student_profile_id={self.student_profile_id}, skill_id={self.skill_id})>"


class Engagement(Base):
    """
    Engagement model representing a student's professional experience.

    Attributes:
        id: Primary key (UUID)
        student_profile_id: Foreign key to student_profiles
        supervisor_profile_id: Foreign key to supervisor_profiles (nullable)
        supervisor_ref: Raw input from student before resolution
        organization_name: Organization name
        role: Role at organization
        start_date: Start date
        end_date: End date (nullable for ongoing)
        summary: Free-text description
        highlights: JSON array of key points
        links: JSON array of supporting URLs
        status: Engagement status
        rejection_reason: Reason if rejected/edit_requested
        verification_type: Snapshotted from supervisor trust tier
        block_hash: Set upon supervisor approval
        verified_at: Timestamp of approval
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "engagements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    supervisor_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("supervisor_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    supervisor_ref = Column(String(255), nullable=True)
    organization_name = Column(String(255), nullable=False)
    role = Column(String(255), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    summary = Column(Text, nullable=True)
    highlights = Column(JSONB, nullable=True)
    links = Column(JSONB, nullable=True)
    status = Column(Enum(EngagementStatus), nullable=False, default=EngagementStatus.DRAFT, index=True)
    rejection_reason = Column(Text, nullable=True)
    verification_type = Column(Enum(VerificationType), nullable=True)
    block_hash = Column(String(255), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    student_profile = relationship("StudentProfile", back_populates="engagements")
    supervisor_profile = relationship("SupervisorProfile", back_populates="engagements")
    engagement_skills = relationship(
        "EngagementSkill",
        back_populates="engagement",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Engagement(id={self.id}, organization_name='{self.organization_name}', status='{self.status.value}')>"


class EngagementSkill(Base):
    """
    Many-to-many bridge between engagements and skills.

    Attributes:
        id: Primary key (UUID)
        engagement_id: Foreign key to engagements
        skill_id: Foreign key to skills
    """

    __tablename__ = "engagement_skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engagement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    skill_id = Column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    engagement = relationship("Engagement", back_populates="engagement_skills")
    skill = relationship("Skill", back_populates="engagement_skills")

    __table_args__ = (
        Index("ix_engagement_skills_unique", "engagement_id", "skill_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<EngagementSkill(id={self.id}, engagement_id={self.engagement_id}, skill_id={self.skill_id})>"