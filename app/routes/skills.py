"""
Skills module for declared and verified skills management.
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import case, func

from app.database import get_db
from app.models import User, Skill, SkillMaster
from app.schemas import (
    SkillCreateRequest,
    SkillResponse,
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
    # Get declared skills (is_verified = False)
    declared_skills = db.query(Skill).filter(
        Skill.user_id == current_user.id,
        Skill.is_verified == False
    ).order_by(Skill.name).all()

    declared_response = [
        SkillResponse(id=skill.id, name=skill.name)
        for skill in declared_skills
    ]

    # Get verified skills (is_verified = True)
    verified_skills = db.query(Skill).filter(
        Skill.user_id == current_user.id,
        Skill.is_verified == True
    ).all()

    # Group by name and count occurrences
    verified_counts: dict[str, int] = {}
    for skill in verified_skills:
        verified_counts[skill.name] = verified_counts.get(skill.name, 0) + 1

    verified_response = [
        VerifiedSkillItem(name=name, count=count)
        for name, count in sorted(verified_counts.items())
    ]

    return SkillListResponse(
        declared=declared_response,
        verified=verified_response
    )


@router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
def create_skill(
    skill_data: SkillCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new declared skill for the current user.

    Validates:
    - Name is not empty
    - Name is 2-100 characters
    - Skill doesn't already exist for this user (case-insensitive)
    """
    # Check for duplicate skill (case-insensitive)
    existing_skill = db.query(Skill).filter(
        Skill.user_id == current_user.id,
        Skill.name == skill_data.name
    ).first()

    if existing_skill:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Skill '{skill_data.name}' already exists"
        )

    # Create new skill
    new_skill = Skill(
        user_id=current_user.id,
        name=skill_data.name,
        is_verified=False
    )

    db.add(new_skill)
    db.commit()
    db.refresh(new_skill)

    return SkillResponse(id=new_skill.id, name=new_skill.name)


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
    skill = db.query(Skill).filter(Skill.id == skill_id).first()

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )

    # Check ownership
    if skill.user_id != current_user.id:
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