from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Question, Keyword, Category, JobRole, User
from ..security import require_admin
from ..services.importer import dedupe_key
from ..services.nlp import store

router = APIRouter(prefix="/questions", tags=["Questions"])


class QuestionIn(BaseModel):
    question: str = Field(min_length=5)
    category: str
    role: str
    experience: str
    difficulty: str
    source_type: str = ""
    ideal_answer: str = ""
    keywords: List[str] = []


class QuestionUpdate(BaseModel):
    question: Optional[str] = None
    category: Optional[str] = None
    role: Optional[str] = None
    experience: Optional[str] = None
    difficulty: Optional[str] = None
    source_type: Optional[str] = None
    ideal_answer: Optional[str] = None
    keywords: Optional[List[str]] = None


def q_out(q: Question) -> dict:
    return {
        "id": q.id, "question": q.question, "category": q.category, "role": q.role, "experience": q.experience,
        "difficulty": q.difficulty, "source_type": q.source_type, "ideal_answer": q.ideal_answer,
        "keywords": [k.keyword for k in q.keywords],
    }


def _ensure_lookup(db: Session, category: str, role: str):
    if category and not db.query(Category).filter(Category.name == category).first():
        db.add(Category(name=category))
    if role and not db.query(JobRole).filter(JobRole.name == role).first():
        db.add(JobRole(name=role))


def _embed(q: Question):
    q.vec_idx = store.add(store.embed([q.question]))
    store.save_later()


@router.get("/semantic")
def semantic_search(q: str, role: str = "", limit: int = 10, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Search by meaning: embed the text with Sentence-BERT and return the nearest questions from FAISS."""
    if not q.strip() or store.total == 0:
        return {"items": []}
    limit = max(1, min(limit, 50))
    scores, idxs = store.index.search(store.embed([q]), min(store.total, limit * 25))
    best = {int(i): float(s) for s, i in zip(scores[0], idxs[0]) if i >= 0}
    query = db.query(Question).filter(Question.vec_idx.in_(list(best)))
    if role:
        query = query.filter(func.lower(Question.role) == role.lower())
    rows = sorted(query.all(), key=lambda r: best[r.vec_idx], reverse=True)[:limit]
    return {"items": [{**q_out(r), "score": round(best[r.vec_idx], 4)} for r in rows]}


@router.get("")
def list_questions(search: str = "", role: str = "", category: str = "", experience: str = "", difficulty: str = "",
                   source_type: str = "", page: int = 1, page_size: int = 20,
                   _: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(Question)
    if search:
        like = f"%{search.lower()}%"
        q = q.filter(or_(Question.question.ilike(like), Question.ideal_answer.ilike(like)))
    for col, val in ((Question.role, role), (Question.category, category), (Question.experience, experience),
                     (Question.difficulty, difficulty), (Question.source_type, source_type)):
        if val:
            q = q.filter(func.lower(col) == val.lower())
    total = q.count()
    rows = q.order_by(Question.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "items": [q_out(r) for r in rows]}


@router.post("")
def create_question(data: QuestionIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    n = dedupe_key(data.question, data.role, data.experience, data.difficulty, data.category)
    if db.query(Question.id).filter(Question.norm == n).first():
        raise HTTPException(400, "This question already exists")
    q = Question(question=data.question.strip(), norm=n, category=data.category.strip(), role=data.role.strip(),
                 experience=data.experience.strip(), difficulty=data.difficulty.strip().title(),
                 source_type=data.source_type.strip(), ideal_answer=data.ideal_answer.strip(),
                 keywords=[Keyword(keyword=k.strip()) for k in data.keywords if k.strip()])
    _embed(q)
    _ensure_lookup(db, q.category, q.role)
    db.add(q); db.commit(); db.refresh(q)
    return q_out(q)


@router.put("/{question_id}")
def update_question(question_id: int, data: QuestionUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    payload = data.model_dump(exclude_unset=True)
    keywords = payload.pop("keywords", None)
    re_embed = False
    for k, v in payload.items():
        if v is None:
            continue
        v = v.strip()
        if k == "question" and v != q.question:
            re_embed = True
        if k == "difficulty":
            v = v.title()
        setattr(q, k, v)
    new_key = dedupe_key(q.question, q.role, q.experience, q.difficulty, q.category)
    if new_key != q.norm:
        if db.query(Question.id).filter(Question.norm == new_key, Question.id != q.id).first():
            raise HTTPException(400, "Another question with the same text, role, level, difficulty and category already exists")
        q.norm = new_key
    if keywords is not None:
        q.keywords = [Keyword(keyword=k.strip()) for k in keywords if k.strip()]
    if re_embed:
        _embed(q)  # a new vector is appended; the old position is simply no longer referenced
    _ensure_lookup(db, q.category, q.role)
    db.commit(); db.refresh(q)
    return q_out(q)


@router.delete("/{question_id}")
def delete_question(question_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404, "Question not found")
    db.delete(q); db.commit()
    return {"message": "Question deleted"}
