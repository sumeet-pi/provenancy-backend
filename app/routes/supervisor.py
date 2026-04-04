"""
Supervisor profile routes for private and public access.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, SupervisorProfile, UserRole, Engagement, EngagementStatus
from app.schemas import (
    SupervisorProfileUpdateRequest,
    SupervisorProfileUpdateResponse,
    SupervisorPublicResponse,
    SupervisorProfileResponse,
    UserResponse,
    UserRole as UserRoleSchema,
    VerifiedEngagementSupervisorPublic,
)
from app.auth import get_current_user

router = APIRouter(prefix="/supervisor", tags=["Supervisor"])


def require_supervisor(current_user: User = Depends(get_current_user)) -> User:
    """Guard requiring the current user to be a supervisor."""
    if current_user.role != UserRole.SUPERVISOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor access required"
        )
    return current_user


@router.get("/me", response_model=SupervisorProfileUpdateResponse)
def get_my_profile(
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """
    Get current supervisor's private profile.
    Only accessible by users with role = supervisor.
    """
    profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supervisor profile not found"
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

    profile_response = SupervisorProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        full_name=profile.full_name,
        designation=profile.designation,
        organization=profile.organization,
        bio=profile.bio,
        linkedin_url=profile.linkedin_url,
        email_domain=profile.email_domain,
        trust_tier=profile.trust_tier,
        created_at=profile.created_at,
        updated_at=profile.updated_at
    )

    return SupervisorProfileUpdateResponse(
        message="Profile retrieved successfully",
        profile=profile_response,
        profile_complete=profile.organization is not None,
        ledger_id=current_user.ledger_id
    )


@router.put("/me", response_model=SupervisorProfileUpdateResponse)
def update_my_profile(
    profile_data: SupervisorProfileUpdateRequest,
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """
    Update current supervisor's profile.
    Only accessible by users with role = supervisor.
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

    profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == current_user.id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supervisor profile not found"
        )

    # Update fields
    if "full_name" in received_fields:
        profile.full_name = received_fields["full_name"]
    if "designation" in received_fields:
        profile.designation = received_fields["designation"]
    if "organization" in received_fields:
        profile.organization = received_fields["organization"]
    if "bio" in received_fields:
        profile.bio = received_fields["bio"]
    if "linkedin_url" in received_fields:
        profile.linkedin_url = received_fields["linkedin_url"]

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
        trust_tier=profile.trust_tier,
        created_at=profile.created_at,
        updated_at=profile.updated_at
    )

    return SupervisorProfileUpdateResponse(
        message="Profile updated successfully",
        profile=profile_response,
        profile_complete=profile.organization is not None
    )


@router.get("/{supervisor_id}/public", response_model=SupervisorPublicResponse)
def get_public_profile(
    supervisor_id: str,
    db: Session = Depends(get_db)
):
    """
    Get public-facing supervisor profile.
    No authentication required.
    """
    # Validate UUID format
    try:
        supervisor_uuid = uuid.UUID(supervisor_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid supervisor ID format"
        )

    profile = db.query(SupervisorProfile).join(User).filter(
        SupervisorProfile.id == supervisor_uuid,
        User.role == UserRole.SUPERVISOR,
        User.is_active == True
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supervisor profile not found"
        )

    # Get verified engagements for this supervisor
    verified_engagements = db.query(Engagement).filter(
        Engagement.supervisor_profile_id == profile.id,
        Engagement.status == EngagementStatus.VERIFIED
    ).all()

    verified_engagement_list = [
        VerifiedEngagementSupervisorPublic(
            id=eng.id,
            student_full_name=eng.student_profile.full_name if eng.student_profile else "Unknown",
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

    return SupervisorPublicResponse(
        id=profile.id,
        ledger_id=user.ledger_id if user else None,
        full_name=profile.full_name,
        designation=profile.designation,
        organization=profile.organization,
        bio=profile.bio,
        linkedin_url=profile.linkedin_url,
        trust_tier=profile.trust_tier,
        created_at=profile.created_at,
        verified_engagements=verified_engagement_list
    )
