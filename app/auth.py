"""
Authentication routes for user signup, login, and profile retrieval.
"""
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, StudentProfile, SupervisorProfile
from app.schemas import (
    UserSignupRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    StudentCompleteResponse,
    SupervisorCompleteResponse,
    StudentProfileResponse,
    SupervisorProfileResponse,
    UserRole as UserRoleSchema,
    CompleteProfileRequest,
    CompleteProfileResponse,
    LogoutResponse,
)
from app.utils import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_ledger_id,
    create_student_profile,
    create_supervisor_profile,
)

# Initialize router and security scheme
router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


# ============== Dependencies ==============

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer token credentials
        db: Database session

    Returns:
        Current User object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user


def require_student(current_user: User = Depends(get_current_user)) -> User:
    """Guard requiring the current user to be a student."""
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required"
        )
    return current_user


def require_supervisor(current_user: User = Depends(get_current_user)) -> User:
    """Guard requiring the current user to be a supervisor."""
    if current_user.role != UserRole.SUPERVISOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor access required"
        )
    return current_user


def require_complete_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Guard requiring the user's profile to be complete.

    Student -> must have institution
    Supervisor -> must have organization
    """
    if current_user.role == UserRole.STUDENT:
        profile = db.query(StudentProfile).filter(
            StudentProfile.user_id == current_user.id
        ).first()
        if not profile or not profile.institution:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Profile incomplete. Please complete your profile first."
            )
    else:
        profile = db.query(SupervisorProfile).filter(
            SupervisorProfile.user_id == current_user.id
        ).first()
        if not profile or not profile.organization:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Profile incomplete. Please complete your profile first."
            )
    return current_user


# ============== Routes ==============

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserSignupRequest, db: Session = Depends(get_db)):
    """
    Register a new user and create their profile.

    Args:
        user_data: User registration data (full_name, email, password, role)
        db: Database session

    Returns:
        JWT access token with role and ledger_id

    Raises:
        HTTPException: If email already exists
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    role = user_data.role

    # Generate ledger ID
    ledger_id = generate_ledger_id(db, role)

    # Hash password
    hashed_password = hash_password(user_data.password)

    # Create user
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        role=role,
        ledger_id=ledger_id,
        is_active=True
    )
    db.add(user)
    db.flush()  # Flush to get the user ID

    # Create corresponding profile (institution/organization = None per spec)
    if role == UserRole.STUDENT:
        create_student_profile(
            db=db,
            user_id=user.id,
            full_name=user_data.full_name,
        )
    else:
        create_supervisor_profile(
            db=db,
            user_id=user.id,
            full_name=user_data.full_name,
            email=user_data.email,
        )

    db.commit()
    db.refresh(user)

    # Generate JWT token
    token_data = {
        "user_id": str(user.id),
        "role": user.role.value,
        "ledger_id": user.ledger_id
    }
    access_token = create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        role=UserRoleSchema(user.role.value),
        ledger_id=user.ledger_id
    )


@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a user and return JWT token.

    Args:
        login_data: User login data (email, password)
        db: Database session

    Returns:
        JWT access token with role and ledger_id

    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by email
    user = db.query(User).filter(User.email == login_data.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Generate JWT token
    token_data = {
        "user_id": str(user.id),
        "role": user.role.value,
        "ledger_id": user.ledger_id
    }
    access_token = create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        role=UserRoleSchema(user.role.value),
        ledger_id=user.ledger_id
    )


@router.get("/me", response_model=Union[StudentCompleteResponse, SupervisorCompleteResponse])
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user information including profile.

    Args:
        current_user: Current authenticated user (from JWT)
        db: Database session

    Returns:
        User and profile data based on role, with profile_complete flag
    """
    user_response = UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=UserRoleSchema(current_user.role.value),
        ledger_id=current_user.ledger_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )

    if current_user.role == UserRole.STUDENT:
        profile = db.query(StudentProfile).filter(
            StudentProfile.user_id == current_user.id
        ).first()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )

        profile_response = StudentProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            full_name=profile.full_name,
            title=profile.title,
            bio=profile.bio,
            linkedin_url=profile.linkedin_url,
            institution=profile.institution,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )

        return StudentCompleteResponse(
            user=user_response,
            profile=profile_response,
            profile_complete=profile.institution is not None
        )

    else:
        profile = db.query(SupervisorProfile).filter(
            SupervisorProfile.user_id == current_user.id
        ).first()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supervisor profile not found"
            )

        profile_response = SupervisorProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            full_name=profile.full_name,
            designation=profile.designation,
            organization=profile.organization,
            bio=profile.bio,
            linkedin_url=profile.linkedin_url,
            email_domain=profile.email_domain,
            trust_tier=profile.trust_tier.value,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )

        return SupervisorCompleteResponse(
            user=user_response,
            profile=profile_response,
            profile_complete=profile.organization is not None
        )


@router.put("/complete-profile", response_model=CompleteProfileResponse)
def complete_profile(
    profile_data: CompleteProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Complete or update user profile.

    Student can update: institution, bio, title, linkedin_url
    Supervisor can update: organization, designation, bio, linkedin_url
    """
    # Build list of fields sent in the request (only non-None values)
    received_fields = {
        k: v for k, v in {
            "institution": profile_data.institution,
            "title": profile_data.title,
            "bio": profile_data.bio,
            "linkedin_url": profile_data.linkedin_url,
            "organization": profile_data.organization,
            "designation": profile_data.designation,
        }.items() if v is not None
    }

    if not received_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update"
        )

    if current_user.role == UserRole.STUDENT:
        # Validate only student-allowed fields are present
        student_fields = {"institution", "title", "bio", "linkedin_url"}
        foreign_fields = set(received_fields.keys()) - student_fields
        if foreign_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student cannot update fields: {', '.join(sorted(foreign_fields))}"
            )

        # Validate required field
        if profile_data.institution is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="institution is required to complete student profile"
            )

        profile = db.query(StudentProfile).filter(
            StudentProfile.user_id == current_user.id
        ).first()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )

        profile.institution = profile_data.institution
        if profile_data.title is not None:
            profile.title = profile_data.title
        if profile_data.bio is not None:
            profile.bio = profile_data.bio
        if profile_data.linkedin_url is not None:
            profile.linkedin_url = profile_data.linkedin_url

        db.commit()
        db.refresh(profile)

        profile_response = StudentProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            full_name=profile.full_name,
            title=profile.title,
            bio=profile.bio,
            linkedin_url=profile.linkedin_url,
            institution=profile.institution,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )

        return CompleteProfileResponse(
            message="Profile updated successfully",
            profile=profile_response
        )

    else:
        # Validate only supervisor-allowed fields are present
        supervisor_fields = {"organization", "designation", "bio", "linkedin_url"}
        foreign_fields = set(received_fields.keys()) - supervisor_fields
        if foreign_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Supervisor cannot update fields: {', '.join(sorted(foreign_fields))}"
            )

        # Validate required field
        if profile_data.organization is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="organization is required to complete supervisor profile"
            )

        profile = db.query(SupervisorProfile).filter(
            SupervisorProfile.user_id == current_user.id
        ).first()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supervisor profile not found"
            )

        profile.organization = profile_data.organization
        if profile_data.designation is not None:
            profile.designation = profile_data.designation
        if profile_data.bio is not None:
            profile.bio = profile_data.bio
        if profile_data.linkedin_url is not None:
            profile.linkedin_url = profile_data.linkedin_url

        db.commit()
        db.refresh(profile)

        profile_response = SupervisorProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            full_name=profile.full_name,
            designation=profile.designation,
            organization=profile.organization,
            bio=profile.bio,
            linkedin_url=profile.linkedin_url,
            email_domain=profile.email_domain,
            trust_tier=profile.trust_tier.value,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )

        return CompleteProfileResponse(
            message="Profile updated successfully",
            profile=profile_response
        )


@router.post("/logout", response_model=LogoutResponse)
def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint (client-side token discard).

    Since JWT is stateless, this just returns a success message.
    Client should discard the token.
    """
    return LogoutResponse(message="Logged out successfully")


# Keep signup as alias for backward compatibility (deprecated)
@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def signup(user_data: UserSignupRequest, db: Session = Depends(get_db)):
    """Deprecated: Use /auth/register instead."""
    return register(user_data, db)
