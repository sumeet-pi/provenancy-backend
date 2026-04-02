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


# ============== Routes ==============

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserSignupRequest, db: Session = Depends(get_db)):
    """
    Register a new user and create their profile.

    Args:
        user_data: User signup data (full_name, email, password, role)
        db: Database session

    Returns:
        JWT access token

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

    # Parse role
    try:
        role = UserRole(user_data.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'student' or 'supervisor'"
        )

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

    # Create corresponding profile
    if role == UserRole.STUDENT:
        create_student_profile(
            db=db,
            user_id=user.id,
            full_name=user_data.full_name,
            institution=user_data.institution
        )
    else:  # Supervisor
        create_supervisor_profile(
            db=db,
            user_id=user.id,
            full_name=user_data.full_name,
            email=user_data.email,
            organization=user_data.organization
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

    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a user and return JWT token.

    Args:
        login_data: User login data (email, password)
        db: Database session

    Returns:
        JWT access token

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

    return TokenResponse(access_token=access_token)


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
        User and profile data based on role

    Raises:
        HTTPException: If profile not found (should not happen)
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
            profile=profile_response
        )

    else:  # Supervisor
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
            profile=profile_response
        )