"""Semantic question retrieval.

1. Filter candidates in SQL by role / experience / difficulty / category.
2. Embed a query built from the interview configuration with Sentence-BERT.
3. Rank candidates by cosine similarity (vectors come from FAISS).
4. Skip questions already asked, and near-duplicates (>0.92 similarity) of asked ones.
5. The query also contains the candidate's latest answer, so the next question follows the conversation; TOP_K (default 1) is the number
   of best-ranked questions to choose from (1 = always the most similar unseen question).
6. Maximal Marginal Relevance: scores are reduced by similarity to questions already asked, so the interview stays varied.
If no candidate matches, filters are relaxed step by step (role is always kept).
"""
import os
import random
import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models import Question, Interview
from .nlp import store

NEAR_DUP = 0.92
MMR_LAMBDA = 0.7  # 1.0 = pure relevance; lower = more variety between questions
MAX_CANDIDATES = 20000
# FR-4: the most suitable unseen question is returned (TOP_K=1). Set RETRIEVAL_TOP_K=5 to pick randomly among the best 5 instead.
TOP_K = max(1, int(os.getenv("RETRIEVAL_TOP_K", "1")))
# (use experience, use difficulty, category mode: 2=rotating category, 1=any selected category, 0=ignore)
RELAX_STEPS = [(1, 1, 2), (1, 1, 1), (1, 1, 0), (1, 0, 0), (0, 0, 0)]


def _candidates(db: Session, iv: Interview, asked_ids, step, cat):
    use_exp, use_diff, cat_mode = step
    q = db.query(Question.id, Question.vec_idx).filter(Question.vec_idx >= 0, Question.vec_idx < store.total)
    q = q.filter(func.lower(Question.role) == iv.role.lower())
    if use_exp and iv.experience:
        q = q.filter(func.lower(Question.experience) == iv.experience.lower())
    if use_diff and iv.difficulty:
        q = q.filter(func.lower(Question.difficulty) == iv.difficulty.lower())
    cats = [c.lower() for c in (iv.categories or [])]
    if cat_mode == 2 and cat:
        q = q.filter(func.lower(Question.category) == cat.lower())
    elif cat_mode == 1 and cats:
        q = q.filter(func.lower(Question.category).in_(cats))
    if asked_ids:
        q = q.filter(~Question.id.in_(asked_ids))
    return q.limit(MAX_CANDIDATES).all()


def select_question(db: Session, iv: Interview):
    """Return the most suitable unseen Question for this interview, or None."""
    asked = [i.question_id for i in iv.items if i.question_id]
    cats = iv.categories or []
    cat = cats[len(iv.items) % len(cats)] if cats else None  # rotate through chosen categories

    rows = []
    for step in RELAX_STEPS:
        if step[2] == 2 and not cat:
            continue
        rows = _candidates(db, iv, asked, step, cat)
        if rows:
            break
    if not rows:
        return None

    ids = np.array([r[0] for r in rows])
    pos = np.array([r[1] for r in rows])
    cand_vecs = store.vectors(pos)

    query_text = f"{iv.role} {cat or ' '.join(cats)} {iv.difficulty} interview question".strip()
    last_answer = next((i.user_answer for i in reversed(iv.items) if i.user_answer and not i.is_skipped), None)
    if last_answer:  # follow the conversation: the next question is similar to the setup AND to what the candidate just said
        query_text += " " + last_answer[:300]
    qvec = store.embed([query_text])[0]
    scores = cand_vecs @ qvec

    # drop near-duplicates of already asked questions
    if asked:
        asked_pos = [p for (p,) in db.query(Question.vec_idx).filter(Question.id.in_(asked), Question.vec_idx >= 0)]
        if asked_pos:
            sim = cand_vecs @ store.vectors(asked_pos).T
            max_sim = sim.max(axis=1)
            scores = MMR_LAMBDA * scores - (1 - MMR_LAMBDA) * max_sim
            keep = max_sim < NEAR_DUP
            if keep.any():
                scores = np.where(keep, scores, -np.inf)

    order = [int(i) for i in np.argsort(-scores)[:TOP_K] if np.isfinite(scores[i])]
    if not order:
        order = [int(np.argmax(scores))]
    best = int(ids[random.choice(order)])
    return db.get(Question, best)


def tips_for(q: Question) -> list:
    tips = []
    st = (q.source_type or "").lower()
    cat = (q.category or "").lower()
    if "behav" in st or "time" in (q.question or "").lower():
        tips.append("Use the STAR method: Situation, Task, Action, Result.")
    else:
        tips.append("Answer directly first, then support it with one concrete example.")
    tips.append("Keep your answer to about 1-2 minutes and stay specific.")
    if q.keywords:
        tips.append("Naturally work in the key ideas: " + ", ".join(k.keyword for k in q.keywords[:4]) + ".")
    if "lead" in cat:
        tips.append("Show how you influenced others, not only what you did yourself.")
    elif "adapt" in cat:
        tips.append("Highlight how quickly you learned and what you changed afterwards.")
    elif "motiv" in cat:
        tips.append("Connect your answer to the role and the company, not just personal gain.")
    else:
        tips.append("Finish with the result and what you learned.")
    return tips
