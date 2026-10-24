import csv
import io
from collections import Counter
from datetime import timedelta
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Interview, Question, User, Dataset, utcnow
from ..security import require_admin
from .interview import summary

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("")
def analytics(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    now = utcnow()
    interviews = db.query(Interview).all()
    finished = [i for i in interviews if i.finished]
    since = now - timedelta(days=30)
    daily = Counter(i.started_at.strftime("%Y-%m-%d") for i in interviews if i.started_at >= since)
    monthly = Counter(i.started_at.strftime("%Y-%m") for i in interviews)
    roles = Counter(i.role for i in interviews)
    cats = Counter(c for i in interviews for c in (i.categories or []))
    active_ids = {i.user_id for i in interviews if i.started_at >= since}

    def dist(col, n=10):
        rows = db.query(col, func.count(Question.id)).group_by(col).order_by(func.count(Question.id).desc()).limit(n).all()
        return [{"name": k or "(none)", "count": c} for k, c in rows]

    days = [(now - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(29, -1, -1)]
    return {
        "total_users": db.query(User).count(),
        "active_users": len(active_ids),
        "total_interviews": len(interviews),
        "total_questions": db.query(Question).count(),
        "total_categories": db.query(Question.category).distinct().count(),
        "avg_duration": int(sum(i.duration for i in finished) / len(finished)) if finished else 0,
        "top_roles": [{"name": k, "count": v} for k, v in roles.most_common(8)],
        "top_categories": [{"name": k, "count": v} for k, v in cats.most_common(8)],
        "daily": [{"date": d, "count": daily.get(d, 0)} for d in days],
        "monthly": [{"month": k, "count": v} for k, v in sorted(monthly.items())],
        "dataset": {
            "datasets": db.query(Dataset).count(),
            "by_difficulty": dist(Question.difficulty), "by_experience": dist(Question.experience),
            "by_category": dist(Question.category), "by_role": dist(Question.role),
        },
    }


@router.get("/export")
def export_report(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = {u.id: u for u in db.query(User)}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["interview_id", "user", "email", "date", "duration_sec", "role", "experience", "difficulty",
                "categories", "questions", "answered", "skipped", "viewed_ideal", "finished"])
    for iv in db.query(Interview).order_by(Interview.id):
        s = summary(iv)
        u = users.get(iv.user_id)
        w.writerow([iv.id, u.name if u else "", u.email if u else "", s["date"], s["duration"], iv.role,
                    iv.experience, iv.difficulty, "; ".join(iv.categories or []), s["asked"], s["answered"],
                    s["skipped"], s["viewed_ideal"], iv.finished])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=interview_report.csv"})
