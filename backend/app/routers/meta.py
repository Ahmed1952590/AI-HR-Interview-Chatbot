"""Option lists for the interview form + admin management of categories and job roles."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Category, JobRole, Question, User
from ..security import get_current_user, require_admin

router = APIRouter(tags=["Categories & Roles"])


class NameIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


@router.get("/options")
def options(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    def distinct(col):
        return sorted({v for (v,) in db.query(col).distinct() if v})
    return {
        "roles": sorted({r.name for r in db.query(JobRole)} | set(distinct(Question.role))),
        "categories": sorted({c.name for c in db.query(Category)} | set(distinct(Question.category))),
        "experiences": distinct(Question.experience),
        "difficulties": distinct(Question.difficulty),
    }


def _crud(path: str, Model, field: str):
    def usage(db, name):
        return db.query(Question).filter(func.lower(getattr(Question, field)) == name.lower()).count()

    @router.get(f"/{path}", name=f"list_{path}")
    def list_all(_: User = Depends(require_admin), db: Session = Depends(get_db)):
        return [{"id": r.id, "name": r.name, "questions": usage(db, r.name)} for r in db.query(Model).order_by(Model.name)]

    @router.post(f"/{path}", name=f"add_{path}")
    def add(data: NameIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
        name = data.name.strip()
        if db.query(Model).filter(func.lower(Model.name) == name.lower()).first():
            raise HTTPException(400, "Already exists")
        row = Model(name=name); db.add(row); db.commit(); db.refresh(row)
        return {"id": row.id, "name": row.name, "questions": 0}

    @router.put(f"/{path}/{{item_id}}", name=f"edit_{path}")
    def edit(item_id: int, data: NameIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
        row = db.get(Model, item_id)
        if not row:
            raise HTTPException(404, "Not found")
        old, new = row.name, data.name.strip()
        row.name = new
        db.query(Question).filter(getattr(Question, field) == old).update({field: new})  # keep questions in sync
        db.commit()
        return {"id": row.id, "name": row.name}

    @router.delete(f"/{path}/{{item_id}}", name=f"delete_{path}")
    def delete(item_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
        row = db.get(Model, item_id)
        if not row:
            raise HTTPException(404, "Not found")
        if usage(db, row.name):
            raise HTTPException(400, "Still used by questions. Edit or delete those questions first.")
        db.delete(row); db.commit()
        return {"message": "Deleted"}


_crud("categories", Category, "category")
_crud("roles", JobRole, "role")
