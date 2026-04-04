"""
Student profile routes for private and public access.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User, StudentProfile, UserRole, Engagement, EngagementStatus
from app.schemas import (
    StudentProfileUpdateRequest,
    StudentProfileUpdateResponse,
    StudentPublicResponse,
    StudentProfileResponse,
    UserResponse,
    UserRole as UserRoleSchema,
    VerifiedEngagementPublic,
)
from app.auth import get_current_user, require_student

router = APIRouter(prefix="/student", tags=["Student"])


@router.get("/me", response_model=StudentProfileUpdateResponse)
def get_my_profile(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Get current student's private profile.
    Only accessible by users with role = student.
    """
    profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )

    user_response = UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=UserRoleSchema(current_user.role.value),
        ledger_id=current_user.ledger_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
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

    return StudentProfileUpdateResponse(
        message="Profile retrieved successfully",
        profile=profile_response,
        profile_complete=profile.institution is not None,
        ledger_id=current_user.ledger_id
    )


@router.put("/me", response_model=StudentProfileUpdateResponse)
def update_my_profile(
    profile_data: StudentProfileUpdateRequest,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Update current student's profile.
    Only accessible by users with role = student.
    """
    received_fields = {
        k: v for k, v in profile_data.model_dump().items()
        if v is not None and (not isinstance(v, str) or v.strip())
    }

    if not received_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update"
        )

    profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )

    # Update fields
    if "full_name" in received_fields:
        profile.full_name = received_fields["full_name"]
    if "title" in received_fields:
        profile.title = received_fields["title"]
    if "bio" in received_fields:
        profile.bio = received_fields["bio"]
    if "linkedin_url" in received_fields:
        profile.linkedin_url = received_fields["linkedin_url"]
    if "institution" in received_fields:
        profile.institution = received_fields["institution"]

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

    return StudentProfileUpdateResponse(
        message="Profile updated successfully",
        profile=profile_response,
        profile_complete=profile.institution is not None
    )


@router.get("/{student_id}/public", response_model=StudentPublicResponse)
def get_public_profile(
    student_id: str,
    db: Session = Depends(get_db)
):
    """
    Get public-facing student profile.
    No authentication required.
    """
    # Validate UUID format
    try:
        student_uuid = uuid.UUID(student_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid student ID format"
        )

    # Query with join to User to verify role
    profile = db.query(StudentProfile).join(User).filter(
        StudentProfile.id == student_uuid,
        User.role == UserRole.STUDENT,
        User.is_active == True
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )

    # Get verified engagements for this student
    verified_engagements = db.query(Engagement).filter(
        Engagement.student_profile_id == profile.id,
        Engagement.status == EngagementStatus.VERIFIED
    ).all()

    verified_engagement_list = [
        VerifiedEngagementPublic(
            id=eng.id,
            organization_name=eng.organization_name,
            role=eng.role,
            start_date=eng.start_date,
            end_date=eng.end_date,
            verification_type=eng.verification_type,
            verified_at=eng.verified_at
        )
        for eng in verified_engagements
    ]

    # Get user for ledger_id
    user = db.query(User).filter(User.id == profile.user_id).first()

    return StudentPublicResponse(
        id=profile.id,
        ledger_id=user.ledger_id if user else None,
        full_name=profile.full_name,
        title=profile.title,
        bio=profile.bio,
        linkedin_url=profile.linkedin_url,
        institution=profile.institution,
        created_at=profile.created_at,
        verified_engagements=verified_engagement_list
    )
