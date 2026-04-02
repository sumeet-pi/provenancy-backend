"""
Utility functions for authentication and business logic.
Includes password hashing, JWT handling, ledger ID generation, and trust tier resolver.
"""
import random
import re
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserRole, TrustTier, StudentProfile, SupervisorProfile


# ============== Password Hashing ==============

def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database

    Returns:
        True if password matches, False otherwise
    """
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ============== JWT Handling ==============

def create_access_token(data: dict) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary containing token payload (user_id, role, ledger_id)

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + settings.access_token_expire
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string to decode

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


# ============== Ledger ID Generation ==============

def generate_student_ledger_id(db: Session) -> str:
    """
    Generate a unique student ledger ID.
    Format: PRV-{YEAR}-{4-digit sequence}

    Args:
        db: Database session

    Returns:
        Unique ledger ID string
    """
    current_year = datetime.now().year

    # Find the highest sequence number for the current year
    existing = db.query(User).filter(
        User.ledger_id.like(f"PRV-{current_year}-%")
    ).order_by(User.ledger_id.desc()).first()

    if existing:
        try:
            last_seq = int(existing.ledger_id.split("-")[-1])
            new_seq = last_seq + 1
        except (ValueError, IndexError):
            new_seq = 1
    else:
        new_seq = 1

    # Pad sequence to 4 digits
    return f"PRV-{current_year}-{new_seq:04d}"


def generate_supervisor_ledger_id(db: Session) -> str:
    """
    Generate a unique supervisor ledger ID.
    Format: PRV-SUP-{random 4-digit}

    Args:
        db: Database session

    Returns:
        Unique ledger ID string
    """
    while True:
        random_seq = random.randint(0, 9999)
        ledger_id = f"PRV-SUP-{random_seq:04d}"

        # Check uniqueness
        existing = db.query(User).filter(User.ledger_id == ledger_id).first()
        if not existing:
            return ledger_id


def generate_ledger_id(db: Session, role: UserRole) -> str:
    """
    Generate a ledger ID based on user role.

    Args:
        db: Database session
        role: User role (student or supervisor)

    Returns:
        Unique ledger ID string
    """
    if role == UserRole.STUDENT:
        return generate_student_ledger_id(db)
    else:
        return generate_supervisor_ledger_id(db)


# ============== Trust Tier Resolver ==============

def extract_email_domain(email: str) -> str:
    """
    Extract domain from email address.

    Args:
        email: Email address string

    Returns:
        Domain string (lowercase)
    """
    if "@" in email:
        return email.split("@")[1].lower()
    return ""


def resolve_trust_tier(email: str, organization: Optional[str]) -> TrustTier:
    """
    Resolve the trust tier based on email domain and organization.

    Logic:
    - If organization is provided and matches email domain -> institutional
    - Otherwise -> independent

    Args:
        email: User's email address
        organization: User's organization (nullable)

    Returns:
        Trust tier (institutional or independent)
    """
    email_domain = extract_email_domain(email)

    if organization:
        # Normalize organization for comparison
        org_normalized = organization.lower().strip()
        # Remove common prefixes/suffixes for better matching
        org_clean = re.sub(r"(university|college|institute|school|ltd|inc|corp)$", "", org_normalized).strip()

        if email_domain and (email_domain in org_clean or org_clean in email_domain):
            return TrustTier.INSTITUTIONAL

    return TrustTier.INDEPENDENT


# ============== Profile Creation ==============

def create_student_profile(
    db: Session,
    user_id: str,
    full_name: str,
    institution: Optional[str] = None
) -> StudentProfile:
    """
    Create a student profile.

    Args:
        db: Database session
        user_id: UUID of the user
        full_name: Student's full name
        institution: Educational institution (nullable)

    Returns:
        Created StudentProfile object
    """
    profile = StudentProfile(
        user_id=user_id,
        full_name=full_name,
        institution=institution
    )
    db.add(profile)
    return profile


def create_supervisor_profile(
    db: Session,
    user_id: str,
    full_name: str,
    email: str,
    organization: Optional[str] = None
) -> SupervisorProfile:
    """
    Create a supervisor profile with trust tier resolution.

    Args:
        db: Database session
        user_id: UUID of the user
        full_name: Supervisor's full name
        email: Supervisor's email (for domain extraction)
        organization: Organization name (nullable)

    Returns:
        Created SupervisorProfile object with resolved trust tier
    """
    email_domain = extract_email_domain(email)
    trust_tier = resolve_trust_tier(email, organization)

    profile = SupervisorProfile(
        user_id=user_id,
        full_name=full_name,
        organization=organization,
        email_domain=email_domain,
        trust_tier=trust_tier
    )
    db.add(profile)
    return profile