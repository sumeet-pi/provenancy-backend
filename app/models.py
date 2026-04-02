"""
SQLAlchemy models for the database tables.
Each class represents a table in the database.
"""
import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


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

    def __repr__(self) -> str:
        return f"<SupervisorProfile(id={self.id}, user_id={self.user_id}, full_name='{self.full_name}')>"