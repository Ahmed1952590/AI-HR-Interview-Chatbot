"""Show semantic retrieval in the terminal (handy for the defense and the report).

Usage (from the backend folder, after the dataset has been imported):
    python scripts/semantic_demo.py --role "DevOps Engineer" --experience Fresher --difficulty Easy --category Adaptability
    python scripts/semantic_demo.py --text "how do you handle sudden change at work" --role "DevOps Engineer"

Mode 1 ranks the filtered pool against the interview setup (what the chatbot does).
Mode 2 (--text) ranks questions by meaning against any sentence you type, using the whole FAISS index.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np                       # noqa: E402
from sqlalchemy import func              # noqa: E402
from app.database import SessionLocal    # noqa: E402
from app.models import Question          # noqa: E402
from app.services.nlp import store       # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--role", default="")
ap.add_argument("--experience", default="")
ap.add_argument("--difficulty", default="")
ap.add_argument("--category", default="")
ap.add_argument("--text", default="", help="free text query (search by meaning)")
ap.add_argument("--top", type=int, default=8)
a = ap.parse_args()

db = SessionLocal()
print(f"Vectors in FAISS index: {store.total:,}   Questions in database: {db.query(Question).count():,}\n")

if a.text:
    scores, idxs = store.index.search(store.embed([a.text]), a.top * 25)
    best = {int(i): float(s) for s, i in zip(scores[0], idxs[0]) if i >= 0}
    q = db.query(Question).filter(Question.vec_idx.in_(list(best)))
    if a.role:
        q = q.filter(func.lower(Question.role) == a.role.lower())
    rows = sorted(q.all(), key=lambda r: best[r.vec_idx], reverse=True)[:a.top]
    print(f'Query: "{a.text}"')
    for r in rows:
        print(f"  {best[r.vec_idx]:.3f}  [{r.role} | {r.experience} | {r.difficulty} | {r.category}]  {r.question}")
else:
    q = db.query(Question).filter(Question.vec_idx >= 0)
    for col, val in ((Question.role, a.role), (Question.experience, a.experience),
                     (Question.difficulty, a.difficulty), (Question.category, a.category)):
        if val:
            q = q.filter(func.lower(col) == val.lower())
    rows = q.limit(20000).all()
    if not rows:
        sys.exit("No questions match these filters.")
    query = f"{a.role} {a.category} {a.difficulty} interview question".strip()
    vecs = store.vectors([r.vec_idx for r in rows])
    scores = vecs @ store.embed([query])[0]
    print(f'Pool: {len(rows):,} questions after filters. Query: "{query}"')
    for i in np.argsort(-scores)[:a.top]:
        r = rows[int(i)]
        print(f"  {scores[i]:.3f}  [{r.category} | {r.source_type}]  {r.question}")
