from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Interview, InterviewQuestion, Question, User, utcnow
from ..security import get_current_user
from ..services.retrieval import select_question, tips_for

router = APIRouter(prefix="/interview", tags=["Interview"])

GREETING = "Hello! I'm your HR interview coach. I'll ask one question at a time."
RULES = [
    "Answer each question in your own words, then press Send Answer.",
    "You can skip a question, but skipped questions are recorded.",
    "After answering, you may open the ideal answer, keywords and tips.",
    "Press Next Question to continue until the interview ends.",
]


class StartIn(BaseModel):
    role: str
    experience: str
    difficulty: str
    categories: List[str] = []
    num_questions: int = Field(5, ge=1, le=50)


class AnswerIn(BaseModel):
    interview_id: int
    interview_question_id: int
    answer: str = Field(min_length=1)


class SkipIn(BaseModel):
    interview_id: int
    interview_question_id: int


class FinishIn(BaseModel):
    interview_id: int


def _own_interview(db: Session, user: User, interview_id: int) -> Interview:
    iv = db.get(Interview, interview_id)
    if not iv or iv.user_id != user.id:
        raise HTTPException(404, "Interview not found")
    return iv


def _own_item(db: Session, iv: Interview, item_id: int) -> InterviewQuestion:
    item = db.get(InterviewQuestion, item_id)
    if not item or item.interview_id != iv.id:
        raise HTTPException(404, "Interview question not found")
    return item


def _duration(iv: Interview) -> int:
    end = iv.finished_at or utcnow()
    return int((end - iv.started_at).total_seconds())


def summary(iv: Interview) -> dict:
    answered = sum(1 for i in iv.items if i.user_answer and not i.is_skipped)
    skipped = sum(1 for i in iv.items if i.is_skipped)
    return {
        "id": iv.id, "date": iv.started_at.isoformat(), "started_at": iv.started_at.isoformat(),
        "finished_at": iv.finished_at.isoformat() if iv.finished_at else None,
        "duration": iv.duration if iv.finished else _duration(iv),
        "role": iv.role, "experience": iv.experience, "difficulty": iv.difficulty,
        "categories": iv.categories or [], "num_questions": iv.num_questions, "finished": iv.finished,
        "asked": len(iv.items), "answered": answered, "skipped": skipped,
        "viewed_ideal": sum(1 for i in iv.items if i.viewed_ideal_answer),
    }


@router.post("/start")
def start(data: StartIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    has_role = db.query(Question.id).filter(func.lower(Question.role) == data.role.lower()).first()
    if not has_role:
        raise HTTPException(400, "No questions found for this job role. Ask an administrator to import the dataset.")
    iv = Interview(user_id=user.id, role=data.role, experience=data.experience, difficulty=data.difficulty,
                   categories=data.categories, num_questions=data.num_questions)
    db.add(iv); db.commit(); db.refresh(iv)
    return {"interview": summary(iv), "greeting": GREETING, "rules": RULES}


@router.get("/question")
def next_question(interview_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    iv = _own_interview(db, user, interview_id)
    if iv.finished:
        return {"done": True}
    pending = next((i for i in iv.items if i.user_answer is None and not i.is_skipped), None)
    if not pending:
        if len(iv.items) >= iv.num_questions:
            return {"done": True}
        q = select_question(db, iv)
        if not q:
            return {"done": True, "reason": "No more unseen questions match this configuration."}
        pending = InterviewQuestion(interview_id=iv.id, question_id=q.id, question_text=q.question)
        db.add(pending); db.commit(); db.refresh(pending); db.refresh(iv)
    q = db.get(Question, pending.question_id)
    return {
        "done": False, "interview_question_id": pending.id, "question": pending.question_text,
        "category": q.category if q else "", "difficulty": q.difficulty if q else "",
        "source_type": q.source_type if q else "", "index": len(iv.items), "total": iv.num_questions,
    }


@router.post("/answer")
def answer(data: AnswerIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    iv = _own_interview(db, user, data.interview_id)
    item = _own_item(db, iv, data.interview_question_id)
    item.user_answer = data.answer.strip()
    item.is_skipped = False
    db.commit()
    return {"saved": True}


@router.post("/skip")
def skip(data: SkipIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    iv = _own_interview(db, user, data.interview_id)
    item = _own_item(db, iv, data.interview_question_id)
    item.is_skipped = True
    db.commit()
    return {"skipped": True}


@router.get("/ideal/{item_id}")
def ideal_answer(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(InterviewQuestion, item_id)
    if not item:
        raise HTTPException(404, "Not found")
    _own_interview(db, user, item.interview_id)
    q = db.get(Question, item.question_id) if item.question_id else None
    if not q:
        raise HTTPException(404, "The original question is no longer available")
    item.viewed_ideal_answer = True
    db.commit()
    return {
        "ideal_answer": q.ideal_answer, "keywords": [k.keyword for k in q.keywords], "category": q.category,
        "difficulty": q.difficulty, "role": q.role, "experience": q.experience, "source_type": q.source_type,
        "tips": tips_for(q),
    }


@router.post("/finish")
def finish(data: FinishIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    iv = _own_interview(db, user, data.interview_id)
    if not iv.finished:
        iv.finished_at = utcnow()
        iv.finished = True
        iv.duration = _duration(iv)
        # pending (never answered / skipped) questions count as skipped
        for i in iv.items:
            if i.user_answer is None and not i.is_skipped:
                i.is_skipped = True
        db.commit(); db.refresh(iv)
    return summary(iv)


@router.get("/history")
def history(search: str = "", role: str = "", date_from: Optional[str] = None, date_to: Optional[str] = None,
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Interview).filter(Interview.user_id == user.id)
    if role:
        q = q.filter(func.lower(Interview.role) == role.lower())
    try:
        if date_from:
            q = q.filter(Interview.started_at >= datetime.fromisoformat(date_from))
        if date_to:
            q = q.filter(Interview.started_at < datetime.fromisoformat(date_to) + timedelta(days=1))
    except ValueError:
        raise HTTPException(400, "Dates must look like 2026-10-31")
    rows = q.order_by(Interview.started_at.desc()).all()
    if search:
        s = search.lower()
        rows = [r for r in rows if s in r.role.lower() or any(s in (i.question_text or "").lower() or s in (i.user_answer or "").lower() for i in r.items)]
    return [summary(r) for r in rows]


@router.get("/stats")
def my_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Interview).filter(Interview.user_id == user.id).all()
    finished = [r for r in rows if r.finished]
    return {
        "total": len(rows), "completed": len(finished),
        "answered": sum(summary(r)["answered"] for r in rows),
        "skipped": sum(summary(r)["skipped"] for r in rows),
        "avg_duration": int(sum(r.duration for r in finished) / len(finished)) if finished else 0,
    }


@router.get("/{interview_id}")
def detail(interview_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    iv = _own_interview(db, user, interview_id)
    items = []
    for it in iv.items:
        q = db.get(Question, it.question_id) if it.question_id else None
        items.append({
            "id": it.id, "question": it.question_text, "answer": it.user_answer, "skipped": it.is_skipped,
            "viewed_ideal": it.viewed_ideal_answer, "category": q.category if q else "",
            "ideal_answer": q.ideal_answer if q else "", "keywords": [k.keyword for k in q.keywords] if q else [],
        })
    return {**summary(iv), "items": items}
