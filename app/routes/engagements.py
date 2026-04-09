"""
Engagement routes for student and supervisor interactions.
"""
import re
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User, UserRole, Engagement, EngagementStatus,
    StudentProfile, SupervisorProfile, Skill, EngagementSkill
)
from app.schemas import (
    EngagementCreate,
    EngagementUpdate,
    EngagementResponse,
    EngagementListResponse,
    EngagementStatus as EngagementStatusSchema,
    SkillResponse,
    RejectEngagementRequest,
    RequestEditEngagementRequest,
    VerificationType,
)
from app.auth import get_current_user, require_student, require_supervisor, require_complete_profile

router = APIRouter(prefix="/engagements", tags=["Engagements"])


# ============== Status Transition Validation ==============

ALLOWED_TRANSITIONS = {
    EngagementStatus.DRAFT: [EngagementStatus.PENDING],
    EngagementStatus.PENDING: [EngagementStatus.VERIFIED, EngagementStatus.REJECTED, EngagementStatus.EDIT_REQUESTED],
    EngagementStatus.EDIT_REQUESTED: [EngagementStatus.PENDING],
    EngagementStatus.VERIFIED: [],
    EngagementStatus.REJECTED: [],
}


def validate_status_transition(current: EngagementStatus, new: EngagementStatus) -> bool:
    """Check if status transition is allowed."""
    return new in ALLOWED_TRANSITIONS.get(current, [])


# ============== Role-Based Status Validation ==============

STUDENT_ALLOWED_STATUSES = {"all", "draft", "pending", "verified", "rejected", "edit_requested"}
SUPERVISOR_ALLOWED_STATUSES = {"all", "pending", "verified", "rejected", "edit_requested"}


def get_allowed_statuses(role: UserRole) -> set[str]:
    """Return allowed status values for the given role."""
    if role == UserRole.STUDENT:
        return STUDENT_ALLOWED_STATUSES
    return SUPERVISOR_ALLOWED_STATUSES


def build_status_error_message(role: UserRole) -> str:
    """Build an error message listing allowed values for the role."""
    allowed = sorted(get_allowed_statuses(role))
    return f"Invalid status. Allowed values: {', '.join(allowed)}"


# ============== Helper Functions ==============

def get_engagement_or_404(db: Session, engagement_id: UUID, user: User) -> Engagement:
    """Get engagement by ID and verify ownership/access."""
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found"
        )

    # For students, verify ownership
    if user.role == UserRole.STUDENT:
        student_profile = db.query(StudentProfile).filter(
            StudentProfile.user_id == user.id
        ).first()
        if not student_profile or engagement.student_profile_id != student_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this engagement"
            )
    # For supervisors, they can view any engagement in pending queue
    # (additional check happens in specific endpoints)

    return engagement


def check_duplicate_engagement(
    db: Session,
    student_profile_id: UUID,
    organization_name: str,
    role: str,
    start_date: datetime,
    end_date: Optional[datetime],
    exclude_id: Optional[UUID] = None
) -> bool:
    """Check if a duplicate engagement already exists (same org + role + non-rejected)."""
    org_normalized = organization_name.lower().strip()
    role_normalized = role.lower().strip()

    query = db.query(Engagement).filter(
        Engagement.student_profile_id == student_profile_id,
        Engagement.organization_name.ilike(org_normalized),
        Engagement.role.ilike(role_normalized),
        Engagement.status.notin_([EngagementStatus.REJECTED])
    )

    if exclude_id:
        query = query.filter(Engagement.id != exclude_id)

    return query.first() is not None


def resolve_skills(db: Session, skill_names: List[str], student_profile_id: UUID, user_id: UUID) -> List[Skill]:
    """Resolve skill names to Skill objects, creating if needed."""
    skills = []
    for name in skill_names:
        name = name.strip().lower()
        if not name:
            continue

        skill = db.query(Skill).filter(
            Skill.student_profile_id == student_profile_id,
            Skill.name == name
        ).first()

        if not skill:
            skill = Skill(
                student_profile_id=student_profile_id,
                user_id=user_id,
                name=name,
                is_verified=False
            )
            db.add(skill)
            db.flush()

        skills.append(skill)

    return skills


def map_engagement_to_response(engagement: Engagement) -> EngagementResponse:
    """Map engagement model to response schema with skills."""
    skills = []
    for es in engagement.engagement_skills:
        skills.append(SkillResponse(
            id=es.skill.id,
            name=es.skill.name
        ))

    return EngagementResponse(
        id=engagement.id,
        student_profile_id=engagement.student_profile_id,
        supervisor_profile_id=engagement.supervisor_profile_id,
        supervisor_ref=engagement.supervisor_ref,
        organization_name=engagement.organization_name,
        role=engagement.role,
        start_date=engagement.start_date,
        end_date=engagement.end_date,
        summary=engagement.summary,
        highlights=engagement.highlights,
        links=engagement.links,
        status=EngagementStatusSchema(engagement.status.value),
        rejection_reason=engagement.rejection_reason,
        verified_at=engagement.verified_at,
        block_hash=engagement.block_hash,
        verification_type=engagement.verification_type,
        created_at=engagement.created_at,
        updated_at=engagement.updated_at,
        skills=skills
    )


# ============== Student Routes ==============

@router.post("", response_model=EngagementResponse, status_code=status.HTTP_201_CREATED)
def create_engagement(
    engagement_data: EngagementCreate,
    current_user: User = Depends(require_complete_profile),
    db: Session = Depends(get_db)
):
    """Create a new engagement (status = draft)."""
    # Get student profile
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user.id
    ).first()

    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )

    # Check for duplicate
    if check_duplicate_engagement(
        db,
        student_profile.id,
        engagement_data.organization_name,
        engagement_data.role,
        engagement_data.start_date,
        engagement_data.end_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate engagement: similar engagement already exists with overlapping dates"
        )

    # Create engagement
    engagement = Engagement(
        student_profile_id=student_profile.id,
        organization_name=engagement_data.organization_name,
        role=engagement_data.role,
        start_date=engagement_data.start_date,
        end_date=engagement_data.end_date,
        summary=engagement_data.summary,
        highlights=engagement_data.highlights,
        links=engagement_data.links,
        supervisor_ref=engagement_data.supervisor_ref,
        status=EngagementStatus.DRAFT
    )

    db.add(engagement)
    db.flush()

    # Handle skills
    if engagement_data.skills:
        skills = resolve_skills(
            db,
            engagement_data.skills,
            student_profile.id,
            current_user.id
        )
        for skill in skills:
            es = EngagementSkill(
                engagement_id=engagement.id,
                skill_id=skill.id
            )
            db.add(es)

    db.commit()
    db.refresh(engagement)

    return map_engagement_to_response(engagement)


@router.get("", response_model=List[EngagementListResponse])
def list_engagements(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all engagements for the current user (role-aware)."""
    allowed_statuses = get_allowed_statuses(current_user.role)

    # Build base query
    if current_user.role == UserRole.STUDENT:
        student_profile = db.query(StudentProfile).filter(
            StudentProfile.user_id == current_user.id
        ).first()
        if not student_profile:
            return []
        query = db.query(Engagement).filter(
            Engagement.student_profile_id == student_profile.id
        )
    else:
        supervisor_profile = db.query(SupervisorProfile).filter(
            SupervisorProfile.user_id == current_user.id
        ).first()
        if not supervisor_profile:
            return []
        query = db.query(Engagement).filter(
            Engagement.supervisor_profile_id == supervisor_profile.id
        )

    # Validate and apply status filter
    if status_filter:
        status_lower = status_filter.lower()
        if status_lower not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=build_status_error_message(current_user.role)
            )
        if status_lower != "all":
            try:
                status_enum = EngagementStatus(status_lower)
                query = query.filter(Engagement.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=build_status_error_message(current_user.role)
                )

    engagements = query.order_by(Engagement.created_at.desc()).all()

    return [
        EngagementListResponse(
            id=e.id,
            organization_name=e.organization_name,
            role=e.role,
            start_date=e.start_date,
            end_date=e.end_date,
            status=EngagementStatusSchema(e.status.value),
            verified_at=e.verified_at
        )
        for e in engagements
    ]


@router.get("/{engagement_id}", response_model=EngagementResponse)
def get_engagement(
    engagement_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single engagement by ID.

    Accessible by:
    - Owner student
    - Assigned supervisor
    """
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found"
        )

    # For students, verify ownership
    if current_user.role == UserRole.STUDENT:
        student_profile = db.query(StudentProfile).filter(
            StudentProfile.user_id == current_user.id
        ).first()
        if not student_profile or engagement.student_profile_id != student_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this engagement"
            )
    # For supervisors, verify they are assigned to this engagement
    elif current_user.role == UserRole.SUPERVISOR:
        supervisor_profile = db.query(SupervisorProfile).filter(
            SupervisorProfile.user_id == current_user.id
        ).first()
        if not supervisor_profile or engagement.supervisor_profile_id != supervisor_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this engagement"
            )

    return map_engagement_to_response(engagement)


@router.put("/{engagement_id}", response_model=EngagementResponse)
def update_engagement(
    engagement_id: UUID,
    engagement_data: EngagementUpdate,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """Update an engagement.

    Allowed only if status is draft, pending, or edit_requested.
    NOT allowed if status is verified (immutable).
    """
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found"
        )

    # Verify ownership
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user.id
    ).first()
    if not student_profile or engagement.student_profile_id != student_profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this engagement"
        )

    # Check status for update eligibility (verified and pending are immutable)
    if engagement.status == EngagementStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update engagement. Verified engagements are immutable."
        )
    if engagement.status not in [EngagementStatus.DRAFT, EngagementStatus.EDIT_REQUESTED]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update engagement. Only draft or edit_requested engagements can be updated."
        )

    # Enforce immutability for verified fields - handled at API level
    # Fields that cannot be modified if status was previously verified are blocked here

    # Check for duplicate (exclude current engagement)
    if engagement_data.organization_name and engagement_data.role and engagement_data.start_date:
        if check_duplicate_engagement(
            db,
            engagement.student_profile_id,
            engagement_data.organization_name,
            engagement_data.role,
            engagement_data.start_date,
            engagement_data.end_date,
            exclude_id=engagement.id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate engagement: similar engagement already exists"
            )

    # Update fields
    update_data = engagement_data.model_dump(exclude_unset=True)

    # Remove skills from direct update (handled separately)
    update_data.pop("skills", None)

    for field, value in update_data.items():
        if value is not None:
            setattr(engagement, field, value)

    # Handle skills update
    if engagement_data.skills is not None:
        # Remove existing engagement_skills
        db.query(EngagementSkill).filter(
            EngagementSkill.engagement_id == engagement.id
        ).delete()

        # Add new skills
        student_profile = db.query(StudentProfile).filter(
            StudentProfile.user_id == current_user.id
        ).first()

        if student_profile:
            skills = resolve_skills(
                db,
                engagement_data.skills,
                student_profile.id,
                current_user.id
            )
            for skill in skills:
                es = EngagementSkill(
                    engagement_id=engagement.id,
                    skill_id=skill.id
                )
                db.add(es)

    db.commit()
    db.refresh(engagement)

    return map_engagement_to_response(engagement)


@router.delete("/{engagement_id}")
def delete_engagement(
    engagement_id: UUID,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """Delete an engagement.

    Allowed only if status is NOT verified (verified engagements are immutable).
    """
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found"
        )

    # Verify ownership
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user.id
    ).first()
    if not student_profile or engagement.student_profile_id != student_profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this engagement"
        )

    # Check status - verified engagements are immutable
    if engagement.status == EngagementStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete engagement. Verified engagements are immutable."
        )

    db.delete(engagement)
    db.commit()

    return {"message": "Engagement deleted successfully"}


@router.post("/{engagement_id}/submit", response_model=EngagementResponse)
def submit_engagement(
    engagement_id: UUID,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """Submit an engagement for verification (draft -> pending)."""
    engagement = get_engagement_or_404(db, engagement_id, current_user)

    # Validate transition
    if not validate_status_transition(engagement.status, EngagementStatus.PENDING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit engagement with status '{engagement.status.value}'"
        )

    # Verify required fields before submission
    if not engagement.organization_name or not engagement.role or not engagement.start_date or not engagement.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name, role, start date, and end date are required to submit"
        )

    # Validate supervisor_ref is present
    if not engagement.supervisor_ref:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supervisor reference is required to submit"
        )

    # Resolve supervisor from supervisor_ref (ledger_id or email)
    supervisor = db.query(SupervisorProfile).join(User).filter(
        User.ledger_id == engagement.supervisor_ref
    ).first()

    # Try by email if not found by ledger_id
    if not supervisor:
        supervisor = db.query(SupervisorProfile).join(User).filter(
            User.email == engagement.supervisor_ref
        ).first()

    if not supervisor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid supervisor reference"
        )

    # Assign supervisor_profile_id
    engagement.supervisor_profile_id = supervisor.id

    # Update status
    engagement.status = EngagementStatus.PENDING

    db.commit()
    db.refresh(engagement)

    return map_engagement_to_response(engagement)


# ============== Supervisor Routes ==============

@router.get("/supervisor/engagements/requests", response_model=List[EngagementListResponse])
def get_supervisor_engagement_requests(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (all, pending, verified, rejected, edit_requested)"),
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """Get all engagements assigned to or accessible by this supervisor.

    Accessible engagements include:
    - Engagements where supervisor_profile_id matches current supervisor
    """
    # Get supervisor profile
    supervisor_profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == current_user.id
    ).first()

    if not supervisor_profile:
        return []

    # Build query for supervisor's engagements
    query = db.query(Engagement).filter(
        Engagement.supervisor_profile_id == supervisor_profile.id
    )

    # Apply status filter
    if status_filter and status_filter.lower() != "all":
        allowed_statuses = {"pending", "verified", "rejected", "edit_requested"}
        status_lower = status_filter.lower()
        if status_lower not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Allowed values: all, {', '.join(sorted(allowed_statuses))}"
            )
        try:
            status_enum = EngagementStatus(status_lower)
            query = query.filter(Engagement.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Allowed values: all, {', '.join(sorted(allowed_statuses))}"
            )

    engagements = query.order_by(Engagement.created_at.desc()).all()

    return [
        EngagementListResponse(
            id=e.id,
            organization_name=e.organization_name,
            role=e.role,
            start_date=e.start_date,
            end_date=e.end_date,
            status=EngagementStatusSchema(e.status.value),
            verified_at=e.verified_at
        )
        for e in engagements
    ]


@router.post("/{engagement_id}/approve", response_model=EngagementResponse)
def approve_engagement(
    engagement_id: UUID,
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """Approve an engagement (pending -> verified).

    Only allowed if status is 'pending'.
    Sets verification_type based on email domain vs organization match.
    Generates block_hash for immutable proof.
    Endorses all linked skills.
    """
    # Fetch engagement
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found"
        )

    # Get supervisor profile
    supervisor_profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == current_user.id
    ).first()

    if not supervisor_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supervisor profile not found"
        )

    # Verify supervisor is assigned to this engagement
    if engagement.supervisor_profile_id != supervisor_profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this engagement"
        )

    # Check status is pending
    if engagement.status != EngagementStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve engagement with status '{engagement.status.value}'. Only pending engagements can be approved."
        )

    # Determine verification type based on email domain vs organization match
    supervisor_email_domain = supervisor_profile.email_domain.lower()
    org_name = engagement.organization_name.lower()

    # Simple domain-in-org check
    verification_type = VerificationType.INDEPENDENT
    if supervisor_email_domain and any(
        domain_part in org_name for domain_part in supervisor_email_domain.split('.')
        if len(domain_part) > 2  # skip TLD parts like 'com', 'org'
    ):
        verification_type = VerificationType.INSTITUTIONAL

    # Generate verification timestamp
    verified_at = datetime.now(timezone.utc)

    # Generate block hash from engagement_id, student_profile_id, supervisor_profile_id, timestamp
    import hashlib
    payload = f"{engagement.id}:{engagement.student_profile_id}:{supervisor_profile.id}:{verified_at.isoformat()}"
    digest = hashlib.sha256(payload.encode()).hexdigest()
    block_hash = f"0x{digest[:6]}...{digest[-4:]}"

    # Update engagement in single transaction
    engagement.status = EngagementStatus.VERIFIED
    engagement.supervisor_profile_id = supervisor_profile.id
    engagement.verification_type = verification_type
    engagement.verified_at = verified_at
    engagement.block_hash = block_hash
    engagement.rejection_reason = None  # Clear any previous rejection reason

    # Endorse all linked skills (mark as verified)
    for es in engagement.engagement_skills:
        es.skill.is_verified = True

    db.commit()
    db.refresh(engagement)

    return map_engagement_to_response(engagement)


@router.post("/{engagement_id}/reject", response_model=EngagementResponse)
def reject_engagement(
    engagement_id: UUID,
    request_data: RejectEngagementRequest,
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """Reject an engagement (pending -> rejected).

    Only allowed if status is 'pending'.
    """
    # Fetch engagement
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found"
        )

    # Get supervisor profile
    supervisor_profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == current_user.id
    ).first()

    if not supervisor_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supervisor profile not found"
        )

    # Verify supervisor is assigned to this engagement
    if engagement.supervisor_profile_id != supervisor_profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this engagement"
        )

    # Check status is pending
    if engagement.status != EngagementStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject engagement with status '{engagement.status.value}'. Only pending engagements can be rejected."
        )

    # Update engagement
    engagement.status = EngagementStatus.REJECTED
    engagement.rejection_reason = request_data.reason

    db.commit()
    db.refresh(engagement)

    return map_engagement_to_response(engagement)


@router.post("/{engagement_id}/request-edit", response_model=EngagementResponse)
def request_edit_engagement(
    engagement_id: UUID,
    request_data: RequestEditEngagementRequest,
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """Request edits on an engagement (pending -> edit_requested).

    Only allowed if status is 'pending'.
    """
    # Fetch engagement
    engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    if not engagement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found"
        )

    # Get supervisor profile
    supervisor_profile = db.query(SupervisorProfile).filter(
        SupervisorProfile.user_id == current_user.id
    ).first()

    if not supervisor_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supervisor profile not found"
        )

    # Verify supervisor is assigned to this engagement
    if engagement.supervisor_profile_id != supervisor_profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this engagement"
        )

    # Check status is pending
    if engagement.status != EngagementStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot request edits on engagement with status '{engagement.status.value}'. Only pending engagements can be requested for edits."
        )

    # Update engagement
    engagement.status = EngagementStatus.EDIT_REQUESTED
    engagement.rejection_reason = request_data.reason

    db.commit()
    db.refresh(engagement)

    return map_engagement_to_response(engagement)