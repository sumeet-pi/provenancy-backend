"""
Skills module for declared and verified skills management.
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import case, func

from app.database import get_db
from app.models import User, Skill, SkillMaster, StudentProfile, Engagement, EngagementSkill, EngagementStatus
from app.schemas import (
    SkillCreateRequest,
    SkillBulkCreateRequest,
    SkillResponse,
    SkillBulkResponse,
    VerifiedSkillItem,
    SkillListResponse,
    SkillDeleteResponse,
)
from app.auth import get_current_user

router = APIRouter(prefix="/skills", tags=["Skills"])


# ─────────────────────────────────────────────────────────────────────────────
# Skill Search (Public)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/search")
def search_skills(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
    """
    Search skills from the master list (public endpoint).
    Returns up to 10 matching skills for autocomplete.
    """
    results = db.query(SkillMaster)\
        .filter(SkillMaster.name.ilike(f"%{q}%"))\
        .order_by(
            case(
                (SkillMaster.name.ilike(q), 0),        # exact match first
                (SkillMaster.name.ilike(f"{q}%"), 1),  # starts with second
                else_=2                                  # contains last
            ),
            SkillMaster.name
        )\
        .limit(10)\
        .all()

    return [{"id": str(s.id), "name": s.name} for s in results]


# ─────────────────────────────────────────────────────────────────────────────
# User Skills (Protected)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=SkillListResponse)
def get_skills(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all skills for the current user.

    Returns both declared skills (user-added) and verified skills (from approved engagements).
    Verified skills are currently derived from the skills table where is_verified=True.
    """
    # Get student's profile
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user.id
    ).first()

    if not student_profile:
        return SkillListResponse(declared=[], verified=[])

    # Get declared skills (is_verified = False)
    declared_skills = db.query(Skill).filter(
        Skill.student_profile_id == student_profile.id,
        Skill.is_verified == False
    ).order_by(Skill.name).all()

    declared_response = [
        SkillResponse(id=skill.id, name=skill.name)
        for skill in declared_skills
    ]

    # Get verified skills - count by counting verified engagements that have each skill
    # First get all skills that have been verified (is_verified = True)
    verified_skill_names = db.query(Skill.name).filter(
        Skill.student_profile_id == student_profile.id,
        Skill.is_verified == True
    ).distinct().all()

    # For each verified skill, count how many verified engagements have it
    verified_counts: dict[str, int] = {}
    for (skill_name,) in verified_skill_names:
        # Count engagements that are verified AND have this skill
        count = db.query(func.count(Engagement.id)).join(
            EngagementSkill, Engagement.id == EngagementSkill.engagement_id
        ).join(
            Skill, EngagementSkill.skill_id == Skill.id
        ).filter(
            Engagement.student_profile_id == student_profile.id,
            Engagement.status == EngagementStatus.VERIFIED,
            Skill.name == skill_name
        ).scalar() or 0
        verified_counts[skill_name] = count

    verified_response = [
        VerifiedSkillItem(name=name, count=count)
        for name, count in sorted(verified_counts.items())
    ]

    return SkillListResponse(
        declared=declared_response,
        verified=verified_response
    )


@router.post("", response_model=SkillBulkResponse, status_code=status.HTTP_201_CREATED)
def create_skills(
    skill_data: SkillBulkCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create multiple declared skills for the current user.

    Validates:
    - Each skill name is not empty
    - Each skill name is 2-100 characters
    - Maximum 10 skills can be added at once
    - Duplicate skills within the request are deduplicated
    - Skills that already exist for this user are skipped

    Returns:
        created: List of skills that were successfully created
        skipped: List of skill names that already existed and were skipped
    """
    # Get student's profile
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user.id
    ).first()

    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile not found"
        )

    created_skills: List[SkillResponse] = []
    skipped_skills: List[str] = []

    # Get existing skill names for this student
    existing_skills = db.query(Skill).filter(
        Skill.student_profile_id == student_profile.id
    ).all()
    existing_names = {skill.name.lower() for skill in existing_skills}

    # Process each skill
    for skill_name in skill_data.skills:
        if skill_name.lower() in existing_names:
            skipped_skills.append(skill_name)
            continue

        # Create new skill
        new_skill = Skill(
            student_profile_id=student_profile.id,
            user_id=current_user.id,
            name=skill_name,
            is_verified=False
        )
        db.add(new_skill)
        db.flush()  # Flush to get the ID without committing

        created_skills.append(SkillResponse(id=new_skill.id, name=new_skill.name))
        existing_names.add(skill_name.lower())  # Prevent duplicates in same batch

    db.commit()

    return SkillBulkResponse(
        created=created_skills,
        skipped=skipped_skills
    )


@router.delete("/{skill_id}", response_model=SkillDeleteResponse)
def delete_skill(
    skill_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a skill by ID.

    Rules:
    - Skill must belong to the current user
    - Verified skills (is_verified=True) cannot be deleted
    - Returns 404 if skill not found
    """
    # Get student's profile
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == current_user.id
    ).first()

    if not student_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )

    skill = db.query(Skill).filter(Skill.id == skill_id).first()

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )

    # Check ownership (using student_profile_id)
    if skill.student_profile_id != student_profile.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )

    # Prevent deletion of verified skills
    if skill.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verified skills cannot be deleted"
        )

    db.delete(skill)
    db.commit()

    return SkillDeleteResponse(message="Skill removed")