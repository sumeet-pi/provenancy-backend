from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SkillMaster

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/search")
def search_skills(q: str, db: Session = Depends(get_db)):
    """
    Search skill_master table for autocomplete.
    Returns top 10 matching skills for the given query.
    Case-insensitive partial match.
    """
    if not q or len(q) < 1:
        return []

    results = db.query(SkillMaster)\
        .filter(SkillMaster.name.ilike(f"{q}%"))\
        .order_by(SkillMaster.name)\
        .limit(10)\
        .all()

    return [{"id": str(s.id), "name": s.name, "category": s.category} for s in results]
