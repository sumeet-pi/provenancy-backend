from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import case

from app.database import get_db
from app.models import SkillMaster

router = APIRouter(prefix="/skills", tags=["Skills"])


@router.get("/search")
def search_skills(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db)
):
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